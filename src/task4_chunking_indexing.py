"""
Task 4 — Chunking & Indexing vào Vector Store.

Hướng dẫn:
    1. Đọc toàn bộ markdown files từ data/standardized/
    2. Chọn 1 chunking strategy (giải thích lý do)
    3. Chọn 1 embedding model (giải thích lý do)
    4. Index vào vector store (ChromaDB khuyến cáo — đơn giản, local, không cần Docker)

Chunking options (langchain-text-splitters):
    - RecursiveCharacterTextSplitter: an toàn, phổ biến
    - MarkdownHeaderTextSplitter: tốt cho file có heading
    - SemanticChunker: dùng embedding để tách (nâng cao)

Embedding model options:
    - sentence-transformers/all-MiniLM-L6-v2 (384 dim, nhẹ)
    - BAAI/bge-m3 (1024 dim, multilingual, tốt cho cả tiếng Việt lẫn tiếng Anh)
    - OpenAI text-embedding-3-small (1536 dim, API)

Vector store options:
    - ChromaDB (khuyến cáo: đơn giản, local persistent, không cần Docker)
    - Weaviate (hỗ trợ hybrid search built-in, cần Docker/Cloud)
    - FAISS (chỉ dense search)

Cài đặt:
    pip install langchain-text-splitters sentence-transformers chromadb

Lưu ý quan trọng: nếu sau này đổi corpus (đổi chủ đề, thêm/bớt tài liệu), phải XÓA
chroma_db/ cũ trước khi reindex — nếu không, chunk cũ và mới sẽ tồn tại lẫn lộn
trong cùng collection, retrieval sẽ trả về kết quả rác từ dữ liệu cũ.
"""

from functools import lru_cache
from hashlib import sha1
from pathlib import Path

STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"
CHROMA_DIR = Path(__file__).parent.parent / "chroma_db"


# =============================================================================
# CONFIGURATION — Giải thích lựa chọn của bạn trong comment
# =============================================================================

# Recursive splitting giữ được đoạn/văn/câu khi có thể, đồng thời vẫn bảo đảm
# giới hạn kích thước với tài liệu Markdown có cấu trúc không đồng nhất.
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100     # Giữ ngữ cảnh ở ranh giới giữa hai chunk liên tiếp.
CHUNKING_METHOD = "recursive"  # "recursive" | "markdown_header" | "semantic"

# BGE-M3 hỗ trợ tốt corpus tiếng Việt/Anh và dùng được cho dense retrieval local.
EMBEDDING_MODEL = "BAAI/bge-m3"
EMBEDDING_DIM = 1024

# TODO: Chọn vector store
VECTOR_STORE = "chromadb"  # "chromadb" | "weaviate" | "faiss"
COLLECTION_NAME = "ecommerce_support_docs"


# =============================================================================
# IMPLEMENTATION
# =============================================================================

def load_documents() -> list[dict]:
    """
    Đọc toàn bộ markdown files từ data/standardized/.

    Returns:
        List of {'content': str, 'metadata': {'source': str, 'type': str}}
    """
    if not STANDARDIZED_DIR.exists():
        return []

    documents = []
    for md_file in sorted(STANDARDIZED_DIR.rglob("*.md")):
        content = md_file.read_text(encoding="utf-8").strip()
        if not content:
            continue
        relative_path = md_file.relative_to(STANDARDIZED_DIR).as_posix()
        doc_type = "legal" if "legal" in md_file.parts else "news"
        documents.append({
            "content": content,
            "metadata": {
                "source": relative_path,
                "type": doc_type,
                "doc_type": doc_type,
            },
        })
    return documents


def _infer_customer_role(document: dict) -> str:
    """Suy ra nhóm khách hàng từ tên nguồn và nội dung tài liệu."""
    metadata = document.get("metadata", {})
    searchable = " ".join([
        str(metadata.get("source", "")),
        document.get("content", "")[:2000],
    ]).lower()
    seller_terms = ("nguoi-ban", "người bán", "seller")
    buyer_terms = ("nguoi-mua", "người mua", "buyer")
    has_seller = any(term in searchable for term in seller_terms)
    has_buyer = any(term in searchable for term in buyer_terms)
    if has_seller and not has_buyer:
        return "seller"
    if has_buyer and not has_seller:
        return "buyer"
    return "both"


def chunk_documents(documents: list[dict]) -> list[dict]:
    """
    Chunk documents theo strategy đã chọn.

    Returns:
        List of {'content': str, 'metadata': dict} — mỗi item là 1 chunk
    """
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )
    chunks = []
    for document in documents:
        content = document.get("content", "").strip()
        if not content:
            continue
        role = _infer_customer_role(document)
        for index, text in enumerate(splitter.split_text(content)):
            chunks.append({
                "content": text,
                "metadata": {
                    **document.get("metadata", {}),
                    "chunk_index": index,
                    "customer_role": role,
                },
            })
    return chunks


@lru_cache(maxsize=1)
def get_embedding_model():
    """Khởi tạo embedding model một lần và dùng chung cho indexing/search."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBEDDING_MODEL)


def get_collection():
    """Mở collection đã được index; không tự tạo collection rỗng."""
    import chromadb

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_collection(name=COLLECTION_NAME)


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """
    Embed toàn bộ chunks bằng model đã chọn.

    Returns:
        Mỗi chunk dict được thêm key 'embedding': list[float]
    """
    if not chunks:
        return []
    model = get_embedding_model()
    embeddings = model.encode(
        [chunk["content"] for chunk in chunks],
        show_progress_bar=True,
        normalize_embeddings=True,
    )
    for chunk, embedding in zip(chunks, embeddings):
        chunk["embedding"] = embedding.tolist()
    return chunks


def index_to_vectorstore(chunks: list[dict]):
    """
    Lưu chunks vào vector store đã chọn.
    """
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
        meta = chunk["metadata"]
        identity = f"{meta.get('source', '')}:{meta.get('chunk_index', 0)}"
        ids.append(sha1(identity.encode("utf-8")).hexdigest())
    collection.upsert(
        ids=ids,
        documents=[chunk["content"] for chunk in chunks],
        embeddings=[chunk["embedding"] for chunk in chunks],
        metadatas=[chunk["metadata"] for chunk in chunks],
    )
    return collection


def run_pipeline():
    """Chạy toàn bộ pipeline: load → chunk → embed → index."""
    print("=" * 50)
    print("Task 4: Chunking & Indexing")
    print(f"  Chunking: {CHUNKING_METHOD} (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")
    print(f"  Embedding: {EMBEDDING_MODEL} (dim={EMBEDDING_DIM})")
    print(f"  Vector Store: {VECTOR_STORE}")
    print("=" * 50)

    docs = load_documents()
    print(f"\n✓ Loaded {len(docs)} documents")

    chunks = chunk_documents(docs)
    print(f"✓ Created {len(chunks)} chunks")

    chunks = embed_chunks(chunks)
    print(f"✓ Embedded {len(chunks)} chunks")

    index_to_vectorstore(chunks)
    print("✓ Indexed to vector store")


if __name__ == "__main__":
    run_pipeline()
