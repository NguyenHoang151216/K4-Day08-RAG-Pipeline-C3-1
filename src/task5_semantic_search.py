"""
Task 5 — Semantic Search Module.

Viết module tìm kiếm ngữ nghĩa (dense retrieval) trên vector store.

Yêu cầu:
    - Input: query string + top_k
    - Output: danh sách chunks có score, sorted descending
    - Phải tương thích với embedding model và vector store ở Task 4
"""

import os


HYDE_MODEL = "openai/gpt-oss-20b:free"
HYDE_SYSTEM_PROMPT = """Bạn là chuyên gia về thương mại điện tử và pháp luật Việt Nam.
Từ câu hỏi của người dùng, hãy viết một đoạn tài liệu giả định có khả năng chứa câu
trả lời. Đoạn văn cần ngắn gọn, giàu từ khóa liên quan và viết bằng tiếng Việt.
Không nhắc rằng đây là câu trả lời giả định, không thêm tiêu đề hay giải thích."""


def _open_index():
    """Trả collection đã index hoặc ``None`` nếu Task 4 chưa chạy."""
    from .task4_chunking_indexing import get_collection

    try:
        collection = get_collection()
        return collection if collection.count() > 0 else None
    except Exception as exc:
        message = str(exc).lower()
        if "does not exist" in message or "not found" in message:
            return None
        raise


def _query_collection(collection, embedding, top_k: int) -> list[dict]:
    """Query Chroma và chuẩn hóa kết quả về contract chung của Task 5."""
    results = collection.query(
        query_embeddings=[embedding],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )
    output = []
    for document, metadata, distance in zip(
        results.get("documents", [[]])[0],
        results.get("metadatas", [[]])[0],
        results.get("distances", [[]])[0],
    ):
        score = min(1.0, max(0.0, 1.0 - float(distance)))
        output.append({
            "content": document or "",
            "score": round(score, 4),
            "metadata": metadata or {},
        })
    return sorted(output, key=lambda item: item["score"], reverse=True)[:top_k]


def semantic_search(query: str, top_k: int = 10) -> list[dict]:
    """
    Tìm kiếm ngữ nghĩa sử dụng vector similarity.

    Args:
        query: Câu truy vấn
        top_k: Số lượng kết quả tối đa

    Returns:
        List of {
            'content': str,      # Nội dung chunk
            'score': float,      # Cosine similarity score
            'metadata': dict     # source, doc_type, chunk_index
        }
        Sorted by score descending.
    """
    if not isinstance(query, str) or not query.strip() or top_k <= 0:
        return []

    # Qua embed_query() chứ KHÔNG gọi .encode() trực tiếp: model E5 cần tiền tố
    # "query: ", thiếu nó thì điểm cosine tụt mà KHÔNG có triệu chứng nào.
    # embed_query() tự bật/tắt tiền tố theo tên model nên đổi model vẫn đúng.
    from .task4_chunking_indexing import embed_query

    collection = _open_index()
    if collection is None:
        return []

    query_vector = embed_query(query.strip())
    return _query_collection(collection, query_vector, top_k)


def semantic_search_hyde(query: str, top_k: int = 10) -> list[dict]:
    """Tìm kiếm bằng Hypothetical Document Embeddings (HyDE).

    Khác với :func:`semantic_search`, hàm này nhờ LLM viết một đoạn tài liệu
    giả định có thể trả lời ``query``, rồi embed đoạn văn đó để tìm chunk thật
    gần nhất trong ChromaDB. LLM chỉ hỗ trợ tạo truy vấn; nội dung trả về luôn
    lấy từ vector store.

    Raises:
        RuntimeError: Khi thiếu API key hoặc OpenRouter không sinh được tài liệu.
    """
    if not isinstance(query, str) or not query.strip() or top_k <= 0:
        return []

    # HyDE embed một đoạn TÀI LIỆU giả định, nên dùng embed_passages() với tiền
    # tố "passage: " cho khớp cách các chunk trong index được nhúng — không phải
    # embed_query(). Nhầm hai cái này làm lệch không gian vector.
    from .task4_chunking_indexing import embed_passages

    collection = _open_index()
    if collection is None:
        return []

    hypothetical_document = _generate_hypothetical_doc(query.strip())
    vector = embed_passages([hypothetical_document])[0]
    return _query_collection(collection, vector, top_k)


def _generate_hypothetical_doc(query: str) -> str:
    """Sinh tài liệu giả định cho HyDE bằng OpenRouter."""
    from dotenv import load_dotenv
    from openai import OpenAI

    load_dotenv()
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Thiếu OPENROUTER_API_KEY. Hãy cấu hình key trong file .env để chạy HyDE."
        )

    client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
    try:
        response = client.chat.completions.create(
            model=os.getenv("OPENROUTER_MODEL", HYDE_MODEL),
            messages=[
                {"role": "system", "content": HYDE_SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
            temperature=0.2,
            max_tokens=250,
        )
        hypothetical_document = (response.choices[0].message.content or "").strip()
    except Exception as exc:
        raise RuntimeError(f"Không thể sinh tài liệu HyDE từ OpenRouter: {exc}") from exc

    if not hypothetical_document:
        raise RuntimeError("OpenRouter trả về tài liệu HyDE rỗng")
    return hypothetical_document


if __name__ == "__main__":
    # Test
    results = semantic_search("quy định trả hàng hoàn tiền shopee", top_k=5)
    for r in results:
        print(f"[{r['score']:.3f}] {r['content'][:100]}...")
