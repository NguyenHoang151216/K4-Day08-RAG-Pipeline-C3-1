"""
RAG Evaluation Pipeline.

Sử dụng RAGAS để đánh giá chất lượng RAG pipeline.

Yêu cầu:
    1. Load golden_dataset.json (≥15 Q&A pairs)
    2. Chạy RAG pipeline trên từng question
    3. Evaluate với 4 metrics: faithfulness, relevance, context_recall, context_precision
    4. So sánh A/B ít nhất 2 configs
    5. Export results ra results.md

Lưu ý rate limit nếu dùng model OpenRouter ":free": RAGAS/DeepEval gọi LLM RẤT NHIỀU LẦN
(không phải 1 lần/câu hỏi mà nhiều lần/metric/câu hỏi). Model free của OpenRouter giới hạn
50 request/ngày CHO CẢ TÀI KHOẢN (không phải theo model hay theo API key — đổi model free
khác hay tạo key mới KHÔNG reset quota). Nếu chạy full 15+ câu hỏi mà bị rate limit giữa
chừng, thử giảm xuống subset 5 câu để chạy kịp trong buổi, hoặc nạp $10 credit để mở khóa
1000 request/ngày.
"""

import json
import os
import time
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

GOLDEN_DATASET_PATH = Path(__file__).parent / "golden_dataset.json"
RESULTS_PATH = Path(__file__).parent / "results.md"


def load_golden_dataset() -> list[dict]:
    """Load golden dataset từ JSON file."""
    with open(GOLDEN_DATASET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# =============================================================================
# Helpers
# =============================================================================

def _get_llm_judge():
    """
    Tạo LLM judge trỏ về OpenRouter cho RAGAS.
    RAGAS cần LLM để chấm điểm faithfulness, relevancy, v.v.
    """
    from langchain_openai import ChatOpenAI

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENROUTER_API_KEY không tìm thấy trong .env. "
            "Vui lòng tạo file .env và điền key."
        )

    # Model :free trên OpenRouter — giới hạn 50 req/ngày
    # Thay đổi model nếu cần: https://openrouter.ai/models?max_price=0
    llm = ChatOpenAI(
        model="meta-llama/llama-4-scout-17b-16e-instruct:free",
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        temperature=0.0,
        max_retries=2,
    )
    return llm


def _get_embeddings():
    """Tạo embedding model cho RAGAS (dùng cho answer_relevancy metric)."""
    from langchain_openai import OpenAIEmbeddings

    api_key = os.getenv("OPENROUTER_API_KEY")
    # OpenRouter không hỗ trợ embeddings, dùng HuggingFace local thay thế
    try:
        from langchain_huggingface import HuggingFaceEmbeddings
        return HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
    except ImportError:
        # Fallback: không dùng embeddings, RAGAS sẽ skip answer_relevancy
        print("⚠ langchain_huggingface chưa cài, answer_relevancy có thể bị skip.")
        return None


def _run_rag_pipeline_config_a(question: str, top_k: int = 5) -> dict:
    """
    Config A: Hybrid + Rerank (full pipeline).
    Gọi retrieve(use_reranking=True) → generate_with_citation().
    
    Returns: {'answer': str, 'sources': list[dict], 'contexts': list[str]}
    """
    try:
        from src.task10_generation import generate_with_citation
        result = generate_with_citation(question, top_k=top_k)
        return {
            "answer": result.get("answer", ""),
            "sources": result.get("sources", []),
            "contexts": [s.get("content", "") for s in result.get("sources", [])],
        }
    except Exception as e:
        print(f"  ⚠ Config A lỗi cho câu: {question[:50]}... → {e}")
        return {"answer": f"Lỗi: {e}", "sources": [], "contexts": []}


def _run_rag_pipeline_config_b(question: str, top_k: int = 5) -> dict:
    """
    Config B: Dense-Only (chỉ semantic search, không rerank, không fallback).
    Gọi trực tiếp semantic_search() → generate LLM.
    
    Returns: {'answer': str, 'sources': list[dict], 'contexts': list[str]}
    """
    try:
        from src.task5_semantic_search import semantic_search
        from src.task10_generation import (
            reorder_for_llm,
            format_context,
            SYSTEM_PROMPT,
        )
        from openai import OpenAI

        # Bước 1: Chỉ dùng semantic search (dense-only)
        results = semantic_search(question, top_k=top_k)

        if not results:
            return {
                "answer": "Không tìm thấy thông tin liên quan.",
                "sources": [],
                "contexts": [],
            }

        # Bước 2: Reorder + format context + gọi LLM
        reordered = reorder_for_llm(results)
        context_str = format_context(reordered)

        client = OpenAI(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1",
        )

        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct:free",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Context:\n{context_str}\n\nQuestion: {question}",
                },
            ],
            temperature=0.3,
        )
        answer = response.choices[0].message.content

        return {
            "answer": answer,
            "sources": results,
            "contexts": [r.get("content", "") for r in results],
        }
    except Exception as e:
        print(f"  ⚠ Config B lỗi cho câu: {question[:50]}... → {e}")
        return {"answer": f"Lỗi: {e}", "sources": [], "contexts": []}


# =============================================================================
# RAGAS Evaluation
# =============================================================================

def evaluate_with_ragas(
    golden_dataset: list[dict],
    config_name: str = "hybrid_rerank",
    max_questions: int | None = None,
) -> dict:
    """
    Evaluate RAG pipeline sử dụng RAGAS.

    Args:
        golden_dataset: List các câu Q&A từ golden_dataset.json
        config_name: "hybrid_rerank" (Config A) hoặc "dense_only" (Config B)
        max_questions: Giới hạn số câu (tiết kiệm quota). None = chạy hết.

    Returns:
        Dict chứa DataFrame kết quả và scores trung bình.
    """
    from ragas import evaluate
    from ragas.metrics import (
        faithfulness,
        answer_relevancy,
        context_recall,
        context_precision,
    )
    from datasets import Dataset

    # Chọn pipeline function theo config
    if config_name == "dense_only":
        run_fn = _run_rag_pipeline_config_b
    else:
        run_fn = _run_rag_pipeline_config_a

    # Giới hạn số câu nếu cần (tiết kiệm rate limit)
    dataset_to_eval = golden_dataset
    if max_questions is not None:
        dataset_to_eval = golden_dataset[:max_questions]

    print(f"\n{'='*60}")
    print(f"🔄 Đang chạy RAG pipeline [{config_name}] cho {len(dataset_to_eval)} câu...")
    print(f"{'='*60}")

    eval_data = {
        "question": [],
        "answer": [],
        "contexts": [],
        "ground_truth": [],
    }

    for i, item in enumerate(dataset_to_eval):
        question = item["question"]
        print(f"  [{i+1}/{len(dataset_to_eval)}] {question[:60]}...")

        # Gọi RAG pipeline
        result = run_fn(question)

        eval_data["question"].append(question)
        eval_data["answer"].append(result["answer"])
        eval_data["contexts"].append(
            result["contexts"] if result["contexts"] else ["Không có context."]
        )
        eval_data["ground_truth"].append(item.get("expected_answer", ""))

        # Delay nhẹ tránh rate limit
        time.sleep(1)

    dataset = Dataset.from_dict(eval_data)

    # Lấy LLM judge
    llm = _get_llm_judge()
    embeddings = _get_embeddings()

    print(f"\n🔍 Đang chạy RAGAS evaluation (4 metrics)...")
    print(f"   ⚠ Bước này tốn nhiều API calls — kiên nhẫn chờ...\n")

    # Chạy evaluation
    try:
        eval_kwargs = {
            "dataset": dataset,
            "metrics": [faithfulness, answer_relevancy, context_recall, context_precision],
            "llm": llm,
        }
        if embeddings:
            eval_kwargs["embeddings"] = embeddings

        ragas_result = evaluate(**eval_kwargs)

        df = ragas_result.to_pandas()

        # Tính scores trung bình
        avg_scores = {
            "faithfulness": df["faithfulness"].mean() if "faithfulness" in df else None,
            "answer_relevancy": df["answer_relevancy"].mean() if "answer_relevancy" in df else None,
            "context_recall": df["context_recall"].mean() if "context_recall" in df else None,
            "context_precision": df["context_precision"].mean() if "context_precision" in df else None,
        }

        print(f"\n✅ Kết quả [{config_name}]:")
        for metric, score in avg_scores.items():
            if score is not None:
                print(f"   {metric}: {score:.4f}")

        return {
            "config_name": config_name,
            "dataframe": df,
            "avg_scores": avg_scores,
            "num_questions": len(dataset_to_eval),
        }

    except Exception as e:
        print(f"\n❌ RAGAS evaluation lỗi: {e}")
        print(f"   Có thể do hết quota OpenRouter (50 req/ngày).")
        print(f"   Thử giảm max_questions hoặc mượn API key khác.")
        return {
            "config_name": config_name,
            "dataframe": None,
            "avg_scores": {
                "faithfulness": None,
                "answer_relevancy": None,
                "context_recall": None,
                "context_precision": None,
            },
            "num_questions": len(dataset_to_eval),
            "error": str(e),
        }


# =============================================================================
# A/B Comparison
# =============================================================================

def compare_configs(
    golden_dataset: list[dict],
    max_questions: int | None = 5,
) -> dict:
    """
    So sánh A/B giữa 2 configs:
    - Config A: Hybrid search + RRF reranking (full pipeline)
    - Config B: Dense-only (chỉ semantic search, không rerank)

    Args:
        golden_dataset: List Q&A từ golden_dataset.json
        max_questions: Giới hạn số câu (mặc định 5 để tiết kiệm quota)

    Returns:
        Dict chứa kết quả 2 configs và bảng delta.
    """
    print("\n" + "=" * 60)
    print("📊 BẮT ĐẦU SO SÁNH A/B")
    print("   Config A: Hybrid + Rerank (retrieve full pipeline)")
    print("   Config B: Dense-Only (semantic_search only)")
    print(f"   Số câu: {max_questions or len(golden_dataset)}")
    print("=" * 60)

    # Chạy Config A
    result_a = evaluate_with_ragas(
        golden_dataset,
        config_name="hybrid_rerank",
        max_questions=max_questions,
    )

    # Chạy Config B
    result_b = evaluate_with_ragas(
        golden_dataset,
        config_name="dense_only",
        max_questions=max_questions,
    )

    # Tính delta (A - B)
    delta = {}
    metrics = ["faithfulness", "answer_relevancy", "context_recall", "context_precision"]
    for metric in metrics:
        score_a = result_a["avg_scores"].get(metric)
        score_b = result_b["avg_scores"].get(metric)
        if score_a is not None and score_b is not None:
            delta[metric] = score_a - score_b
        else:
            delta[metric] = None

    print(f"\n{'='*60}")
    print(f"📊 KẾT QUẢ SO SÁNH A/B")
    print(f"{'='*60}")
    print(f"{'Metric':<22} {'Config A':>10} {'Config B':>10} {'Δ (A-B)':>10}")
    print(f"{'-'*52}")
    for metric in metrics:
        a = result_a["avg_scores"].get(metric)
        b = result_b["avg_scores"].get(metric)
        d = delta.get(metric)
        a_str = f"{a:.4f}" if a is not None else "N/A"
        b_str = f"{b:.4f}" if b is not None else "N/A"
        d_str = f"{d:+.4f}" if d is not None else "N/A"
        print(f"{metric:<22} {a_str:>10} {b_str:>10} {d_str:>10}")

    return {
        "config_a": result_a,
        "config_b": result_b,
        "delta": delta,
    }


# =============================================================================
# Find Worst Performers
# =============================================================================

def _find_worst_performers(comparison: dict, golden_dataset: list[dict], n: int = 3) -> list[dict]:
    """
    Tìm N câu hỏi có điểm thấp nhất từ Config A (pipeline chính).
    
    Returns:
        List of dicts: [{question, worst_metric, worst_score, failure_stage, root_cause}]
    """
    df_a = comparison["config_a"].get("dataframe")
    if df_a is None:
        return []

    metrics = ["faithfulness", "answer_relevancy", "context_recall", "context_precision"]
    available_metrics = [m for m in metrics if m in df_a.columns]

    if not available_metrics:
        return []

    # Tính điểm trung bình theo hàng (mỗi câu hỏi)
    df_a["avg_score"] = df_a[available_metrics].mean(axis=1)
    worst_indices = df_a.nsmallest(n, "avg_score").index.tolist()

    worst = []
    for idx in worst_indices:
        row = df_a.iloc[idx]
        question = row.get("question", golden_dataset[idx]["question"] if idx < len(golden_dataset) else "N/A")

        # Tìm metric thấp nhất
        min_metric = None
        min_score = 1.0
        for m in available_metrics:
            val = row.get(m)
            if val is not None and val < min_score:
                min_score = val
                min_metric = m

        # Xác định failure stage
        if min_metric in ["context_recall", "context_precision"]:
            failure_stage = "Retrieval"
        else:
            failure_stage = "Generation"

        # Root cause dựa trên metric
        root_cause_map = {
            "faithfulness": "LLM sinh thông tin không bám sát context được retrieve",
            "answer_relevancy": "Câu trả lời không đúng trọng tâm câu hỏi",
            "context_recall": "Retriever không lấy đủ evidence liên quan từ corpus",
            "context_precision": "Context retrieve chứa quá nhiều noise, ít chunk hữu ích",
        }
        root_cause = root_cause_map.get(min_metric, "Không xác định")

        worst.append({
            "question": question if isinstance(question, str) else str(question),
            "worst_metric": min_metric,
            "worst_score": min_score,
            "failure_stage": failure_stage,
            "root_cause": root_cause,
        })

    return worst


# =============================================================================
# Export Results
# =============================================================================

def export_results(comparison: dict, golden_dataset: list[dict]):
    """
    Export kết quả evaluation ra results.md.
    
    Đủ 4 phần bắt buộc:
    1. Bảng điểm 4 metrics × 2 configs + Δ
    2. Mô tả configs
    3. Worst 3 performers
    4. 3 đề xuất cải tiến
    """
    metrics = ["faithfulness", "answer_relevancy", "context_recall", "context_precision"]
    metric_names = {
        "faithfulness": "Faithfulness",
        "answer_relevancy": "Answer Relevancy",
        "context_recall": "Context Recall",
        "context_precision": "Context Precision",
    }

    scores_a = comparison["config_a"]["avg_scores"]
    scores_b = comparison["config_b"]["avg_scores"]
    delta = comparison["delta"]
    num_q = comparison["config_a"]["num_questions"]

    # Worst performers
    worst = _find_worst_performers(comparison, golden_dataset)

    # Tính average
    valid_a = [v for v in scores_a.values() if v is not None]
    valid_b = [v for v in scores_b.values() if v is not None]
    avg_a = sum(valid_a) / len(valid_a) if valid_a else None
    avg_b = sum(valid_b) / len(valid_b) if valid_b else None
    avg_delta = (avg_a - avg_b) if (avg_a is not None and avg_b is not None) else None

    def _fmt(val):
        return f"{val:.4f}" if val is not None else "N/A"

    def _fmt_delta(val):
        return f"{val:+.4f}" if val is not None else "N/A"

    # Build markdown
    lines = []
    lines.append("# RAG Evaluation Results")
    lines.append("")
    lines.append("## Framework sử dụng")
    lines.append("")
    lines.append("> **RAGAS** (Retrieval Augmented Generation Assessment) v0.1.21")
    lines.append(f"> Ngày chạy: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"> Số câu hỏi: {num_q} / {len(golden_dataset)} (golden dataset)")
    lines.append(f"> LLM Judge: `meta-llama/llama-4-scout-17b-16e-instruct:free` qua OpenRouter")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Phần 1: Bảng điểm
    lines.append("## 1. Overall Scores")
    lines.append("")
    lines.append("| Metric | Config A (Hybrid + Rerank) | Config B (Dense-Only) | Δ (A−B) |")
    lines.append("|--------|---------------------------|----------------------|---------|")
    for m in metrics:
        name = metric_names[m]
        a = _fmt(scores_a.get(m))
        b = _fmt(scores_b.get(m))
        d = _fmt_delta(delta.get(m))
        lines.append(f"| {name} | {a} | {b} | {d} |")
    lines.append(f"| **Average** | **{_fmt(avg_a)}** | **{_fmt(avg_b)}** | **{_fmt_delta(avg_delta)}** |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Phần 2: Mô tả configs
    lines.append("## 2. A/B Comparison — Mô Tả Configs")
    lines.append("")
    lines.append("**Config A — Hybrid + Rerank (Full Pipeline):**")
    lines.append("> Gọi `retrieve(query, use_reranking=True)` → Semantic Search (Task 5) + Lexical BM25 (Task 6) → RRF Rerank (Task 7) → Fallback PageIndex (Task 8) nếu cosine < threshold → `generate_with_citation()` (Task 10).")
    lines.append("")
    lines.append("**Config B — Dense-Only:**")
    lines.append("> Gọi trực tiếp `semantic_search(query, top_k=5)` → chỉ dùng embedding cosine similarity, không BM25, không rerank, không fallback → gọi LLM sinh câu trả lời.")
    lines.append("")
    lines.append("**Kết luận:**")
    if avg_delta is not None and avg_delta > 0:
        lines.append(f"> Config A (Hybrid + Rerank) **tốt hơn** Config B trung bình **{avg_delta:+.4f}** điểm. Hybrid search kết hợp BM25 giúp bắt chính xác số hiệu văn bản (\"Điều 87\", \"Nghị định 52\") mà dense search hay trượt. RRF reranking cân bằng kết quả từ 2 phương pháp.")
    elif avg_delta is not None and avg_delta < 0:
        lines.append(f"> Config B (Dense-Only) **tốt hơn** Config A trung bình **{abs(avg_delta):.4f}** điểm. Cần điều tra thêm vì sao hybrid search không cải thiện.")
    else:
        lines.append("> Chưa có đủ dữ liệu để kết luận. Cần chạy lại với đủ quota.")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Phần 3: Worst 3
    lines.append("## 3. Worst Performers (Bottom 3)")
    lines.append("")
    if worst:
        lines.append("| # | Câu hỏi | Metric thấp nhất | Score | Failure Stage | Root Cause |")
        lines.append("|---|---------|-----------------|-------|---------------|------------|")
        for i, w in enumerate(worst):
            q_short = w["question"][:50] + "..." if len(w["question"]) > 50 else w["question"]
            lines.append(
                f"| {i+1} | {q_short} | {w['worst_metric']} | {w['worst_score']:.4f} | {w['failure_stage']} | {w['root_cause']} |"
            )
    else:
        lines.append("*Chưa có dữ liệu — cần chạy evaluation thành công trước.*")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Phần 4: Đề xuất
    lines.append("## 4. Recommendations — Đề Xuất Cải Tiến")
    lines.append("")
    lines.append("### Đề xuất 1: Tăng chunk overlap và dùng MarkdownHeaderTextSplitter")
    lines.append("**Action:** Tăng `CHUNK_OVERLAP` từ 100 → 200, kết hợp `MarkdownHeaderTextSplitter` tách theo Điều/Khoản trước khi chia nhỏ bằng `RecursiveCharacterTextSplitter`.")
    lines.append("**Expected impact:** Giảm trường hợp điều khoản bị cắt đôi giữa 2 chunk, tăng Context Recall ~10-15% cho câu hỏi pháp lý cần nguyên Điều.")
    lines.append("")
    lines.append("### Đề xuất 2: Thêm Query Expansion")
    lines.append("**Action:** Dùng LLM sinh 2-3 biến thể câu hỏi (đồng nghĩa, formal/informal), search riêng từng biến thể rồi gộp bằng RRF.")
    lines.append("**Expected impact:** Tăng Recall cho câu hỏi dùng từ ngữ đời thường (\"bán TikTok bao nhiêu đóng thuế\") khác xa văn phong luật (\"doanh thu từ hoạt động sản xuất kinh doanh\").")
    lines.append("")
    lines.append("### Đề xuất 3: Parse legal_ref chính xác hơn cho citation")
    lines.append("**Action:** Dùng regex phức tạp hơn để bắt \"Khoản X Điều Y\" thay vì chỉ \"Điều Y\". Chèn `legal_ref` nổi bật vào context gửi cho LLM.")
    lines.append("**Expected impact:** Citation chính xác hơn dạng `[Nghị định 01/2021/NĐ-CP, Khoản 1 Điều 87]`, tăng Faithfulness ~5-10%.")
    lines.append("")

    # Ghi file
    content = "\n".join(lines)
    RESULTS_PATH.write_text(content, encoding="utf-8")
    print(f"\n📝 Đã xuất kết quả ra: {RESULTS_PATH}")


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    golden_dataset = load_golden_dataset()
    print(f"✅ Loaded {len(golden_dataset)} test cases từ golden_dataset.json")

    # Kiểm tra API key
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("❌ OPENROUTER_API_KEY chưa có trong .env!")
        print("   Vui lòng tạo file .env và điền: OPENROUTER_API_KEY=sk-or-v1-...")
        exit(1)

    print(f"🔑 API Key: {api_key[:12]}...")

    # Chạy A/B comparison
    # ⚠ Mặc định chỉ 5 câu để tiết kiệm quota (50 req/ngày)
    # Đổi max_questions=None để chạy hết 15+ câu nếu đủ quota
    MAX_QUESTIONS = 5

    print(f"\n📊 Sẽ chạy {MAX_QUESTIONS} câu (tiết kiệm quota).")
    print(f"   Đổi MAX_QUESTIONS = None trong code để chạy hết {len(golden_dataset)} câu.\n")

    comparison = compare_configs(golden_dataset, max_questions=MAX_QUESTIONS)

    # Export kết quả
    export_results(comparison, golden_dataset)

    print("\n" + "=" * 60)
    print("🎉 HOÀN THÀNH! Kiểm tra file: group_project/evaluation/results.md")
    print("=" * 60)
