"""
Task 9 — Retrieval Pipeline hoàn chỉnh.

    Query
      ├─ chuẩn hoá (bung viết tắt: TNCN → thu nhập cá nhân)
      ├─ nếu câu hỏi NÊU SỐ HIỆU → tra thẳng theo doc_id, GHIM lên đầu
      ├─ Semantic Search  → dense_results   (giữ điểm cosine GỐC)
      ├─ Lexical Search   → sparse_results
      ├─ Merge bằng RRF → Rerank
      └─ nếu cosine gốc tốt nhất < threshold → fallback vectorless

BỐN QUYẾT ĐỊNH QUAN TRỌNG, mỗi cái đều có bằng chứng đo được
============================================================

1. THRESHOLD SO VỚI COSINE GỐC, KHÔNG PHẢI ĐIỂM RRF
   Điểm RRF sau khi fuse CHỈ phụ thuộc thứ hạng: top-1 luôn ≈ 1/(60+1) ≈ 0,0164
   bất kể nội dung có liên quan hay không. So threshold với nó thì fallback gần
   như không bao giờ chạy, kể cả với câu hoàn toàn lạc đề.

2. SCORE_THRESHOLD = 0.85, KHÔNG PHẢI 0.48
   Con số 0.48 trong LAB_GUIDE.md tính cho model khác. Đo thật trên corpus này
   với `multilingual-e5-small` (xem DATA_REPORT.md mục 5):
       câu liên quan : 0,882 – 0,923
       câu lạc đề    : 0,815 – 0,828
   Dùng 0.48 thì mọi câu đều vượt ngưỡng → fallback chết hẳn.

3. TRA KHOÁ KHÔNG PHẢI BÀI TOÁN XẾP HẠNG
   Khi câu hỏi nêu đích danh "Nghị định 52/2013/NĐ-CP", kết quả tra theo doc_id
   phải được GHIM lên đầu, không thả vào rổ RRF. P-185 đo được hai lần hỏng cùng
   kiểu: đáp án đúng bị RRF đẩy xuống hạng 6 rồi bị top_k=5 cắt mất.

4. KHỬ TRÙNG THEO provision_id, KHÔNG THEO content
   Một Điều dài bị cắt thành nhiều chunk; khử theo content thì chúng vẫn là các
   kết quả riêng và chiếm hết top_k.

Chạy:  python -m src.task9_retrieval_pipeline
"""

from __future__ import annotations

from .legal_utils import extract_doc_id, normalize_query
from .task5_semantic_search import semantic_search
from .task6_lexical_search import lexical_search
from .task7_reranking import rerank, rerank_rrf
from .task8_pageindex_vectorless import pageindex_search

# =============================================================================
# CONFIGURATION
# =============================================================================

# Đo được: liên quan 0,882–0,923 · lạc đề 0,815–0,828 → lấy giữa hai cụm.
# Đổi embedding model thì PHẢI đo lại, dải điểm mỗi model một khác.
SCORE_THRESHOLD = 0.85
DEFAULT_TOP_K = 5
RERANK_METHOD = "rrf"


def _goi_an_toan(fn, *args, **kwargs) -> list[dict]:
    """Gọi một nhánh retrieval, trả [] nếu nhánh đó chưa implement hoặc lỗi.

    Có chủ đích: pipeline phải chạy được khi một nhánh còn dang dở (nhiều người
    làm song song), thay vì kéo sập cả hệ thống. Mỗi lần suy giảm đều IN RA —
    suy giảm im lặng còn tệ hơn crash vì không ai biết mà sửa.
    """
    try:
        return fn(*args, **kwargs) or []
    except NotImplementedError:
        print(f"  ⚠ {fn.__module__}.{fn.__name__} chưa implement — bỏ qua nhánh này")
        return []
    except Exception as e:
        print(f"  ⚠ {fn.__module__}.{fn.__name__} lỗi: {type(e).__name__}: {e}")
        return []


def _khoa(item: dict) -> str:
    """Khoá khử trùng: ưu tiên provision_id, không có thì dùng content."""
    return (item.get("metadata") or {}).get("provision_id") or item.get("content", "")[:160]


def _chuan_hoa_diem(items: list[dict]) -> list[dict]:
    """Đưa điểm về [0,1] để ba nhánh so sánh được với nhau trên giao diện.

    Mỗi nhánh trả điểm ở thang khác hẳn: cosine [0,1], RRF ≈0,016, còn vectorless
    là điểm trùng từ khoá thô (có thể 48,0). Hiển thị lẫn lộn thì người xem tưởng
    hệ thống hỏng. Chuẩn hoá theo max của chính danh sách — thứ hạng giữ nguyên,
    chỉ đổi cách đọc.
    """
    if not items:
        return items
    cao_nhat = max((it.get("score") or 0) for it in items)
    if cao_nhat > 0:
        for it in items:
            it["score"] = round((it.get("score") or 0) / cao_nhat, 4)
    return items


def _tra_theo_doc_id(doc_id: str, query: str, top_k: int) -> list[dict]:
    """Tra thẳng ChromaDB theo metadata doc_id — nhánh 'tra khoá'.

    Trả [] nếu chưa index hoặc không có văn bản đó, để pipeline đi tiếp bình
    thường chứ không chết.
    """
    try:
        from .task4_chunking_indexing import embed_query, get_collection

        res = get_collection().query(
            query_embeddings=[embed_query(query)],
            n_results=top_k,
            where={"doc_id": doc_id},
            include=["documents", "metadatas", "distances"],
        )
        if not res["documents"] or not res["documents"][0]:
            return []
        return [
            {
                "content": doc,
                "score": round(max(0.0, 1.0 - dist), 4),
                "metadata": meta,
                "source": "hybrid",
            }
            for doc, meta, dist in zip(
                res["documents"][0], res["metadatas"][0], res["distances"][0]
            )
        ]
    except Exception as e:
        print(f"  ⚠ tra theo doc_id thất bại: {type(e).__name__}: {e}")
        return []


def retrieve(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    score_threshold: float = SCORE_THRESHOLD,
    use_reranking: bool = True,
) -> list[dict]:
    """
    Returns:
        List of {'content', 'score', 'metadata', 'source'} với
        source ∈ {'hybrid', 'pageindex'}, tối đa `top_k` phần tử.
    """
    q = normalize_query(query)

    # ── Nhánh tra khoá: câu hỏi nêu đích danh số hiệu văn bản ──────────────
    ghim: list[dict] = []
    doc_id = extract_doc_id(query)
    if doc_id:
        ghim = _tra_theo_doc_id(doc_id, q, top_k)
        if ghim:
            print(f"  → tra khoá {doc_id}: {len(ghim)} kết quả, ghim lên đầu")

    # ── Hai nhánh hybrid ───────────────────────────────────────────────────
    dense = _goi_an_toan(semantic_search, q, top_k=top_k * 2)
    sparse = _goi_an_toan(lexical_search, q, top_k=top_k * 2)

    # ── Merge bằng RRF ─────────────────────────────────────────────────────
    danh_sach = [ds for ds in (dense, sparse) if ds]
    merged: list[dict] = []
    if danh_sach:
        merged = _goi_an_toan(rerank_rrf, danh_sach, top_k=top_k * 2) or [
            it for ds in danh_sach for it in ds
        ]
    for it in merged:
        it["source"] = "hybrid"

    # Ghim đứng trước, phần còn lại nối sau, khử trùng theo provision_id
    da_co = {_khoa(it) for it in ghim}
    ket_hop = list(ghim)
    for it in merged:
        k = _khoa(it)
        if k not in da_co:
            da_co.add(k)
            ket_hop.append(it)

    # ── Rerank ─────────────────────────────────────────────────────────────
    final = ket_hop
    if use_reranking and ket_hop:
        rr = _goi_an_toan(rerank, query, ket_hop, top_k=top_k, method=RERANK_METHOD)
        if rr:
            # Rerank không được làm mất phần ghim: nếu nó đánh rơi thì ghép lại.
            khoa_rr = {_khoa(x) for x in rr}
            final = [g for g in ghim if _khoa(g) not in khoa_rr] + rr

    # ── Fallback: SO VỚI COSINE GỐC của semantic_search, KHÔNG phải điểm RRF ─
    best = dense[0]["score"] if dense else 0.0
    if not ghim and best < score_threshold:
        print(f"  ⚠ cosine gốc tốt nhất {best:.3f} < ngưỡng {score_threshold} → fallback vectorless")
        fb = _goi_an_toan(pageindex_search, query, top_k=top_k)
        if fb:
            for it in fb:
                it.setdefault("source", "pageindex")
            return fb[:top_k]

    for it in final:
        it.setdefault("source", "hybrid")
    return final[:top_k]


if __name__ == "__main__":
    test_queries = [
        "Vốn điều lệ của công ty cổ phần được quy định thế nào?",
        "Hàng hoá nào bị cấm đăng bán trên sàn thương mại điện tử?",
        "Điều 35 Nghị định 52/2013/NĐ-CP quy định gì?",   # nêu số hiệu → tra khoá
        "Bán trên TikTok Shop bao nhiêu thì nộp thuế TNCN và GTGT?",  # bung viết tắt
        "xyzabc123nonsense",                               # lạc đề → fallback
    ]
    for q in test_queries:
        print(f"\n{'='*70}\nQuery: {q}")
        print(f"  chuẩn hoá → {normalize_query(q)}")
        print("-" * 70)
        for i, r in enumerate(retrieve(q, top_k=3), 1):
            m = r.get("metadata", {})
            print(f"  {i}. [{r['score']:.3f}] [{r['source']}] "
                  f"{m.get('doc_title', '?')[:36]} {m.get('legal_ref', '')}")
            print(f"     {r['content'][:90].replace(chr(10), ' ')}")
