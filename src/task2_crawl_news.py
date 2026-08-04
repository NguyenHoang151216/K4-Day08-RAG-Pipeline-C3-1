"""
Task 2 — Dựng data/landing/news/ (≥5 tệp JSON, mỗi tệp có field `url`).

Hai nhóm nguồn, cùng một schema JSON:

1. **Quy định sàn TMĐT** — TikTok Shop, Shopee. Đã cào sẵn về data/raw_crawl/,
   ở đây chỉ đóng gói lại thành JSON kèm metadata. Xếp vào `news/` chứ không phải
   `legal/` vì đây là chính sách nền tảng, KHÔNG phải văn bản quy phạm pháp luật —
   phân biệt này quan trọng khi trích dẫn.

2. **Bài báo** — VnExpress, chủ đề thuế với người bán hàng online. Cào bằng
   `requests` + `BeautifulSoup`; `crawl4ai` cần Playwright + Chromium (~150MB)
   mà các trang này là HTML tĩnh nên không cần tới.

Schema (TestTask2 kiểm sự tồn tại của `url` và kích thước >500 byte):
    {"url", "title", "date_crawled", "content_markdown", "source_type"}

Chạy:
    python -m src.task2_crawl_news
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

RAW_DIR = Path(__file__).parent.parent / "data" / "raw_crawl"
DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "news"

UA = {"User-Agent": "Mozilla/5.0 (compatible; VinUni-Lab08-RAG/1.0; +educational)"}


# =============================================================================
# Nhóm 1 — Quy định sàn TMĐT (đã có sẵn bản cào)
# =============================================================================

PLATFORM_DOCS = [
    {
        "raw": "tiktok_seller_policy.md",
        "out": "tiktok-seller-terms.json",
        "url": "https://seller-vn.tiktok.com/university/essay?knowledge_id=2581017870255874&lang=vi-VN",
        "title": "Điều khoản dịch vụ dành cho Người bán trên TikTok Shop",
    },
    {
        "raw": "shopee_product_policy.md",
        "out": "shopee-product-listing.json",
        "url": "https://help.shopee.vn/portal/4/article/77246",
        "title": "Quy định về đăng bán sản phẩm trên Shopee",
    },
]


# =============================================================================
# Nhóm 2 — Bài báo cần cào
# =============================================================================

ARTICLE_URLS = [
    "https://vnexpress.net/bi-khoi-to-voi-cao-buoc-ban-hang-online-hon-35-ty-dong-nhung-tron-thue-5083763.html",
    "https://vnexpress.net/ba-trum-ban-online-kim-cuong-hang-hieu-giau-doanh-thu-835-ty-dong-5092540.html",
    "https://vnexpress.net/indonesia-sap-thu-thue-ban-hang-online-4906712.html",
]


def crawl_article(url: str) -> dict:
    """Cào một bài báo HTML tĩnh, trả dict theo schema chung.

    Bóc theo thẻ ngữ nghĩa của VnExpress (`h1.title-detail`, `p.Normal`) rồi mới
    fallback sang `<article>`/`<p>`. Bóc mù toàn bộ `<p>` sẽ nuốt cả menu, quảng
    cáo và bài liên quan — đúng loại nhiễu vừa mất công dọn ở Task 3.
    """
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")

    h = soup.select_one("h1.title-detail") or soup.select_one("h1")
    title = h.get_text(strip=True) if h else "Không rõ tiêu đề"

    sapo = soup.select_one("p.description")
    paras = soup.select("article p.Normal") or soup.select("p.Normal") or soup.select("article p")

    parts = []
    if sapo:
        parts.append(f"**{sapo.get_text(strip=True)}**")
    parts += [p.get_text(strip=True) for p in paras if len(p.get_text(strip=True)) > 30]

    content = unicodedata.normalize("NFC", "\n\n".join(parts))
    return {
        "url": url,
        "title": unicodedata.normalize("NFC", title),
        "date_crawled": datetime.now().isoformat(timespec="seconds"),
        "content_markdown": f"# {title}\n\n{content}",
        "source_type": "news_article",
    }


def dong_goi_platform() -> int:
    """Đóng gói bản cào quy định sàn thành JSON."""
    n = 0
    for cfg in PLATFORM_DOCS:
        src = RAW_DIR / cfg["raw"]
        if not src.exists():
            print(f"  ⚠ thiếu {src.name} — bỏ qua")
            continue
        text = unicodedata.normalize("NFC", src.read_text(encoding="utf-8"))
        rec = {
            "url": cfg["url"],
            "title": cfg["title"],
            "date_crawled": datetime.now().isoformat(timespec="seconds"),
            "content_markdown": text,
            "source_type": "platform_policy",
        }
        out = DATA_DIR / cfg["out"]
        out.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  ✓ {cfg['out']:<32} {out.stat().st_size:>9,} byte  [quy định sàn]")
        n += 1
    return n


def crawl_all() -> None:
    print("=" * 62)
    print("Task 2 — Dựng data/landing/news/")
    print("=" * 62)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    print("\n--- Quy định sàn TMĐT ---")
    n = dong_goi_platform()

    print("\n--- Bài báo ---")
    for i, url in enumerate(ARTICLE_URLS, 1):
        name = f"article_{i:02d}.json"
        try:
            rec = crawl_article(url)
        except Exception as e:
            print(f"  ✗ {url[:70]}\n      {type(e).__name__}: {e}")
            continue
        if len(rec["content_markdown"]) < 400:
            # Cào ra vỏ rỗng thì BÁO, đừng ghi file rác cho qua test
            print(f"  ⚠ {name} chỉ có {len(rec['content_markdown'])} ký tự — bỏ, không ghi")
            continue
        out = DATA_DIR / name
        out.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  ✓ {name:<32} {out.stat().st_size:>9,} byte  [{rec['title'][:40]}]")
        n += 1

    files = [p for p in DATA_DIR.iterdir() if p.is_file() and not p.name.startswith(".")]
    nho = [p.name for p in files if p.stat().st_size <= 500]
    print(f"\n✓ {len(files)} tệp trong {DATA_DIR} (TestTask2 cần ≥5, mỗi tệp >500 byte)")
    if nho:
        print(f"  ⚠ tệp quá nhỏ: {nho}")


if __name__ == "__main__":
    crawl_all()
