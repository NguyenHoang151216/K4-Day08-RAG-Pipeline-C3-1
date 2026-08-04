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

from .legal_utils import (
    ARTICLE_RE,
    build_vocabulary,
    fix_split_syllables,
    is_quoted_article,
    normalize_doc_number,
    parse_vn_date,
)

RAW_DIR = Path(__file__).parent.parent / "data" / "raw_crawl"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "standardized"


# =============================================================================
# KHAI BÁO NGUỒN — một chỗ duy nhất, Task 4 đọc lại front-matter nên không cần
# lặp thông tin này ở đó.
# =============================================================================

SOURCES = {
    "luat_doanh_nghiep_2020.md": {
        "out": "legal/luat-doanh-nghiep-59-2020-qh14.md",
        "doc_title": "Luật Doanh nghiệp 2020",
        "doc_number": "59/2020/QH14",
        "url": "https://thuvienphapluat.vn/van-ban/Doanh-nghiep/Luat-Doanh-nghiep-so-59-2020-QH14-427301.aspx",
        "structured": True,   # có cấu trúc "Điều N"
    },
    "nghi_dinh_52_2013.md": {
        "out": "legal/nghi-dinh-52-2013-nd-cp.md",
        "doc_title": "Nghị định 52/2013/NĐ-CP về thương mại điện tử",
        "doc_number": "52/2013/NĐ-CP",
        "url": "https://thuvienphapluat.vn/van-ban/Thuong-mai/Nghi-dinh-52-2013-ND-CP-thuong-mai-dien-tu-187901.aspx",
        "structured": True,
    },
    # Trả lời câu demo #1 "doanh thu bao nhiêu thì phải nộp thuế".
    # Dùng Luật Thuế GTGT 2024 chứ KHÔNG dùng Thông tư 40/2021: ngưỡng 100 triệu
    # trong TT 40 đã bị khoản 25 Điều 5 Luật này nâng lên 200 triệu từ 01/01/2026.
    # File .md do Task 1 bóc tự động từ bản Công báo gốc số hoá (không OCR).
    "luat_thue_gtgt_2024.md": {
        "out": "legal/luat-thue-gtgt-48-2024-qh15.md",
        "doc_title": "Luật Thuế giá trị gia tăng 2024",
        "doc_number": "48/2024/QH15",
        "url": "https://datafiles.chinhphu.vn/cpp/files/vbpq/2025/01/luat48.pdf",
        "structured": True,
    },
    # Trả lời câu demo #2 "hồ sơ đăng ký hộ kinh doanh" (Điều 87 trở đi).
    # ⚠️ Mọi PDF của văn bản này trên chinhphu.vn đều là ảnh quét (đo: 0 ký tự/85
    # trang) nên KHÔNG bóc tự động được, và thuvienphapluat.vn chặn bot trong
    # robots.txt. Bản .md phải do người tải tay — giống 4 file gốc.
    # Chưa có file thì convert_all() in "⚠ thiếu ... — bỏ qua" rồi chạy tiếp.
    "nghi_dinh_01_2021.md": {
        "out": "legal/nghi-dinh-01-2021-nd-cp.md",
        "doc_title": "Nghị định 01/2021/NĐ-CP về đăng ký doanh nghiệp",
        "doc_number": "01/2021/NĐ-CP",
        "url": "https://thuvienphapluat.vn/van-ban/Doanh-nghiep/Nghi-dinh-01-2021-ND-CP-dang-ky-doanh-nghiep-427225.aspx",
        "structured": True,
    },
    "tiktok_seller_policy.md": {
        "out": "news/tiktok-seller-terms.md",
        "doc_title": "Điều khoản dịch vụ dành cho Người bán trên TikTok Shop",
        "doc_number": "",
        "url": "https://seller-vn.tiktok.com/university/essay?knowledge_id=2581017870255874&lang=vi-VN",
        "structured": False,  # dùng mục đánh số, không có "Điều N"
    },
    "shopee_product_policy.md": {
        "out": "news/shopee-product-listing.md",
        "doc_title": "Quy định về đăng bán sản phẩm trên Shopee",
        "doc_number": "",
        "url": "https://help.shopee.vn/portal/4/article/77246",
        "structured": False,
    },
}


# =============================================================================
# BƯỚC 2 — Cắt rìa
# =============================================================================

# Mốc rác ở đuôi — TẤT CẢ đều lấy từ quan sát trên bản cào thật, không đoán.
#
# Chia hai nhóm vì độ mơ hồ khác nhau:
#   - Nhóm NGUYÊN DÒNG: từ ngắn có thể xuất hiện hợp lệ giữa bài ("Ghi chú",
#     "Ý kiến"), nên chỉ tính là rác khi đứng MỘT MÌNH trọn một dòng.
#   - Nhóm TIỀN TỐ: cụm dài, không thể nhầm.
_RAC_NGUYEN_DONG = re.compile(
    r"^\s*(Lưu\s*trữ|Ghi\s*chú|Ý\s*kiến|Facebook|Email|In|Tải\s*về"
    r"|Bản\s*Tiếng\s*Anh|Lược\s*đồ|Tải\s*văn\s*bản)\s*$",
    re.IGNORECASE,
)

_RAC_TIEN_TO = re.compile(
    r"^\s*("
    # Widget "đăng ký nhận thông báo" của thuvienphapluat
    r"Họ\s*&\s*Tên\s*:|Email\s*nhận\s*thông\s*báo|Thông\s*báo\s*cho\s*tôi\s*khi"
    r"|Ghi\s*chú\s*cho\s*Văn\s*bản"
    # Khối điều hướng / bài liên quan
    r"|Bài\s*liên\s*quan|Hỏi\s*đáp\s*pháp\s*luật|Bản\s*án\s*liên\s*quan"
    r"|MỤC\s*LỤC\s*VĂN\s*BẢN|In\s*mục\s*lục|PHÁP\s*LUẬT\s*DOANH\s*NGHIỆP"
    r"|THƯ\s*VIỆN\s*PHÁP\s*LUẬT|Trang\s*Thông\s*tin\s*điện\s*tử"
    # Tooltip so sánh văn bản (chỉ có ở bản cào LDN)
    r"|Xem\s*nội\s*dung\s*VB|Click\s*vào\s*để\s*xem|Tải\s*biểu\s*mẫu"
    r"|Chú\s*thích\s*:|Rà\s*chuột\s*vào"
    r")",
    re.IGNORECASE,
)

# ⚠️ BẢN DỊCH TIẾNG ANH đính kèm trong cùng trang — thứ nguy hiểm nhất ở đây.
#
# Đo trên bản cào: LDN 2020 có bản tiếng Anh chèn từ dòng 7620 (ngay sau Điều 218
# ở dòng 7573) và chiếm gần nửa file; NĐ 52 có bản tiếng Anh ở đuôi. Nạp nhầm vào
# kho tiếng Việt thì BM25 không bao giờ khớp — hỏng HOÀN TOÀN IM LẶNG, không có
# triệu chứng nào để lần ra.
#
# Tách riêng khỏi `_RAC_TIEN_TO` vì quét theo phạm vi khác: nhóm rác thường chỉ
# quét sau Điều lớn nhất, còn nhóm này quét toàn bộ phần sau Điều đầu tiên (bản
# dịch có thể nằm giữa file chứ không riêng đuôi). Các cụm dưới đây không thể
# xuất hiện trong thân văn bản tiếng Việt nên quét rộng vẫn an toàn.
_BAN_DICH_EN = re.compile(
    r"^\s*(THE\s*GOVERNMENT|THE\s*NATIONAL\s*ASSEMBLY|THE\s*MINISTRY"
    r"|SOCIALIST\s*REPUBLIC|Independence\s*-\s*Freedom"
    r"|LAW\s*ON\s+[A-Z]|DECREE\s*$|CIRCULAR\s*$|Pursuant\s+to\s+the\s+Constitution"
    r"|Article\s+\d+\.\s*[A-Z])",
    re.IGNORECASE,
)


def _la_rac(line: str) -> bool:
    return bool(_RAC_NGUYEN_DONG.match(line) or _RAC_TIEN_TO.match(line))


# Rác giao diện có thể nằm BẤT KỲ ĐÂU giữa bài, không riêng đầu/cuối.
#
# Bản cào thuvienphapluat lặp lại khối header + form đăng nhập ở giữa văn bản,
# nên cắt rìa không đủ. Phát hiện thật khi chạy Task 9: kết quả top-1 cho câu
# "Điều 35 Nghị định 52/2013/NĐ-CP" lại là
# "Ông Bà Anh Chị Tên Thành Viên: Mật khẩu: E-mail:...".
#
# Toàn bộ cụm dưới đây là chrome của trang, không bao giờ xuất hiện trong văn
# bản quy phạm pháp luật, nên lọc theo dòng là an toàn.
_RAC_GIAO_DIEN = re.compile(
    r"^\s*("
    r"Mật\s*khẩu\s*:|Tên\s*Thành\s*Viên\s*:|E-?mail\s*:|ĐT\s*di\s*động\s*:"
    r"|Ông\s*Bà\s*Anh\s*Chị|Bạn\s*chưa\s*là\s*thành\s*viên"
    r"|Đăng\s*ký\s*mới|ĐĂNG\s*KÝ\s*THÀNH\s*VIÊN|Đăng\s*nhập\b"
    r"|Vui\s*lòng\s*nhập\s*thêm|Tra\s*cứu\s*nhanh"
    r"|Số\s*Hiệu,\s*Tiêu\s*đề|Văn\s*bản\s*PL\s*Dự\s*thảo"
    r"|Thời\s*điểm\s*Áp\s*dụng\s*Tình\s*trạng"
    r"|Lao\s*Động\s*Tiền\s*Lương\s*X"
    r")",
    re.IGNORECASE,
)

# Dòng bảng markdown do widget form sinh ra — toàn dấu | và khoảng trắng.
_DONG_BANG = re.compile(r"^\s*\|[\s|]*\|?\s*$|^\s*\|.*\|\s*$")


# Rác PHÂN TRANG của bản PDF Công báo (nguồn mới từ Task 1, khác hẳn bản cào HTML):
# header lặp lại ở mỗi trang và số trang đứng một mình.
#
# KHÔNG gộp vào `_la_rac()` — hàm đó dùng để tìm MỐC CẮT, mà header Công báo có
# ngay từ trang đầu; lấy nó làm mốc sẽ chặt cụt gần hết văn bản. Phải lọc theo
# từng dòng như `_RAC_GIAO_DIEN`.
_HEADER_CONG_BAO = re.compile(r"^\s*CÔNG\s*BÁO\s*/\s*Số\b.*$", re.IGNORECASE)
_SO_TRANG = re.compile(r"^\s*\d{1,3}\s*$")


def bo_rac_phan_trang(lines: list[str]) -> list[str]:
    """Bỏ header Công báo và số trang của văn bản bóc từ PDF.

    Tự nhận biết nguồn: chỉ chạy khi đếm được ≥3 dòng header Công báo. Làm vậy để
    KHÔNG đụng tới các file cào từ HTML — ở đó một dòng chỉ có số hoàn toàn có thể
    là nội dung thật, xoá đi là mất dữ liệu. Có header Công báo lặp lại thì chắc
    chắn là bản PDF công báo, lúc đó dòng chỉ có số luôn là số trang.
    """
    if sum(1 for l in lines if _HEADER_CONG_BAO.match(l)) < 3:
        return lines
    return [l for l in lines if not (_HEADER_CONG_BAO.match(l) or _SO_TRANG.match(l))]


def cat_ria(lines: list[str], structured: bool) -> list[str]:
    """Bỏ nav ở đầu và widget ở cuối.

    Với văn bản QPPL: giữ từ mốc "Điều" ĐẦU TIÊN tới mốc rác đầu tiên đứng SAU
    mốc "Điều" cuối cùng. Không cắt tại mốc rác bất kỳ vì cụm "THƯ VIỆN PHÁP LUẬT"
    cũng xuất hiện rải rác giữa bài dưới dạng watermark.
    """
    moc_dieu = [
        (i, int(m.group(1).rstrip("abcdefghijklmnopqrstuvwxyz") or 0))
        for i, l in enumerate(lines)
        if (m := ARTICLE_RE.match(l))
    ]
    dau = moc_dieu[0][0] if (structured and moc_dieu) else 0
    cuoi = len(lines)

    if moc_dieu:
        # Neo vào Điều có SỐ LỚN NHẤT, không phải Điều cuối theo VỊ TRÍ.
        #
        # Bản cào LDN có một "Điều 19" bị trích dẫn ở dòng 14814 — nằm sâu trong
        # phần phụ lục sau bản dịch tiếng Anh. Neo vào vị trí cuối thì mốc cắt
        # rơi xuống tận đó và giữ lại nguyên nửa file rác (đo được: giảm 15%
        # thay vì 58%). Neo vào số lớn nhất (Điều 218, dòng 7573) thì đúng.
        neo = max(moc_dieu, key=lambda x: x[1])[0]
        for i in range(neo, len(lines)):
            if _la_rac(lines[i]):
                cuoi = i
                break

        # Bản dịch tiếng Anh quét trên toàn bộ phần sau Điều đầu tiên, vì nó có
        # thể nằm GIỮA file. Lấy mốc nào đến trước.
        for i in range(dau, cuoi):
            if _BAN_DICH_EN.match(lines[i]):
                cuoi = i
                break

    giu = lines[dau:cuoi]
    # Bỏ nốt dòng bảng (widget form render thành bảng) và rác giao diện lẫn giữa
    return [
        l for l in giu
        if not _DONG_BANG.match(l) and not _RAC_GIAO_DIEN.match(l)
    ]


# =============================================================================
# BƯỚC 3 — Khử mục lục
# =============================================================================

def khu_muc_luc(lines: list[str]) -> list[str]:
    """Bỏ bản mục lục, giữ thân bài.

    Cách nhận biết KHÔNG dựa vào vị trí (mục lục không phải lúc nào cũng ở đầu)
    mà dựa vào **lượng nội dung đi sau mỗi mốc Điều**: mục lục chỉ có tiêu đề,
    thân bài có nội dung thật. Với mỗi số Điều, giữ lần xuất hiện có nhiều nội
    dung nhất.

    Vì sao phải bỏ: mục lục toàn từ khoá nên khớp RẤT tốt với câu hỏi và xếp hạng
    cao, nhưng không trả lời được gì. Đây là kiểu nhiễu tệ nhất — không phải rác
    dễ thấy mà là mồi nhử.
    """
    moc = [(i, ARTICLE_RE.match(l)) for i, l in enumerate(lines)]
    moc = [(i, m.group(1)) for i, m in moc if m]
    if not moc:
        return lines

    # Kích thước khối nội dung của mỗi mốc = tới mốc kế tiếp
    khoi: list[tuple[int, str, int, int]] = []   # (dong_bat_dau, so_dieu, dong_ket, do_dai)
    for k, (i, so) in enumerate(moc):
        ket = moc[k + 1][0] if k + 1 < len(moc) else len(lines)
        do_dai = sum(len(l.strip()) for l in lines[i:ket])
        khoi.append((i, so, ket, do_dai))

    # Với mỗi số Điều, chọn khối dài nhất; các khối còn lại là mục lục/trích dẫn
    tot_nhat: dict[str, tuple[int, int]] = {}   # so_dieu -> (dong_bat_dau, do_dai)
    for i, so, _, do_dai in khoi:
        if so not in tot_nhat or do_dai > tot_nhat[so][1]:
            tot_nhat[so] = (i, do_dai)

    bo: set[int] = set()
    for i, so, ket, _ in khoi:
        if tot_nhat[so][0] != i:
            bo.update(range(i, ket))
        elif is_quoted_article(lines[i]):
            # Điều bị TRÍCH vào thân văn bản sửa đổi — không phải điều của văn bản này
            bo.update(range(i, ket))

    return [l for i, l in enumerate(lines) if i not in bo]


# =============================================================================
# BƯỚC 4 — Ghép dòng vụn
# =============================================================================

# Dòng bắt đầu bằng các mốc này là mở đầu ý mới → KHÔNG ghép vào dòng trước.
_MOC_CAU_TRUC = re.compile(
    r"^\s*(Điều\s+\d|Chương\s+[IVXLCDM\d]|Mục\s+\d|Phần\s+[IVXLCDM\d]"
    r"|\d{1,3}\s*[.)]\s|[a-vxyđ]\s*[.)]\s|[A-Z]\s*[.)]\s|-\s|\*\s|#)",
)


def ghep_dong_vun(lines: list[str]) -> list[str]:
    """Nối dòng bị thẻ <span> cắt rời thành câu liền mạch.

    Điều kiện ghép: dòng hiện tại KHÔNG kết thúc bằng dấu kết câu, VÀ dòng sau
    KHÔNG mở đầu một ý mới. Hai điều kiện cùng lúc mới ghép — chỉ dùng một điều
    kiện sẽ nuốt mất ranh giới giữa các khoản.
    """
    ra: list[str] = []
    for dong in lines:
        s = dong.strip()
        if not s:
            if ra and ra[-1] != "":
                ra.append("")
            continue
        if (
            ra
            and ra[-1]
            and not re.search(r"[.;:!?]\s*$", ra[-1])
            and not _MOC_CAU_TRUC.match(s)
            and not ARTICLE_RE.match(ra[-1])
        ):
            ra[-1] = f"{ra[-1]} {s}"
        else:
            ra.append(s)
    return ra


# =============================================================================
# Trích metadata từ khối đầu bản cào
# =============================================================================

def doc_metadata(raw: str) -> dict:
    """Bóc 'Ngày ban hành: / 17/06/2020' ở khối header của thuvienphapluat.

    Định dạng là nhãn ở một dòng, giá trị ở dòng kế. Trả {} nếu không có khối này
    (bản cào TikTok/Shopee không có).
    """
    lines = [l.strip() for l in raw.split("\n")[:60]]
    ra: dict[str, str] = {}
    nhan = {
        "Ngày ban hành:": "issued_date",
        "Ngày hiệu lực:": "effective_date",
        "Số hiệu:": "doc_number",
    }
    for i, l in enumerate(lines[:-1]):
        if l in nhan:
            gia_tri = lines[i + 1].strip()
            khoa = nhan[l]
            ra[khoa] = parse_vn_date(gia_tri) or gia_tri if "date" in khoa else gia_tri
    return ra


# =============================================================================
# Pipeline chính
# =============================================================================

def lam_sach(raw: str, structured: bool, tu_vung: set[str]) -> str:
    """Chạy đủ 5 bước trên một văn bản."""
    # Bước 1 — NFC. Bắt buộc với tiếng Việt: "ệ" có 2 cách mã hoá, không chuẩn
    # hoá thì 2 chuỗi trông y hệt nhau lại không bằng nhau và BM25 khớp trượt.
    text = unicodedata.normalize("NFC", raw)
    lines = text.split("\n")

    lines = cat_ria(lines, structured)          # Bước 2
    # Bước 2b — rác phân trang của bản bóc từ PDF. Phải chạy TRƯỚC bước 3 và 4:
    # header Công báo chen vào giữa hai mốc Điều sẽ làm bước 3 đếm sai độ dài
    # khối nội dung, còn bước 4 thì dán nó dính vào câu bên cạnh.
    lines = bo_rac_phan_trang(lines)
    if structured:
        lines = khu_muc_luc(lines)              # Bước 3
    lines = ghep_dong_vun(lines)                # Bước 4

    # Lọc rác giao diện LẦN HAI, sau khi ghép dòng.
    # Bước 4 dán các mảnh rác còn sót thành một dòng dài MỚI, mà dòng mới đó
    # không tồn tại lúc lọc lần đầu nên lọt lưới. Lần này khớp theo cụm đặc
    # trưng ở BẤT KỲ vị trí nào trong dòng — các cụm dưới đây không bao giờ có
    # trong văn bản quy phạm pháp luật.
    lines = [
        l for l in lines
        if not _RAC_GIAO_DIEN.match(l)
        and not any(
            cum in l
            for cum in ("THƯ VIỆN PHÁP LUẬT", "Đăng nhập bằng Google",
                        "Đang tải văn bản", "Thỏa Ước Dịch Vụ")
        )
    ]

    text = "\n".join(lines)
    text = fix_split_syllables(text, tu_vung)   # Bước 5

    # Bước 6 — gộp khoảng trắng thừa. PDF căn đều hai bên giãn chữ bằng cách chèn
    # nhiều dấu cách ("Bảo  hiểm  nhân  thọ"), bóc ra thì giữ nguyên. Tokenizer
    # BM25 tách theo \w+ nên không sai, nhưng chuỗi này đi thẳng vào prompt của
    # LLM và hiện trên UI nguồn trích dẫn, để nguyên trông như lỗi hiển thị.
    text = re.sub(r"[ \t]{2,}", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


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
