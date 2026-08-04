"""
Task 4 — Chunking & Indexing vào ChromaDB.

CHUNKING 2 TẦNG — không cắt mù 800 ký tự
=========================================
Với văn bản pháp luật, đáp án của một câu hỏi gần như luôn nằm gọn trong MỘT
Điều. Cắt mù làm đứt Điều giữa chừng và mất khả năng trích dẫn chính xác.

    Tầng 1 — cắt theo cấu trúc
        Văn bản QPPL : ^Điều\\s+(\\d+[a-z]?)  → mỗi Điều = 1 chunk
        Quy định sàn : mốc mục đánh số (^\\d+\\., ^[A-Z]\\.)
    Tầng 2 — chỉ khi 1 khối > CHUNK_SIZE
        RecursiveCharacterTextSplitter(800, overlap=100)
        Mọi chunk con THỪA KẾ legal_ref của khối cha
        → chunk con thứ 3 của Điều 87 vẫn cite được "[NĐ 01/2021, Điều 87]"

Lưu ý vận hành: đổi corpus thì phải XOÁ chroma_db/ trước khi index lại, nếu
không chunk cũ và mới tồn tại lẫn lộn trong cùng collection.

Chạy:
    python -m src.task4_chunking_indexing
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from .legal_utils import (
    ARTICLE_RE,
    infer_customer_role,
    make_provision_id,
    normalize_doc_number,
)

STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"
CHROMA_DIR = Path(__file__).parent.parent / "chroma_db"


# =============================================================================
# CONFIGURATION
# =============================================================================

# 800/100 theo chốt của nhóm. Một Điều trung bình 600–900 ký tự nên phần lớn Điều
# lọt gọn vào 1 chunk; overlap 100 chỉ dùng cho các Điều dài phải cắt tiếp.
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
CHUNKING_METHOD = "legal_structure_then_recursive"

# bge-m3: 1024 chiều, multilingual, mạnh với tiếng Việt. Nặng 2,27 GB.
# Mạng chậm thì đổi bằng biến môi trường, KHÔNG sửa code:
#     $env:EMBEDDING_MODEL="intfloat/multilingual-e5-small"; $env:EMBEDDING_DIM="384"
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))

VECTOR_STORE = "chromadb"
COLLECTION_NAME = "ecommerce_legal_docs"

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
    """Bóc YAML front-matter do Task 3 ghi. Trả ({}, text) nếu không có."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    meta = {}
    for line in text[3:end].strip().split("\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, text[end + 4 :].lstrip("\n")


def load_documents() -> list[dict]:
    """Đọc data/standardized/**/*.md kèm metadata từ front-matter."""
    docs = []
    for md in sorted(STANDARDIZED_DIR.rglob("*.md")):
        meta, body = _parse_front_matter(md.read_text(encoding="utf-8"))
        docs.append(
            {
                "content": body,
                "metadata": {
                    "source": md.name,
                    "type": meta.get("type") or ("legal" if "legal" in str(md) else "news"),
                    "doc_title": meta.get("doc_title", md.stem),
                    "doc_number": meta.get("doc_number", ""),
                    "doc_id": meta.get("doc_id") or normalize_doc_number(meta.get("doc_number", "")),
                    "issued_date": meta.get("issued_date", ""),
                    "effective_date": meta.get("effective_date", ""),
                    "source_url": meta.get("source_url", ""),
                },
            }
        )
    return docs


# =============================================================================
# Chunk — 2 tầng
# =============================================================================

def _cat_tang_1(text: str, structured: bool) -> list[tuple[str, str]]:
    """Cắt theo cấu trúc. Trả list (legal_ref, nội_dung_khối).

    `legal_ref` là "" cho phần mở đầu đứng trước mốc đầu tiên (căn cứ ban hành),
    và cho quy định sàn thì là nhãn mục ("Mục 3") thay vì "Điều N".
    """
    lines = text.split("\n")
    moc: list[tuple[int, str]] = []
    for i, l in enumerate(lines):
        if structured:
            if m := ARTICLE_RE.match(l):
                moc.append((i, f"Điều {m.group(1)}"))
        elif m := SECTION_RE.match(l):
            moc.append((i, f"Mục {m.group(1) or m.group(2)}"))

    if not moc:
        return [("", text)]

    khoi = []
    if moc[0][0] > 0:
        dau = "\n".join(lines[: moc[0][0]]).strip()
        if dau:
            khoi.append(("", dau))
    for k, (i, ref) in enumerate(moc):
        ket = moc[k + 1][0] if k + 1 < len(moc) else len(lines)
        noi_dung = "\n".join(lines[i:ket]).strip()
        if noi_dung:
            khoi.append((ref, noi_dung))
    return khoi


def chunk_documents(documents: list[dict]) -> list[dict]:
    """Chunk 2 tầng, gắn đủ 11 trường metadata."""
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks: list[dict] = []
    for doc in documents:
        meta = doc["metadata"]
        structured = meta["type"] == "legal"
        doc_id = meta["doc_id"] or meta["source"].replace(".md", "")

        idx = 0
        for ref, khoi in _cat_tang_1(doc["content"], structured):
            # Tầng 2: chỉ cắt tiếp khi khối vượt giới hạn
            phan = splitter.split_text(khoi) if len(khoi) > CHUNK_SIZE else [khoi]
            so = re.sub(r"\D", "", ref) or "0"
            for j, noi_dung in enumerate(phan):
                if not noi_dung.strip():
                    continue
                # Chunk con thừa kế nguyên legal_ref của khối cha → citation vẫn
                # trỏ đúng Điều dù nội dung đã bị cắt làm nhiều mảnh.
                pid = make_provision_id(doc_id, "article" if structured else "section", so)
                if len(phan) > 1:
                    pid = f"{pid}__p{j}"
                chunks.append(
                    {
                        "content": noi_dung.strip(),
                        "metadata": {
                            **meta,
                            "chunk_index": idx,
                            "legal_ref": ref,
                            "provision_id": pid,
                            "customer_role": infer_customer_role(noi_dung, meta["doc_title"]),
                        },
                    }
                )
                idx += 1
    return chunks


# =============================================================================
# Embed + Index
# =============================================================================

def embed_chunks(chunks: list[dict]) -> list[dict]:
    model = get_embedding_model()
    texts = [c["content"] for c in chunks]
    embs = model.encode(texts, show_progress_bar=True, batch_size=16)
    for c, e in zip(chunks, embs):
        c["embedding"] = e.tolist()
    return chunks


def index_to_vectorstore(chunks: list[dict]) -> None:
    col = get_collection()
    # id phải DUY NHẤT: provision_id có thể trùng khi một Điều bị cắt nhiều mảnh
    # ở các văn bản khác nhau, nên ghép thêm source + chunk_index.
    ids = [f"{c['metadata']['source']}#{c['metadata']['chunk_index']}" for c in chunks]
    B = 500
    for i in range(0, len(chunks), B):
        lo = chunks[i : i + B]
        col.upsert(
            ids=ids[i : i + B],
            documents=[c["content"] for c in lo],
            embeddings=[c["embedding"] for c in lo],
            metadatas=[c["metadata"] for c in lo],
        )


def run_pipeline() -> None:
    print("=" * 62)
    print("Task 4 — Chunking & Indexing")
    print(f"  Chunking : {CHUNKING_METHOD} (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")
    print(f"  Embedding: {EMBEDDING_MODEL} (dim={EMBEDDING_DIM})")
    print(f"  Store    : {VECTOR_STORE} / {COLLECTION_NAME}")
    print("=" * 62)

    docs = load_documents()
    print(f"\n✓ Nạp {len(docs)} văn bản")

    chunks = chunk_documents(docs)
    print(f"✓ Tạo {len(chunks)} chunk")
    co_ref = sum(1 for c in chunks if c["metadata"]["legal_ref"])
    print(f"  legal_ref có giá trị: {co_ref}/{len(chunks)} ({co_ref*100//max(len(chunks),1)}%)")
    qua = [c for c in chunks if len(c["content"]) > CHUNK_SIZE * 1.1]
    if qua:
        print(f"  ⚠ {len(qua)} chunk vượt giới hạn size — TestTask4 sẽ trượt")

    chunks = embed_chunks(chunks)
    print(f"✓ Embed {len(chunks)} chunk")

    index_to_vectorstore(chunks)
    print(f"✓ Index xong. collection.count() = {get_collection().count()}")


if __name__ == "__main__":
    run_pipeline()
