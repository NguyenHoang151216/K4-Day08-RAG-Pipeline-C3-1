"""
Task 3 — Convert toàn bộ file trong data/landing/ thành Markdown.

Sử dụng MarkItDown của Microsoft:
    https://github.com/microsoft/markitdown

Cài đặt:
    pip install "markitdown[pdf]"
    # Lưu ý: cần extra [pdf] để convert được file PDF. Chỉ "pip install markitdown"
    # (không có extra) sẽ báo MissingDependencyException khi convert PDF, dù JSON/DOCX
    # vẫn convert bình thường.

Hướng dẫn:
    1. Scan toàn bộ file trong data/landing/ (PDF, DOCX, JSON)
    2. Convert sang Markdown
    3. Lưu vào data/standardized/ giữ nguyên cấu trúc thư mục
"""

import json
from pathlib import Path

try:
    from markitdown import MarkItDown
except ImportError:  # Allow JSON conversion even when the optional converter is absent.
    MarkItDown = None

LANDING_DIR = Path(__file__).parent.parent / "data" / "landing"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "standardized"


def convert_legal_docs():
    """Convert PDF/DOCX files trong data/landing/legal/ sang markdown."""
    legal_dir = LANDING_DIR / "legal"
    output_dir = OUTPUT_DIR / "legal"
    output_dir.mkdir(parents=True, exist_ok=True)

    if not legal_dir.exists():
        print(f"  No input directory found: {legal_dir}")
        return

    legal_files = [
        filepath
        for filepath in sorted(legal_dir.rglob("*"))
        if filepath.suffix.lower() in (".pdf", ".docx", ".doc")
    ]
    if not legal_files:
        print("  No supported legal documents found.")
        return
    if MarkItDown is None:
        raise RuntimeError(
            'MarkItDown is required for legal documents. '
            'Install it with: pip install "markitdown[pdf]"'
        )

    md = MarkItDown()
    for filepath in legal_files:
        print(f"Converting: {filepath.name}")
        result = md.convert(str(filepath))

        # Preserve any directory hierarchy below landing/legal/.
        relative_path = filepath.relative_to(legal_dir).with_suffix(".md")
        output_path = output_dir / relative_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(result.text_content or "", encoding="utf-8")
        print(f"  ✓ Saved: {output_path}")


def convert_news_articles():
    """Convert JSON crawled articles trong data/landing/news/ sang markdown."""
    news_dir = LANDING_DIR / "news"
    output_dir = OUTPUT_DIR / "news"
    output_dir.mkdir(parents=True, exist_ok=True)

    if not news_dir.exists():
        print(f"  No input directory found: {news_dir}")
        return

    for filepath in sorted(news_dir.rglob("*.json")):
        print(f"Converting: {filepath.name}")
        data = json.loads(filepath.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            raise ValueError(f"Expected a JSON object in {filepath}")

        relative_path = filepath.relative_to(news_dir).with_suffix(".md")
        output_path = output_dir / relative_path
        output_path.parent.mkdir(parents=True, exist_ok=True)

        title = str(data.get("title") or "Unknown")
        source = str(data.get("url") or "N/A")
        crawled_at = str(data.get("date_crawled") or "N/A")
        article_content = data.get("content_markdown", "")
        if not isinstance(article_content, str):
            article_content = str(article_content)

        header = (
            f"# {title}\n\n"
            f"**Source:** {source}\n"
            f"**Crawled:** {crawled_at}\n\n"
            "---\n\n"
        )
        output_path.write_text(header + article_content, encoding="utf-8")
        print(f"  ✓ Saved: {output_path}")


def convert_all():
    """Convert toàn bộ files."""
    print("=" * 50)
    print("Task 3: Convert to Markdown (MarkItDown)")
    print("=" * 50)

    print("\n--- Legal Documents ---")
    convert_legal_docs()

    print("\n--- News Articles ---")
    convert_news_articles()

    print("\n✓ Done! Output tại:", OUTPUT_DIR)


if __name__ == "__main__":
    convert_all()
