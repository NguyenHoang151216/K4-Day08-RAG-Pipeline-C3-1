"""
Task 6 — Lexical Search Module (BM25).

Mặc định sử dụng BM25. Nếu dùng phương pháp khác (TF-IDF, Elasticsearch,
Weaviate BM25 built-in), hãy giải thích cơ chế trong buổi demo → +5 bonus.

Cài đặt:
    pip install rank-bm25

BM25 hoạt động thế nào:
    - Term Frequency (TF): từ xuất hiện nhiều trong document → điểm cao
    - Inverse Document Frequency (IDF): từ hiếm → quan trọng hơn
    - Document length normalization: document dài không bị ưu tiên quá mức
    - Formula: score(q,d) = Σ IDF(qi) * (tf(qi,d) * (k1+1)) / (tf(qi,d) + k1*(1-b+b*|d|/avgdl))
    - k1=1.5 (term saturation), b=0.75 (length normalization)
"""

import re
from pathlib import Path

STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"

# Lazy cache — nạp 1 lần khi lexical_search() được gọi lần đầu.
# KHÔNG load ở module level: import src.task9 phải chạy được kể cả khi
# data/standardized/ chưa tồn tại trên máy đồng đội.
_CORPUS: list[dict] | None = None
_BM25_INDEX = None


_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)

# Văn bản pháp luật VN dùng "Điều N" làm đơn vị cấu trúc (corpus hiện tại có
# ~400 "Điều" nhưng 0 heading markdown). Index cả file như 1 document làm BM25
# vô dụng: length-normalization pha loãng điểm và corpus chỉ còn 4 doc nên IDF
# mất ý nghĩa. Cắt theo Điều vừa cho điểm chuẩn, vừa cho legal_ref để citation.
_DIEU_RE = re.compile(r"(?m)^\s*(Điều\s+\d+[a-z]?)")

_MAX_CHUNK_CHARS = 4000


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower())


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Tách frontmatter YAML (doc_title, doc_number, type...) khỏi phần nội dung."""
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    meta = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            value = value.strip()
            if value:
                meta[key.strip()] = value
    return meta, text[match.end():]


def _cap(legal_ref: str, chunk: str) -> list[tuple[str, str]]:
    """Chia nhỏ chunk quá dài thay vì cắt cụt — không được làm mất nội dung."""
    return [
        (legal_ref, chunk[i:i + _MAX_CHUNK_CHARS])
        for i in range(0, len(chunk), _MAX_CHUNK_CHARS)
    ]


def _split_by_dieu(text: str) -> list[tuple[str, str]]:
    """Cắt document theo mốc 'Điều N'. Trả list (legal_ref, chunk_text)."""
    marks = list(_DIEU_RE.finditer(text))
    if not marks:
        return _cap("", text)

    chunks = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        chunk = text[m.start():end].strip()
        if chunk:
            chunks.extend(_cap(m.group(1).strip(), chunk))
    return chunks


def _load_corpus() -> list[dict]:
    """
    Đọc data/standardized/**/*.md, cắt theo Điều thành corpus cho BM25.

    Metadata theo schema chốt ở Task 4 để Task 10 cite được dạng
    [Nghị định 52/2013/NĐ-CP, Điều 26].
    """
    corpus = []
    for md_file in STANDARDIZED_DIR.rglob("*.md"):
        raw = md_file.read_text(encoding="utf-8")
        meta, body = _parse_frontmatter(raw)
        doc_title = meta.get("doc_title", md_file.stem)
        doc_type = meta.get("type", "legal" if "legal" in md_file.parts else "news")

        for idx, (legal_ref, chunk) in enumerate(_split_by_dieu(body)):
            corpus.append({
                "content": chunk,
                "metadata": {
                    "source": md_file.name,
                    "type": doc_type,
                    "chunk_index": idx,
                    "doc_title": doc_title,
                    "legal_ref": legal_ref,
                },
            })
    return corpus


def build_bm25_index(corpus: list[dict]):
    """
    Xây dựng BM25 index từ corpus.

    Args:
        corpus: List of {'content': str, 'metadata': dict}
    """
    from rank_bm25 import BM25Okapi

    tokenized_corpus = [_tokenize(doc["content"]) for doc in corpus]
    return BM25Okapi(tokenized_corpus)


def _get_index():
    global _CORPUS, _BM25_INDEX
    if _BM25_INDEX is None:
        _CORPUS = _load_corpus()
        _BM25_INDEX = build_bm25_index(_CORPUS) if _CORPUS else None
    return _CORPUS, _BM25_INDEX


def lexical_search(query: str, top_k: int = 10) -> list[dict]:
    """
    Tìm kiếm từ khóa sử dụng BM25.

    Args:
        query: Câu truy vấn
        top_k: Số lượng kết quả tối đa

    Returns:
        List of {
            'content': str,
            'score': float,      # BM25 score
            'metadata': dict
        }
        Sorted by score descending.
    """
    corpus, bm25 = _get_index()
    if not corpus or bm25 is None:
        return []

    import numpy as np

    tokenized_query = _tokenize(query)
    scores = bm25.get_scores(tokenized_query)
    top_indices = np.argsort(scores)[::-1][:top_k]

    results = []
    for idx in top_indices:
        if scores[idx] > 0:
            results.append({
                "content": corpus[idx]["content"],
                "score": float(scores[idx]),
                "metadata": corpus[idx]["metadata"],
            })
    return results


# =============================================================================
# Bonus — TF-IDF baseline để so sánh với BM25 (demo CP6)
#
# Khác biệt cốt lõi (chuẩn bị giải thích khi demo):
#   1. TF saturation: BM25 có tham số k1 làm điểm bão hoà — từ khoá xuất hiện
#      lần thứ 10 đóng góp ít hơn nhiều lần thứ 2. TF-IDF thì tuyến tính, nên
#      một Điều luật lặp "doanh nghiệp" 50 lần sẽ áp đảo Điều thật sự trả lời.
#   2. Length normalization: BM25 có b (=0.75) điều chỉnh theo độ dài document
#      so với độ dài trung bình. TF-IDF chỉ chuẩn hoá L2, không mô hình hoá
#      việc document dài tự nhiên chứa nhiều từ hơn.
#   → Với corpus luật (Điều dài ngắn rất chênh nhau), BM25 công bằng hơn hẳn.
# =============================================================================

_TFIDF_VECTORIZER = None
_TFIDF_MATRIX = None


def _get_tfidf():
    global _TFIDF_VECTORIZER, _TFIDF_MATRIX, _CORPUS
    if _TFIDF_MATRIX is None:
        from sklearn.feature_extraction.text import TfidfVectorizer

        if _CORPUS is None:
            _CORPUS = _load_corpus()
        if not _CORPUS:
            return None, None, []

        _TFIDF_VECTORIZER = TfidfVectorizer(tokenizer=_tokenize, lowercase=True,
                                            token_pattern=None)
        _TFIDF_MATRIX = _TFIDF_VECTORIZER.fit_transform(
            [d["content"] for d in _CORPUS]
        )
    return _TFIDF_VECTORIZER, _TFIDF_MATRIX, _CORPUS


def lexical_search_tfidf(query: str, top_k: int = 10) -> list[dict]:
    """
    Bonus: sparse retrieval bằng TF-IDF + cosine similarity.

    Cùng interface với lexical_search() để so sánh A/B khi demo.
    """
    vectorizer, matrix, corpus = _get_tfidf()
    if vectorizer is None or not corpus:
        return []

    import numpy as np
    from sklearn.metrics.pairwise import cosine_similarity

    query_vec = vectorizer.transform([query])
    scores = cosine_similarity(query_vec, matrix)[0]
    top_indices = np.argsort(scores)[::-1][:top_k]

    return [
        {
            "content": corpus[idx]["content"],
            "score": float(scores[idx]),
            "metadata": corpus[idx]["metadata"],
        }
        for idx in top_indices
        if scores[idx] > 0
    ]


if __name__ == "__main__":
    demo_queries = [
        "hồ sơ đăng ký hộ kinh doanh cá thể",
        "vốn điều lệ công ty trách nhiệm hữu hạn",
        "Nghị định 52 nghĩa vụ người bán trên sàn",
    ]

    for query in demo_queries:
        print(f"\n=== {query} ===")
        print("-- BM25 --")
        for r in lexical_search(query, top_k=3):
            m = r["metadata"]
            print(f"  [{r['score']:.2f}] {m.get('doc_title', '')} — {m.get('legal_ref', '')}")

        print("-- TF-IDF (bonus) --")
        for r in lexical_search_tfidf(query, top_k=3):
            m = r["metadata"]
            print(f"  [{r['score']:.3f}] {m.get('doc_title', '')} — {m.get('legal_ref', '')}")
