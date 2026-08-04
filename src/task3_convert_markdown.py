"""
Task 3 — Chuẩn hoá dữ liệu thô thành Markdown sạch trong data/standardized/.

Nguồn vào: data/raw_crawl/*.md (bản cào thô, GIỮ NGUYÊN để đối chiếu khi debug)
Nguồn ra:  data/standardized/{legal,news}/*.md  (có YAML front-matter)

Pipeline 5 bước, chạy đúng thứ tự:
    1. Chuẩn hoá Unicode NFC
    2. Cắt rìa       — bỏ nav đầu file và widget cuối file
    3. Khử mục lục   — bỏ bản mục lục trùng với thân bài
    4. Ghép dòng vụn — nối lại câu bị thẻ <span> cắt rời
    5. Ghép âm tiết  — "khai thu ế" → "khai thuế"

Vì sao thứ tự này: bước 3 cần đếm nội dung giữa hai mốc Điều, mà nội dung chỉ đếm
đúng sau khi đã bỏ rác (bước 2). Bước 5 cần từ vựng dựng từ corpus SẠCH, chạy
trước bước 2 thì từ vựng nhiễm rác nav.

Chạy:
    python -m src.task3_convert_markdown
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from markitdown import MarkItDown

LANDING_DIR = Path(__file__).parent.parent / "data" / "landing"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "standardized"


def convert_legal_docs():
    """Convert PDF/DOCX files trong data/landing/legal/ sang markdown."""
    legal_dir = LANDING_DIR / "legal"
    output_dir = OUTPUT_DIR / "legal"
    output_dir.mkdir(parents=True, exist_ok=True)

    md = MarkItDown()

    for filepath in legal_dir.iterdir():
        if filepath.suffix.lower() in (".pdf", ".docx", ".doc"):
            print(f"Converting: {filepath.name}")
            # TODO: Convert và lưu file
            # result = md.convert(str(filepath))
            # output_path = output_dir / f"{filepath.stem}.md"
            # output_path.write_text(result.text_content, encoding="utf-8")
            # print(f"  ✓ Saved: {output_path}")
            raise NotImplementedError("Implement convert_legal_docs")


def convert_news_articles():
    """Convert JSON crawled articles trong data/landing/news/ sang markdown."""
    news_dir = LANDING_DIR / "news"
    output_dir = OUTPUT_DIR / "news"
    output_dir.mkdir(parents=True, exist_ok=True)

    for filepath in news_dir.iterdir():
        if filepath.suffix.lower() == ".json":
            print(f"Converting: {filepath.name}")
            # TODO: Đọc JSON, extract content_markdown, lưu thành .md
            # data = json.loads(filepath.read_text(encoding="utf-8"))
            # output_path = output_dir / f"{filepath.stem}.md"
            #
            # # Thêm metadata header
            # header = f"# {data.get('title', 'Unknown')}\n\n"
            # header += f"**Source:** {data.get('url', 'N/A')}\n"
            # header += f"**Crawled:** {data.get('date_crawled', 'N/A')}\n\n---\n\n"
            #
            # content = header + data.get("content_markdown", "")
            # output_path.write_text(content, encoding="utf-8")
            # print(f"  ✓ Saved: {output_path}")
            raise NotImplementedError("Implement convert_news_articles")


def convert_all() -> None:
    print("=" * 62)
    print("Task 3 — Chuẩn hoá dữ liệu thô")
    print("=" * 62)

    if not RAW_DIR.exists():
        raise SystemExit(f"Không thấy {RAW_DIR}. Đặt bản cào .md vào đó trước.")

    # Từ vựng dựng từ TOÀN BỘ corpus, không phải từng file — từ đúng ở file này
    # là bằng chứng để sửa chỗ bị tách ở file kia.
    raws = {n: (RAW_DIR / n).read_text(encoding="utf-8") for n in SOURCES if (RAW_DIR / n).exists()}
    tu_vung = build_vocabulary(list(raws.values()))
    print(f"\nTừ vựng corpus: {len(tu_vung):,} từ\n")

    for name, cfg in SOURCES.items():
        if name not in raws:
            print(f"  ⚠ thiếu {name} — bỏ qua")
            continue

        raw = raws[name]
        meta = doc_metadata(raw)
        sach = lam_sach(raw, cfg["structured"], tu_vung)

        doc_number = meta.get("doc_number") or cfg["doc_number"]
        front = [
            "---",
            f"doc_title: {cfg['doc_title']}",
            f"doc_number: {doc_number}",
            f"doc_id: {normalize_doc_number(doc_number)}",
            f"type: {'legal' if cfg['out'].startswith('legal/') else 'news'}",
            f"issued_date: {meta.get('issued_date', '')}",
            f"effective_date: {meta.get('effective_date', '')}",
            f"source_url: {cfg['url']}",
            "---",
            "",
        ]

        out = OUTPUT_DIR / cfg["out"]
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(front) + sach + "\n", encoding="utf-8")

        giam = 100 - len(sach) * 100 // max(len(raw), 1)
        print(f"  ✓ {name:<32} {len(raw):>8,} → {len(sach):>8,} ký tự (giảm {giam}%)")
        print(f"    → {out.relative_to(OUTPUT_DIR.parent.parent)}")

    print(f"\n✓ Xong. Output tại {OUTPUT_DIR}")


if __name__ == "__main__":
    convert_all()
