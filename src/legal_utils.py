"""Nền tảng dùng chung cho mọi thao tác trên văn bản pháp luật Việt Nam.

Module này được **port từ dự án P-185** (`P-185/src/core/legal_utils.py`) — bộ hàm
đã chạy thật trên kho 19.295 điều khoản pháp luật thuế. Giữ nguyên phần lớn logic
và các docstring giải thích *vì sao* từng quyết định, vì mỗi ràng buộc trong đây
đều đến từ một lỗi đã gặp trên dữ liệu thật.

Lý do gom về một chỗ thay vì để mỗi Task tự viết: `normalize_doc_number` phải cho
ra **đúng cùng một chuỗi** ở lúc index (Task 4) và lúc truy vấn (Task 5/9) — lệch
một ký tự là không bao giờ tìm thấy chunk, mà lỗi đó lại im lặng (chỉ ra kết quả
rỗng, không ném exception).
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

# ── Chuẩn hoá số hiệu văn bản ──────────────────────────────────────────────


def normalize_doc_number(raw: str | None) -> str:
    """Chuẩn hoá số hiệu văn bản thành `doc_id` dùng làm khoá.

    "01/2021/NĐ-CP"  → "01_2021_ND-CP"
    "40/2021/TT-BTC" → "40_2021_TT-BTC"
    "59/2020/QH14"   → "59_2020_QH14"

    Xoá sạch khoảng trắng bên trong chứ không chỉ gom lại: dữ liệu crawl có
    "05/ 2000/TT-BTC" và "05/2005/TT- BTC" do lỗi tách chữ. Số hiệu văn bản không
    bao giờ chứa khoảng trắng thật nên xoá hết là an toàn.
    """
    if not raw:
        return ""
    s = unicodedata.normalize("NFC", raw.strip())
    s = s.replace("/", "_")
    s = s.replace("NĐ", "ND").replace("Nđ", "ND").replace("nđ", "ND")
    s = s.replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", "", s)


def slugify(text: str, max_len: int = 40) -> str:
    """Rút gọn chuỗi thành mảnh an toàn để ghép vào id (bỏ dấu, chỉ [a-z0-9_])."""
    s = unicodedata.normalize("NFD", text or "")
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    s = s.replace("đ", "d").replace("Đ", "D")
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s).strip("_").lower()
    return s[:max_len] or "unknown"


def make_provision_id(doc_id: str, kind: str, num) -> str:
    """Sinh khoá cho một điều khoản. `kind` ∈ article | clause | chunk | section.

    Đây là khoá **khử trùng** khi gộp kết quả BM25 + vector ở Task 7/9. Khử theo
    `content` là sai: hai chunk con của cùng một Điều chỉ khác nhau vài ký tự vẫn
    bị coi là hai kết quả khác nhau.
    """
    prefix = {
        "article": "dieu",
        "clause": "khoan",
        "chunk": "phan",
        "section": "muc",
    }.get(kind, kind)
    return f"{doc_id}__{prefix}_{num}"


# ── Ngày tháng ─────────────────────────────────────────────────────────────


def parse_vn_date(raw: str | None) -> str | None:
    """'17/06/2020' → '2020-06-17'. Trả None nếu không nhận dạng được.

    Dữ liệu Việt Nam ghi dd/mm/yyyy chứ không phải ISO. Trả ISO vì chuỗi ngày ISO
    so sánh đúng thứ tự, còn dd/mm/yyyy thì không.
    """
    if not raw:
        return None
    raw = raw.strip()
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", raw)
    if m:
        day, month, year = m.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"
    if re.match(r"\d{4}-\d{2}-\d{2}", raw):
        return raw[:10]
    return None


# ── Trích thông tin từ tiêu đề / nội dung ──────────────────────────────────

# Mốc bắt đầu một Điều. Dùng chung cho cả bước cắt chunk (Task 4) lẫn bước dọn
# (Task 3), nên định nghĩa một lần ở đây.
ARTICLE_RE = re.compile(r"^\s*Điều\s+(\d+[a-zA-Z]?)\s*[.:]?\s*(.*)$")


def extract_article_num(title: str | None) -> str | None:
    """'Điều 87. Hồ sơ đăng ký hộ kinh doanh' → '87'; giữ cả hậu tố chữ ('12a')."""
    m = re.search(r"[Đđ]iều\s+(\d+[a-zA-Z]?)", title or "")
    return m.group(1) if m else None


# Bắt số hiệu văn bản được dẫn chiếu trong nội dung:
#   "theo Nghị định 52/2013/NĐ-CP", "Thông tư số 40/2021/TT-BTC"
_LOAI_VB = (
    r"(?:Nghị\s*định|Thông\s*tư(?:\s*liên\s*tịch)?|Luật|Quyết\s*định|Pháp\s*lệnh"
    r"|Nghị\s*quyết|Chỉ\s*thị|Văn\s*bản\s*hợp\s*nhất)"
)

_CITATION_RE = re.compile(
    _LOAI_VB + r"(?:\s+số)?\s+" + r"(\d+/\d{4}/[A-ZĐa-zđ\-]+\d*)",
    re.IGNORECASE,
)


def extract_citations(text: str | None) -> list[str]:
    """Trích số hiệu các văn bản được dẫn chiếu trong nội dung (dạng thô).

    Gọi `normalize_doc_number` khi cần dùng làm khoá. `sorted` để kết quả ổn định
    giữa các lần chạy — `set()` không đảm bảo thứ tự.
    """
    if not text:
        return []
    return sorted(set(_CITATION_RE.findall(text)))


# ── Chuẩn hoá câu hỏi ──────────────────────────────────────────────────────
#
# Người Việt hỏi luật gần như luôn viết tắt ("thuế TNCN", "NĐ 52"), trong khi văn
# bản luật viết đầy đủ. BM25 khớp theo token nên "TNCN" KHÔNG BAO GIỜ khớp
# "thu nhập cá nhân" — câu hỏi demo flagship của nhóm dính đúng lỗi này.
#
# Đặt ở đây (không phải trong task5 hay task9) vì CẢ HAI đều phải dùng, mà hai
# bản sao lệch nhau là kiểu lỗi im lặng nguy hiểm nhất.
#
# Dùng \b hai đầu để "CP" không nuốt chữ trong "CPTPP" hay "cấp".
ABBREV_MAP = {
    # Loại văn bản
    r"\bNĐ\b": "Nghị định",
    r"\bTT\b": "Thông tư",
    r"\bQĐ\b": "Quyết định",
    r"\bNQ\b": "Nghị quyết",
    r"\bVBHN\b": "Văn bản hợp nhất",
    # Thuế — nhóm quan trọng nhất với chủ đề này
    r"\bGTGT\b": "giá trị gia tăng",
    r"\bTNCN\b": "thu nhập cá nhân",
    r"\bTNDN\b": "thu nhập doanh nghiệp",
    r"\bVAT\b": "thuế giá trị gia tăng",
    r"\bMST\b": "mã số thuế",
    r"\bHĐĐT\b": "hoá đơn điện tử",
    # Doanh nghiệp
    r"\bTNHH\b": "trách nhiệm hữu hạn",
    r"\bDN\b": "doanh nghiệp",
    r"\bDNNN\b": "doanh nghiệp nhà nước",
    r"\bHKD\b": "hộ kinh doanh",
    r"\bĐKKD\b": "đăng ký kinh doanh",
    r"\bGPKD\b": "giấy phép kinh doanh",
    # Thương mại điện tử
    r"\bTMĐT\b": "thương mại điện tử",
    r"\bBHXH\b": "bảo hiểm xã hội",
    # Cơ quan
    r"\bBTC\b": "Bộ Tài chính",
    r"\bBCT\b": "Bộ Công Thương",
    r"\bUBND\b": "Ủy ban nhân dân",
    r"\bCP\b": "Chính phủ",
}

# Khẩu ngữ → thuật ngữ pháp lý. THÊM biến thể chứ KHÔNG thay từ gốc: "đóng thuế"
# vẫn khớp được vài chỗ trong kho, thay đi là mất tín hiệu.
SYNONYM_MAP = {
    "đóng thuế": "nộp thuế",
    "quên nộp": "chậm nộp",
    "nộp muộn": "chậm nộp",
    "nộp trễ": "chậm nộp",
    "bị phạt": "xử phạt vi phạm hành chính",
    "hoá đơn đỏ": "hoá đơn giá trị gia tăng",
    "hóa đơn đỏ": "hoá đơn giá trị gia tăng",
    "mở công ty": "thành lập doanh nghiệp",
    "lập công ty": "thành lập doanh nghiệp",
}

_NHIEU_KHOANG_TRANG = re.compile(r"\s+")


def normalize_query(query: str) -> str:
    """Bung viết tắt + thêm biến thể pháp lý cho khớp cách viết trong văn bản.

    "Bán trên TikTok Shop bao nhiêu thì nộp thuế TNCN và GTGT?"
    → "... thuế thu nhập cá nhân và giá trị gia tăng?"

    Chuẩn hoá NFC trước: tiếng Việt có hai cách mã hoá cho cùng một ký tự ("ệ"
    dựng sẵn và tổ hợp), không chuẩn hoá thì hai chuỗi trông y hệt mà `!=`.
    """
    if not query:
        return ""
    q = unicodedata.normalize("NFC", query)

    # CHE SỐ HIỆU VĂN BẢN TRƯỚC KHI BUNG VIẾT TẮT.
    # Không che thì `\bNĐ\b` và `\bCP\b` khớp ngay bên trong "52/2013/NĐ-CP" và
    # biến nó thành "52/2013/Nghị định-Chính phủ" — số hiệu bị phá, mọi phép tra
    # theo doc_id sau đó đều trượt. Đã gặp thật khi chạy Task 9.
    che: list[str] = []

    def _che(m: re.Match) -> str:
        che.append(m.group(0))
        return f"\x00{len(che) - 1}\x00"

    q = _DOC_NUM_RE.sub(_che, q)

    for pattern, replacement in ABBREV_MAP.items():
        q = re.sub(pattern, replacement, q)

    for i, goc in enumerate(che):
        q = q.replace(f"\x00{i}\x00", goc)

    thap = q.lower()
    them = [v for k, v in SYNONYM_MAP.items() if k in thap and v.lower() not in thap]
    if them:
        q = f"{q} {' '.join(them)}"
    return _NHIEU_KHOANG_TRANG.sub(" ", q).strip()


# Số hiệu văn bản: 3 đoạn (52/2013/NĐ-CP) hoặc 2 đoạn (03/VBHN-VPQH).
# Loại `*` và `_` khỏi lớp ký tự: LLM viết markdown nên số hiệu hay nằm trong
# `**52/2013/NĐ-CP**`; không loại thì bắt được "52/2013/NĐ-CP**" và mọi phép tra
# sau đó đều trượt, nhìn hệt như LLM bịa số hiệu.
_DOC_NUM_RE = re.compile(r"(\d+/\d{4}/[^\s,;)*_]+|\d+/[A-Za-zĐđ][^\s,;)*_]*)")


def extract_doc_id(query: str) -> str:
    """Trích số hiệu văn bản từ câu hỏi, trả dạng đã chuẩn hoá; "" nếu không có.

    "Điều 35 Nghị định 52/2013/NĐ-CP quy định gì?" → "52_2013_ND-CP"
    """
    m = _DOC_NUM_RE.search(query or "")
    return normalize_doc_number(m.group(1).rstrip(".,;:?!")) if m else ""


# ── Sửa lỗi âm tiết bị tách khi crawl ──────────────────────────────────────

# Một âm tiết bị tách làm đôi khi crawl: "khai thu ế", "giá tr ị", "s ố".
# Phần đuôi luôn là 1 ký tự nguyên âm có dấu.
_TACH_AM_TIET = re.compile(
    r"(\w+)\s+([àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệ"
    r"ìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ])\b"
)


def build_vocabulary(texts: list[str], min_dem: int = 2) -> set[str]:
    """Từ vựng lấy từ chính corpus, chỉ giữ từ xuất hiện ít nhất `min_dem` lần.

    Ngưỡng 2 để một lần gõ sai không tự biến thành "từ hợp lệ" rồi kéo theo các
    chỗ khác bị ghép sai theo.
    """
    dem: Counter[str] = Counter()
    for t in texts:
        dem.update(w.lower() for w in re.findall(r"\w+", t or "") if len(w) > 1)
    return {w for w, n in dem.items() if n >= min_dem}


def fix_split_syllables(text: str, tu_vung: set[str]) -> str:
    """Ghép lại âm tiết bị tách, CHỈ khi dạng ghép có thật trong từ vựng.

    Dữ liệu crawl có "Nộp hồ sơ khai thu ế" thay vì "khai thuế". BM25 tách token
    theo khoảng trắng nên "thuế" trong câu hỏi không bao giờ khớp "thu ế" trong
    văn bản — điều khoản đúng vẫn nằm đó mà không tìm ra được, và không có lỗi
    nào để lần.

    Ràng buộc "dạng ghép phải có trong từ vựng" là để không phá các cụm viết
    đúng: "có ý", "chú ý" ghép lại thành "cóý", "chúý" — không phải từ nên giữ
    nguyên.
    """
    if not text:
        return text

    def _thay(m: re.Match) -> str:
        ghep = m.group(1) + m.group(2)
        return ghep if ghep.lower() in tu_vung else m.group(0)

    return _TACH_AM_TIET.sub(_thay, text)


# ── Lọc điều khoản giả ─────────────────────────────────────────────────────
#
# Văn bản sửa đổi trích nguyên điều bị sửa vào thân mình, và phụ lục/mẫu biểu có
# "Điều 1, 2, 3" riêng. Chúng lọt vào chỉ mục và chen lên trên điều khoản thật.

_MANH_SUA_DOI = re.compile(
    r"(được\s+)?(sửa\s*đổi|bổ\s*sung|thay\s*thế|bãi\s*bỏ|huỷ\s*bỏ|hủy\s*bỏ)|như\s*sau",
    re.IGNORECASE,
)


def is_quoted_article(title: str | None) -> bool:
    """Tiêu đề này là mảnh câu trích dẫn chứ không phải tiêu đề Điều thật?

    P-185 đã thu hẹp hàm này **ba lần vì chặn quá tay** — ghi lại để không nới ra:
    bắt mọi dòng kết thúc "như sau:" là sai (Điều 1 của quyết định hay viết vậy);
    bắt mọi dòng khớp "(sửa đổi|bổ sung).{0,40}Điều \\d" còn sai nặng hơn, nó khớp
    đúng "Điều 1. Sửa đổi, bổ sung một số điều của Nghị định …".

    Còn lại hai dấu hiệu, đều lấy từ bằng chứng verbatim trên dữ liệu thật.
    """
    t = (title or "").strip()
    if t[:1] in ('"', "“", "‘"):
        return True
    m = ARTICLE_RE.match(t)
    phan_ten = (m.group(2) if m else t).strip()
    if re.fullmatch(r"như\s*sau\s*:?", phan_ten, re.IGNORECASE):
        return True
    return bool(phan_ten) and phan_ten[0].islower() and bool(_MANH_SUA_DOI.search(phan_ten))


# ── Suy ra đối tượng áp dụng (K4 Variant) ──────────────────────────────────

_ROLE_HO_KD = re.compile(
    r"hộ\s*kinh\s*doanh|cá\s*nhân\s*kinh\s*doanh|hộ\s*cá\s*thể", re.IGNORECASE
)
_ROLE_DN = re.compile(
    r"doanh\s*nghiệp|công\s*ty\s*(trách\s*nhiệm|cổ\s*phần|hợp\s*danh)|vốn\s*điều\s*lệ",
    re.IGNORECASE,
)


def infer_customer_role(text: str, doc_title: str = "") -> str:
    """Suy ra `customer_role` cho một chunk: ho_kinh_doanh | doanh_nghiep | both.

    Đọc cả nội dung chunk lẫn tên văn bản. Khi cả hai nhóm cùng xuất hiện (hoặc
    không nhóm nào) thì trả "both" — sai theo hướng **rộng** còn hơn gán hẹp rồi
    lọc mất điều khoản đúng.
    """
    blob = f"{doc_title}\n{text}"
    ho = bool(_ROLE_HO_KD.search(blob))
    dn = bool(_ROLE_DN.search(blob))
    if ho and not dn:
        return "ho_kinh_doanh"
    if dn and not ho:
        return "doanh_nghiep"
    return "both"
