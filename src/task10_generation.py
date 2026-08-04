"""
Task 10 — Generation Có Citation qua Groq.

Hướng dẫn:
    1. Chọn top_k, top_p phù hợp (giải thích lý do)
    2. Sắp xếp lại chunks sau reranking để tránh "lost in the middle"
    3. Inject context vào prompt
    4. Yêu cầu LLM trả lời có citation
    5. Nếu không đủ evidence → "I cannot verify this information"

Groq cung cấp API tương thích OpenAI SDK.
Base URL: "https://api.groq.com/openai/v1".
"""

import os

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()


def retrieve(query: str, top_k: int = 5) -> list[dict]:
    """Lazy proxy to avoid loading the retrieval stack until generation is used."""
    from .task9_retrieval_pipeline import retrieve as retrieve_chunks

    return retrieve_chunks(query, top_k=top_k)


# =============================================================================
# CONFIGURATION — Giải thích lựa chọn
# =============================================================================

# top_k: Số chunks đưa vào context
# Chọn 5 vì: đủ evidence mà không quá dài gây lost in the middle
TOP_K = 5

# top_p (nucleus sampling): Xác suất tích luỹ cho token generation
# Chọn 0.9 vì: đủ diverse nhưng không quá random
TOP_P = 0.9

# temperature: Độ ngẫu nhiên của output
# Chọn 0.3 vì: RAG cần factual, ít sáng tạo
TEMPERATURE = 0.3

LLM_MODEL = "openai/gpt-oss-120b"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"


# =============================================================================
# SYSTEM PROMPT
# =============================================================================

SYSTEM_PROMPT = """Bạn là Trợ lý Pháp lý Khởi nghiệp & Thương mại điện tử. Bạn hỗ trợ
tra cứu quy định về doanh nghiệp, hộ kinh doanh, thuế và bán hàng trên sàn TMĐT.

Quy tắc bắt buộc:
1. Chỉ sử dụng thông tin từ context được cung cấp — KHÔNG bịa đặt
2. Mỗi khẳng định phải có trích dẫn ngay sau. Dùng đúng nhãn Citation được
   cung cấp trong context, ví dụ: [Nghị định 01/2021/NĐ-CP, Điều 87]
3. Nếu context không đủ thông tin → trả lời: "Tôi không thể xác minh thông tin này từ nguồn hiện có"
4. Trả lời bằng tiếng Việt, có cấu trúc rõ ràng theo đoạn văn
5. Không suy luận hay mở rộng ngoài những gì được nêu trong context"""


# =============================================================================
# DOCUMENT REORDERING (tránh lost in the middle)
# =============================================================================

def reorder_for_llm(chunks: list[dict]) -> list[dict]:
    """
    Sắp xếp chunks để tránh "lost in the middle" effect.

    LLM nhớ tốt thông tin ở ĐẦU và CUỐI prompt, quên thông tin ở GIỮA.
    Strategy: đặt chunks quan trọng nhất ở đầu và cuối, kém quan trọng ở giữa.

    Input order (by score):  [1, 2, 3, 4, 5]
    Output order:            [1, 3, 5, 4, 2]
    (best first, worst in middle, second-best last)

    Args:
        chunks: List sorted by score descending (from retrieval)

    Returns:
        List reordered để maximize LLM attention.
    """
    if len(chunks) <= 2:
        return list(chunks)

    front = chunks[::2]
    back = chunks[1::2]
    return front + back[::-1]


# =============================================================================
# CONTEXT FORMATTING
# =============================================================================

def format_context(chunks: list[dict]) -> str:
    """
    Format chunks thành context string cho prompt.
    Mỗi chunk có label source để LLM có thể cite.

    Args:
        chunks: List of {'content': str, 'metadata': dict, 'score': float}

    Returns:
        Formatted context string.
    """
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        metadata = chunk.get("metadata") or {}
        source = metadata.get("source") or chunk.get("source") or f"Source {i}"
        doc_type = metadata.get("type", "unknown")
        doc_title = metadata.get("doc_title") or source
        legal_ref = metadata.get("legal_ref")
        citation = f"{doc_title}, {legal_ref}" if legal_ref else str(doc_title)
        content = str(chunk.get("content") or "").strip()

        context_parts.append(
            f"[Document {i}]\n"
            f"Source: {source}\n"
            f"Type: {doc_type}\n"
            f"Citation: [{citation}]\n"
            f"Content:\n{content}"
        )
    return "\n\n---\n\n".join(context_parts)


# =============================================================================
# GENERATION
# =============================================================================

def generate_with_citation(query: str, top_k: int = TOP_K) -> dict:
    """
    End-to-end RAG generation có citation.

    Pipeline:
        1. Retrieve relevant chunks
        2. Reorder để tránh lost in the middle
        3. Format context với source labels
        4. Build prompt (system + context + query)
        5. Call LLM
        6. Return answer + sources

    Args:
        query: Câu hỏi của user

    Returns:
        {
            'answer': str,           # Câu trả lời có citation
            'sources': list[dict],   # Các chunks đã dùng
            'retrieval_source': str  # 'hybrid' hoặc 'pageindex'
        }
    """
    query = query.strip() if isinstance(query, str) else ""
    if not query:
        return {
            "answer": "Vui lòng nhập câu hỏi cần tra cứu.",
            "sources": [],
            "retrieval_source": "none",
        }

    chunks = retrieve(query, top_k=top_k)
    retrieval_source = chunks[0].get("source", "hybrid") if chunks else "none"
    if not chunks:
        return {
            "answer": "Tôi không thể xác minh thông tin này từ nguồn hiện có.",
            "sources": [],
            "retrieval_source": retrieval_source,
        }

    reordered = reorder_for_llm(chunks)
    context = format_context(reordered)
    user_message = (
        "Hãy trả lời câu hỏi chỉ dựa trên context giữa các thẻ dưới đây.\n\n"
        f"<context>\n{context}\n</context>\n\n"
        f"Câu hỏi: {query}"
    )

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return {
            "answer": (
                "Chưa cấu hình GROQ_API_KEY. Hãy thêm khóa API Groq vào file .env."
            ),
            "sources": chunks,
            "retrieval_source": retrieval_source,
        }

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=GROQ_BASE_URL)
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=TEMPERATURE,
            top_p=TOP_P,
        )
        answer = response.choices[0].message.content
        if not answer:
            answer = "Groq không trả về nội dung. Vui lòng thử lại."
    except Exception as exc:
        answer = f"Không thể tạo câu trả lời từ Groq: {exc}"

    return {
        "answer": answer,
        "sources": chunks,
        "retrieval_source": retrieval_source,
    }


if __name__ == "__main__":
    test_queries = [
        "Bán hàng online có phải nộp thuế TNCN và GTGT không?",
        "Hồ sơ đăng ký hộ kinh doanh gồm những gì?",
        "Công ty TNHH cần thực hiện thủ tục thành lập nào?",
    ]

    for q in test_queries:
        print(f"\n{'='*70}")
        print(f"Q: {q}")
        print("=" * 70)
        result = generate_with_citation(q)
        print(f"\nA: {result['answer']}")
        print(f"\n[Sources: {len(result['sources'])} chunks | via {result['retrieval_source']}]")
