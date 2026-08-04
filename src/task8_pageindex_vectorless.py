"""
Task 8 — PageIndex Vectorless RAG.

Đăng ký tài khoản tại: https://pageindex.ai/
SDK & sample code: https://github.com/VectifyAI/PageIndex

PageIndex cho phép RAG mà không cần vector store — sử dụng
structural understanding của document thay vì embedding.

Cài đặt:
    pip install pageindex

Hướng dẫn:
    1. Đăng ký account tại pageindex.ai
    2. Lấy API key
    3. Upload documents
    4. Query sử dụng PageIndex API

Lưu ý: API `/retrieval` của PageIndex hiện đã deprecated (vẫn hoạt động, nhưng response
có field "deprecation" cảnh báo) và trả kết quả trong "retrieved_nodes" — mỗi node có
"relevant_contents": list[list[{section_title, relevant_content}]]. In response thật ra
(json.dumps(...)) trước khi viết logic parse, đừng đoán schema từ ví dụ code cũ.
"""

import os
import re
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PAGEINDEX_API_KEY = os.getenv("PAGEINDEX_API_KEY", "")
STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"

_HEADING_RE = re.compile(r"^(#{1,3})\s+(.*)$", re.MULTILINE)

# Văn bản pháp luật VN dùng "Điều N." làm đơn vị cấu trúc thay cho heading
# markdown (corpus hiện tại có ~400 "Điều" nhưng 0 heading #). Đây chính là
# ranh giới section tự nhiên cho vectorless retrieval trên domain này.
_DIEU_RE = re.compile(r"(?m)^\s*(Điều\s+\d+[a-z]?\s*\.?[^\n]{0,120})")

_MAX_SECTION_CHARS = 4000


def _split_into_sections(text: str, source: str) -> list[dict]:
    """
    Cắt 1 document thành các section theo cấu trúc.

    Ưu tiên heading markdown (#, ##, ###); nếu document không có heading —
    trường hợp của văn bản luật đã convert — thì cắt theo mốc "Điều N".
    """
    headings = list(_HEADING_RE.finditer(text))
    if headings:
        boundaries = [(m.start(), m.end(), m.group(2).strip()) for m in headings]
    else:
        dieu = list(_DIEU_RE.finditer(text))
        boundaries = [(m.start(), m.end(), m.group(1).strip()) for m in dieu]

    def emit(title: str, content: str) -> list[dict]:
        # Chia nhỏ section quá dài thay vì cắt cụt — không làm mất nội dung.
        return [
            {"title": title, "content": content[i:i + _MAX_SECTION_CHARS], "source": source}
            for i in range(0, len(content), _MAX_SECTION_CHARS)
        ]

    if not boundaries:
        return emit(source, text)

    sections = []
    for i, (start, _end_of_title, title) in enumerate(boundaries):
        end = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(text)
        content = text[start:end].strip()
        if content:
            sections.extend(emit(title, content))
    return sections


def _load_sections() -> list[dict]:
    sections = []
    for md_file in STANDARDIZED_DIR.rglob("*.md"):
        text = md_file.read_text(encoding="utf-8")
        sections.extend(_split_into_sections(text, md_file.name))
    return sections


def _keyword_score(query_terms: list[str], title: str, content: str) -> float:
    title_terms = re.findall(r"\w+", title.lower())
    content_terms = re.findall(r"\w+", content.lower())
    score = 0.0
    for term in query_terms:
        score += 2.0 * title_terms.count(term)
        score += 1.0 * content_terms.count(term)
    return score


def _local_vectorless_search(query: str, top_k: int = 5) -> list[dict]:
    """
    Local implementation of vectorless structural retrieval
    (PageIndex-compatible interface). Không dùng embedding/vector store.

    Cắt document theo heading markdown thành section, chấm điểm mỗi section
    bằng độ trùng từ khoá (tiêu đề nhân hệ số 2 + nội dung), trả nguyên
    section (không chunk nhỏ hơn).
    """
    sections = _load_sections()
    if not sections:
        return []

    query_terms = re.findall(r"\w+", query.lower())
    scored = []
    for sec in sections:
        score = _keyword_score(query_terms, sec["title"], sec["content"])
        if score > 0:
            scored.append((score, sec))

    scored.sort(key=lambda x: x[0], reverse=True)

    return [
        {
            "content": sec["content"],
            "score": score,
            "metadata": {"section": sec["title"], "source": sec["source"]},
            "source": "pageindex",
        }
        for score, sec in scored[:top_k]
    ]


def upload_documents():
    """
    Upload toàn bộ markdown documents lên PageIndex.
    """
    # TODO: Implement upload
    #
    # Tham khảo: https://github.com/VectifyAI/PageIndex
    #
    # from pageindex.client import PageIndexClient
    #
    # client = PageIndexClient(api_key=PAGEINDEX_API_KEY)
    #
    # for md_file in STANDARDIZED_DIR.rglob("*.md"):
    #     # Lưu ý: PageIndex nhận PDF, không nhận .md trực tiếp — có thể cần
    #     # convert markdown sang PDF đơn giản bằng fpdf2 trước khi upload.
    #     resp = client.submit_document(str(pdf_path))
    #     doc_id = resp.get("doc_id") or resp.get("id")
    #     print(f"  ✓ Uploaded: {md_file.name} -> {doc_id}")
    raise NotImplementedError("Implement upload_documents")


def pageindex_search(query: str, top_k: int = 5) -> list[dict]:
    """
    Vectorless retrieval sử dụng PageIndex.
    Dùng làm fallback khi hybrid search không có kết quả tốt.

    Args:
        query: Câu truy vấn
        top_k: Số lượng kết quả tối đa

    Returns:
        List of {
            'content': str,
            'score': float,
            'metadata': dict,
            'source': 'pageindex'   # Đánh dấu nguồn retrieval
        }
    """
    if not PAGEINDEX_API_KEY:
        # Không có API key -> local vectorless retriever (Plan B).
        # Phải trả [] thay vì raise: Task 9 gọi hàm này làm fallback khi
        # cosine score thấp, kể cả khi chưa có data/standardized/.
        try:
            return _local_vectorless_search(query, top_k)
        except Exception:
            return []

    from pageindex.client import PageIndexClient

    client = PageIndexClient(api_key=PAGEINDEX_API_KEY)
    resp = client.submit_query(doc_id=doc_id, query=query)
    retrieval_id = resp.get("retrieval_id") or resp.get("id")

    retrieval = client.get_retrieval(retrieval_id)

    results = []
    for rank, node in enumerate(retrieval.get("retrieved_nodes", [])[:2], 1):
        for group in node.get("relevant_contents", []):
            for item in group:
                results.append({
                    "content": item.get("relevant_content", ""),
                    "score": 1.0 / rank,
                    "metadata": {"section": item.get("section_title")},
                    "source": "pageindex",
                })
    return results[:top_k]


if __name__ == "__main__":
    if not PAGEINDEX_API_KEY:
        print("⚠ Hãy set PAGEINDEX_API_KEY trong file .env")
        print("  Đăng ký tại: https://pageindex.ai/")
    else:
        print("Uploading documents...")
        upload_documents()

        print("\nTest query:")
        results = pageindex_search("danh sách sản phẩm cấm đăng bán", top_k=3)
        for r in results:
            print(f"[{r['score']:.3f}] {r['content'][:100]}...")
