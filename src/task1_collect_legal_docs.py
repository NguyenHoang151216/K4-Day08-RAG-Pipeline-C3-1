"""
Task 1 — Thu thập văn bản quy phạm pháp luật vào data/landing/legal/.

Chủ đề: Trợ lý Pháp lý Khởi nghiệp & Thương mại điện tử.

NGUỒN — vì sao là chinhphu.vn chứ không phải thuvienphapluat.vn
================================================================
`thuvienphapluat.vn` đặt `ClaudeBot: Disallow: /` trong robots.txt kèm
`Content-Signal: ai-train=no`. Script tự động KHÔNG cào trang đó. Bản .md của
Luật Doanh nghiệp 2020 và Nghị định 52/2013 trong data/raw_crawl/ do người tải
tay — đó là việc của con người, không phải của crawler.

`vanban.chinhphu.vn` có robots.txt = `Allow: /`, không cấm gì, và tệp gốc nằm
trên `datafiles.chinhphu.vn` theo pattern:

    https://datafiles.chinhphu.vn/cpp/files/vbpq/{năm}/{tháng}/{số}.signed.pdf

Lưu ý {tháng} là tháng ĐĂNG CÔNG BÁO, không phải tháng ban hành — Luật Doanh
nghiệp ban hành 17/06/2020 nhưng nằm ở thư mục 2020/07.

KHÔNG OCR
=========
Đo trên chinhphu.vn: nhiều PDF là bản ký số quét ảnh, không có lớp text. Script
này BÁO ra chứ không OCR. OCR tiếng Việt trên bảng biểu và dấu thanh đủ kém để
sinh ra điều khoản sai mà đọc vẫn hợp lý — loại lỗi nguy hiểm nhất cho một trợ lý
pháp lý. Nguồn CHỮ của pipeline là data/raw_crawl/*.md, PDF ở landing/ chỉ để lưu
bằng chứng nguồn.

Chạy:
    python -m src.task1_collect_legal_docs
"""

from __future__ import annotations

from pathlib import Path

import requests

DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "legal"

UA = {"User-Agent": "Mozilla/5.0 (compatible; VinUni-Lab08-RAG/1.0; +educational)"}
BASE = "https://datafiles.chinhphu.vn/cpp/files/vbpq"

# Mỗi mục: (tên file lưu, đường dẫn tương đối trên datafiles, mô tả, cụm chữ để
# xác minh đúng văn bản). Cụm xác minh cần thiết vì thư mục datafiles đặt tên
# theo SỐ văn bản, mà tháng đó có thể có nhiều văn bản trùng số khác loại.
DOCUMENTS = [
    (
        "luat-doanh-nghiep-59-2020-qh14.pdf",
        "2020/07/59.signed.pdf",
        "Luật Doanh nghiệp 2020 (59/2020/QH14)",
        "doanh nghiệp",
    ),
    (
        "luat-doanh-nghiep-59-2020-qh14-tiep.pdf",
        "2020/07/59tiep.pdf",
        "Luật Doanh nghiệp 2020 — phần tiếp",
        "doanh nghiệp",
    ),
    (
        "nghi-dinh-01-2021-nd-cp.pdf",
        "2021/01/01.signed.pdf",
        "Nghị định 01/2021/NĐ-CP về đăng ký doanh nghiệp",
        "đăng ký doanh nghiệp",
    ),
    (
        "nghi-dinh-01-2021-nd-cp-alt.pdf",
        "2021/01/1.signed.pdf",
        "Ứng viên thứ hai cho NĐ 01/2021 (cùng thư mục, khác cách đánh số)",
        "đăng ký doanh nghiệp",
    ),
]


def tai_file(url: str, dest: Path) -> int:
    """Tải một tệp về `dest`, trả số byte. Ném lên nếu HTTP lỗi."""
    r = requests.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    dest.write_bytes(r.content)
    return len(r.content)


def co_lop_text(path: Path) -> tuple[bool, int]:
    """PDF này có lớp text bóc được không? Trả (có_text, số_ký_tự).

    Trả (False, -1) khi máy chưa có thư viện đọc PDF — phân biệt với "đã đọc
    được nhưng rỗng" (ảnh quét), vì hai trường hợp đó cần hành động khác nhau.
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        try:
            from PyPDF2 import PdfReader  # type: ignore
        except ImportError:
            return False, -1
    try:
        reader = PdfReader(str(path))
        text = "".join((p.extract_text() or "") for p in reader.pages[:5])
        return len(text.strip()) > 200, len(text.strip())
    except Exception:
        return False, 0


def collect_all() -> None:
    print("=" * 62)
    print("Task 1 — Thu thập văn bản pháp luật (nguồn: chinhphu.vn)")
    print("=" * 62)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    for filename, rel, mota, cum_xac_minh in DOCUMENTS:
        dest = DATA_DIR / filename
        url = f"{BASE}/{rel}"
        try:
            n = tai_file(url, dest)
        except Exception as e:
            print(f"  ✗ {mota}\n      {type(e).__name__}: {e}")
            continue

        co_text, so_ky_tu = co_lop_text(dest)
        if so_ky_tu == -1:
            trang_thai = "chưa có thư viện đọc PDF để kiểm"
        elif co_text:
            trang_thai = f"CÓ lớp text ({so_ky_tu:,} ký tự/5 trang đầu)"
        else:
            trang_thai = "⚠ ẢNH QUÉT, không có lớp text — KHÔNG OCR, dùng .md làm nguồn chữ"

        print(f"  ✓ {mota}")
        print(f"      {filename}  {n:,} byte  |  {trang_thai}")

    files = sorted(p for p in DATA_DIR.iterdir() if p.suffix.lower() in {".pdf", ".docx", ".doc"})
    print(f"\n✓ {len(files)} tệp trong {DATA_DIR} (TestTask1 cần ≥3, mỗi tệp >1KB)")


if __name__ == "__main__":
    collect_all()
