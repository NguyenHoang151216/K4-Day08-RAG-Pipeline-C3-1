"""Task 4 — đọc Markdown, chia chunk, tạo embedding và index ChromaDB."""

from __future__ import annotations

import os
import re
from functools import lru_cache
from hashlib import sha1
from pathlib import Path

STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"
CHROMA_DIR = Path(__file__).parent.parent / "chroma_db"

# Recursive splitting phù hợp tài liệu Markdown không đồng nhất. 100 ký tự
# overlap giúp giữ ngữ cảnh tại ranh giới nhưng vẫn tránh lặp quá nhiều.
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
CHUNKING_METHOD = "recursive"

# bge-m3: 1024 chiều, multilingual, mạnh với tiếng Việt. Nặng 2,27 GB.
# Mạng chậm thì đổi bằng biến môi trường, KHÔNG sửa code:
#     $env:EMBEDDING_MODEL="intfloat/multilingual-e5-small"; $env:EMBEDDING_DIM="384"
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))

VECTOR_STORE = "chromadb"
COLLECTION_NAME = "ecommerce_support_docs"

# Mốc mục của quy định sàn (TikTok/Shopee không dùng "Điều")
SECTION_RE = re.compile(r"^\s*(\d{1,2})\.\s+\S|^\s*([A-Z])\.\s+\S")


# =============================================================================
# Singleton — Task 5 import lại, đừng khởi tạo model/collection lần thứ hai
# =============================================================================

_model = None
_client = None


def get_embedding_model():
    """SentenceTransformer dùng chung. Cache module-level: model 2,27 GB, nạp hai
    lần là tốn gấp đôi RAM và gấp đôi thời gian khởi động."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def get_collection():
    """Collection ChromaDB dùng chung cho cả index (Task 4) lẫn truy vấn (Task 5)."""
    global _client
    if _client is None:
        import chromadb

        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return _client.get_or_create_collection(
        name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
    )


# =============================================================================
# Load
# =============================================================================

def _parse_front_matter(text: str) -> tuple[dict, str]:
    """Bóc front matter đơn giản do Task 3 tạo, không cần thêm PyYAML."""
    if not text.startswith("---"):
        return {}, text
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, re.DOTALL)
    if not match:
        return {}, text
    metadata = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            metadata[key.strip()] = value.strip().strip("\"'")
    return metadata, text[match.end():]


def load_documents() -> list[dict]:
    """Đọc đệ quy mọi file ``.md`` không rỗng trong data/standardized/."""
    if not STANDARDIZED_DIR.exists():
        return []

    documents = []
    for md_file in sorted(STANDARDIZED_DIR.rglob("*.md")):
        raw = md_file.read_text(encoding="utf-8").strip()
        if not raw:
            continue
        front_matter, content = _parse_front_matter(raw)
        content = content.strip()
        if not content:
            continue
        relative_path = md_file.relative_to(STANDARDIZED_DIR).as_posix()
        doc_type = "legal" if "legal" in md_file.parts else "news"
        documents.append({
            "content": content,
            "metadata": {
                **front_matter,
                "source": relative_path,
                "type": doc_type,
                "doc_type": doc_type,
            },
        })
    return documents


def _infer_customer_role(content: str, source: str = "") -> str:
    """Gắn buyer/seller/both theo từ khóa, ưu tiên không lọc mất tài liệu."""
    text = f"{source}\n{content}".lower()
    buyer = any(term in text for term in ("người mua", "khách hàng", "buyer"))
    seller = any(term in text for term in ("người bán", "thương nhân", "seller"))
    if buyer and not seller:
        return "buyer"
    if seller and not buyer:
        return "seller"
    return "both"


def _fallback_split(text: str) -> list[str]:
    """Recursive-like splitter dùng khi chưa cài langchain-text-splitters."""
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        if end < len(text):
            window = text[start:end]
            candidates = [window.rfind(sep) for sep in ("\n\n", "\n", ". ", " ")]
            boundary = max(candidates)
            # Không tạo chunk quá ngắn chỉ để bám dấu phân cách gần đầu.
            if boundary >= CHUNK_SIZE // 2:
                end = start + boundary + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(start + 1, end - CHUNK_OVERLAP)
    return chunks


def _split_text(text: str) -> list[str]:
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
    except ImportError:
        return _fallback_split(text)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )
    return splitter.split_text(text)


def chunk_documents(documents: list[dict]) -> list[dict]:
    """Chia documents thành chunks và bảo toàn metadata nguồn."""
    chunks = []
    for document in documents:
        content = str(document.get("content", "")).strip()
        if not content:
            continue
        base_metadata = dict(document.get("metadata") or {})
        role = _infer_customer_role(content, str(base_metadata.get("source", "")))
        for index, text in enumerate(_split_text(content)):
            article = next(
                (match.group(1) for line in text.splitlines()
                 if (match := _ARTICLE_RE.match(line))),
                "",
            )
            chunks.append({
                "content": text,
                "metadata": {
                    **base_metadata,
                    "chunk_index": index,
                    "customer_role": role,
                    "legal_ref": f"Điều {article}" if article else "",
                },
            })
    return chunks


@lru_cache(maxsize=1)
def get_embedding_model():
    """Load SentenceTransformer một lần và dùng chung cho Task 4/5."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBEDDING_MODEL)


def get_collection():
    """Mở collection đã index; ném NotFoundError nếu chưa chạy pipeline."""
    import chromadb

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_collection(name=COLLECTION_NAME)


def embed_chunks(chunks: list[dict]) -> list[dict]:
    model = get_embedding_model()
    texts = [c["content"] for c in chunks]
    embs = model.encode(texts, show_progress_bar=True, batch_size=16)
    for c, e in zip(chunks, embs):
        c["embedding"] = e.tolist()
    return chunks


def index_to_vectorstore(chunks: list[dict]):
    """Upsert chunks vào persistent Chroma collection sử dụng cosine distance."""
    if not chunks:
        return None
    import chromadb

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    ids = []
    for chunk in chunks:
        metadata = chunk["metadata"]
        identity = f"{metadata.get('source', '')}:{metadata.get('chunk_index', 0)}"
        ids.append(sha1(identity.encode("utf-8")).hexdigest())
    collection.upsert(
        ids=ids,
        documents=[chunk["content"] for chunk in chunks],
        embeddings=[chunk["embedding"] for chunk in chunks],
        metadatas=[chunk["metadata"] for chunk in chunks],
    )
    return collection


def run_pipeline() -> None:
    """Chạy toàn bộ pipeline Task 4 và in thống kê nghiệm thu."""
    print("=" * 58)
    print("Task 4: Chunking & Indexing")
    print(f"  Chunking: {CHUNKING_METHOD} (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")
    print(f"  Embedding: {EMBEDDING_MODEL} (dim={EMBEDDING_DIM})")
    print(f"  Vector Store: {VECTOR_STORE}")
    print("=" * 58)

    documents = load_documents()
    print(f"\nLoaded {len(documents)} documents")
    if not documents:
        raise SystemExit(
            "Không có file .md trong data/standardized/. "
            "Hãy chạy Task 3 hoặc đồng bộ branch chứa dữ liệu trước."
        )

    chunks = chunk_documents(documents)
    print(f"Created {len(chunks)} chunks")
    embedded_chunks = embed_chunks(chunks)
    print(f"Embedded {len(embedded_chunks)} chunks")
    collection = index_to_vectorstore(embedded_chunks)
    print(f"Indexed successfully. collection.count() = {collection.count()}")


if __name__ == "__main__":
    run_pipeline()
