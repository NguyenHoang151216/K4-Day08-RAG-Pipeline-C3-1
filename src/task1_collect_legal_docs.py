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

KHÔNG OCR — nhưng CÓ bóc lớp text nếu PDF thật sự có
====================================================
Phân biệt hai thứ khác hẳn nhau:

  - **PDF quét ảnh** (không có lớp text): script BÁO ra chứ KHÔNG OCR. OCR tiếng
    Việt trên bảng biểu và dấu thanh đủ kém để sinh ra điều khoản sai mà đọc vẫn
    hợp lý — loại lỗi nguy hiểm nhất cho một trợ lý pháp lý.
  - **PDF gốc số hoá** (có sẵn lớp text do trình soạn thảo nhúng vào): bóc ra là
    thao tác đọc thuần tuý, không suy đoán ký tự, không sai dấu. An toàn.

Đo thực tế: mọi PDF ký số của văn bản 2020–2021 trên chinhphu.vn đều là ảnh quét
(0 ký tự). Ngược lại bản Công báo của Luật Thuế GTGT 2024 là bản gốc số hoá —
44.738 ký tự, đủ 18/18 "Điều", không một lỗi dấu nào. Nên chỉ file loại sau mới
được bóc sang data/raw_crawl/.

⚠️ Đã kiểm và LOẠI: Thông tư 40/2021/TT-BTC. Bản duy nhất có lớp text (vbpq.mof.gov.vn)
là lớp text do OCR sinh ra — hỏng dấu ("thué", "thảng", "bảo hiếm") và mất 4/21
heading Điều. Quan trọng hơn: ngưỡng 100 triệu trong đó ĐÃ HẾT HIỆU LỰC, bị Luật
Thuế GTGT 2024 nâng lên 200 triệu từ 01/01/2026. Nạp vào sẽ khiến chatbot trả lời
sai con số kèm citation trông rất thuyết phục.

Chạy:
    python -m src.task1_collect_legal_docs
"""

from __future__ import annotations

from pathlib import Path

import requests

DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "legal"
RAW_DIR = Path(__file__).parent.parent / "data" / "raw_crawl"

UA = {"User-Agent": "Mozilla/5.0 (compatible; VinUni-Lab08-RAG/1.0; +educational)"}
BASE = "https://datafiles.chinhphu.vn/cpp/files/vbpq"

# Mỗi mục: (tên file lưu, đường dẫn tương đối trên datafiles, mô tả, cụm chữ để
# xác minh đúng văn bản, tên file .md ở raw_crawl nếu PDF có lớp text — None thì
# chỉ lưu làm bằng chứng nguồn). Cụm xác minh cần thiết vì thư mục datafiles đặt
# tên theo SỐ văn bản, mà tháng đó có thể có nhiều văn bản trùng số khác loại.
DOCUMENTS = [
    (
        "luat-doanh-nghiep-59-2020-qh14.pdf",
        "2020/07/59.signed.pdf",
        "Luật Doanh nghiệp 2020 (59/2020/QH14)",
        "doanh nghiệp",
        None,   # ảnh quét — bản .md do người tải tay
    ),
    (
        "luat-doanh-nghiep-59-2020-qh14-tiep.pdf",
        "2020/07/59tiep.pdf",
        "Luật Doanh nghiệp 2020 — phần tiếp",
        "doanh nghiệp",
        None,
    ),
    (
        "nghi-dinh-01-2021-nd-cp.pdf",
        "2021/01/01nd.signed.pdf",   # tên đúng lấy từ trang vanban.chinhphu.vn;
        "Nghị định 01/2021/NĐ-CP về đăng ký doanh nghiệp",   # bản "01.signed.pdf"
        "đăng ký doanh nghiệp",                              # trước đó là file khác
        None,   # 85 trang, đo được 0 ký tự → ảnh quét, KHÔNG OCR
    ),
    (
        "luat-thue-gtgt-48-2024-qh15.pdf",
        "2025/01/luat48.pdf",
        "Luật Thuế GTGT 2024 (48/2024/QH15) — ngưỡng 200 triệu, hiệu lực 01/01/2026",
        "giá trị gia tăng",
        "luat_thue_gtgt_2024.md",   # bản Công báo gốc số hoá → bóc được
    ),
]


def tai_file(url: str, dest: Path) -> int:
    """Tải một tệp về `dest`, trả số byte. Ném lên nếu HTTP lỗi."""
    r = requests.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    dest.write_bytes(r.content)
    return len(r.content)


def doc_lop_text(path: Path) -> tuple[str, int]:
    """Đọc lớp text có sẵn của PDF. Trả (text, mã_trạng_thái).

    mã: 1 = có lớp text thật · 0 = đọc được nhưng rỗng (ảnh quét) · -1 = chưa có
    thư viện để kiểm. Phân biệt 0 với -1 vì hai trường hợp cần hành động khác nhau:
    ảnh quét thì dừng hẳn, còn thiếu thư viện thì cài thêm là xong.

    Dùng MarkItDown — dependency ĐÃ khai báo ở requirements.txt và cũng là công cụ
    Task 3 dùng. Bản trước gọi pypdf/PyPDF2 vốn KHÔNG có trong requirements nên
    luôn rơi vào nhánh -1, khiến mọi PDF đều bị báo "chưa kiểm được".
    """
    try:
        from markitdown import MarkItDown
    except ImportError:
        return "", -1
    try:
        text = MarkItDown().convert(str(path)).text_content.strip()
    except Exception:
        return "", 0
    # Ngưỡng 200 ký tự: bản quét vẫn có thể sinh vài chục ký tự rác từ metadata.
    return text, (1 if len(text) > 200 else 0)


def boc_lop_text(text: str, ten_md: str) -> str:
    """Ghi lớp text đã đọc được sang data/raw_crawl/<ten_md>.

    KHÔNG phải OCR: chỉ lấy chuỗi ký tự mà trình soạn thảo đã nhúng sẵn trong
    PDF, không có bước suy đoán hình dạng chữ nên không sinh ra lỗi dấu.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out = RAW_DIR / ten_md
    out.write_text(text, encoding="utf-8")
    return f"→ raw_crawl/{ten_md} ({len(text):,} ký tự)"


def collect_all() -> None:
    print("=" * 62)
    print("Task 1 — Thu thập văn bản pháp luật (nguồn: chinhphu.vn)")
    print("=" * 62)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    for filename, rel, mota, cum_xac_minh, ten_md in DOCUMENTS:
        dest = DATA_DIR / filename
        url = f"{BASE}/{rel}"
        try:
            n = tai_file(url, dest)
        except Exception as e:
            print(f"  ✗ {mota}\n      {type(e).__name__}: {e}")
            continue

        text, ma = doc_lop_text(dest)
        if ma == -1:
            trang_thai = "chưa cài markitdown để kiểm"
        elif ma == 1:
            trang_thai = f"CÓ lớp text ({len(text):,} ký tự)"
        else:
            trang_thai = "⚠ ẢNH QUÉT, không có lớp text — KHÔNG OCR, dùng .md làm nguồn chữ"

        print(f"  ✓ {mota}")
        print(f"      {filename}  {n:,} byte  |  {trang_thai}")

        # Xác minh đúng văn bản: thư mục datafiles đặt tên theo SỐ nên dễ trùng.
        if ma == 1 and cum_xac_minh.lower() not in text.lower():
            print(f"      ⚠ KHÔNG thấy cụm '{cum_xac_minh}' — có thể tải nhầm văn bản")

        # Chỉ bóc khi ĐÃ khai báo tên .md VÀ đo được lớp text thật. Hai điều kiện
        # cùng lúc: khai báo mà file hoá ra là ảnh quét thì bỏ qua, không OCR chữa cháy.
        if ten_md and ma == 1:
            print(f"      {boc_lop_text(text, ten_md)}")
        elif ten_md:
            print(f"      ✗ khai báo bóc sang {ten_md} nhưng không có lớp text — BỎ QUA")

    files = sorted(p for p in DATA_DIR.iterdir() if p.suffix.lower() in {".pdf", ".docx", ".doc"})
    print(f"\n✓ {len(files)} tệp trong {DATA_DIR} (TestTask1 cần ≥3, mỗi tệp >1KB)")


if __name__ == "__main__":
    collect_all()
