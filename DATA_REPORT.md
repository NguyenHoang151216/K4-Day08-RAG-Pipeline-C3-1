# BÁO CÁO TẦNG DỮ LIỆU — bàn giao cho tầng truy vấn

> **Đọc ai:** Đức Anh (Task 5 semantic, Task 9 pipeline) và Kỳ Anh (Task 6 BM25, Task 7 rerank, Task 8 vectorless).
> **Đọc phần nào trước:** thẳng xuống **Mục 4 — Phương pháp truy vấn phải code**. Đó là phần quyết định bạn viết gì.
>
> Trạng thái: **đợt A** (nguồn, schema, phương pháp, cạm bẫy). Mục 2 và 5 điền ở CP3 khi đã có `chroma_db/`.

---

## 1. Nguồn dữ liệu

Chủ đề: **Trợ lý Pháp lý Khởi nghiệp & Thương mại điện tử** — tra cứu quy định khi bán hàng trên TikTok Shop/Shopee, đăng ký hộ kinh doanh, thành lập công ty TNHH/Cổ phần.

### 1.1 Văn bản quy phạm pháp luật → `data/landing/legal/`

| # | Văn bản | Trả lời được câu hỏi gì | Trạng thái |
|---|---|---|---|
| 1 | **Luật Doanh nghiệp 2020** (59/2020/QH14) | Thành lập TNHH/CP, loại hình, vốn điều lệ, người đại diện | ✅ đã có, 218/218 Điều |
| 2 | **Nghị định 52/2013/NĐ-CP** về TMĐT | Nghĩa vụ người bán trên sàn, website TMĐT | ✅ đã có, 80/80 Điều |
| 3 | **Nghị định 01/2021/NĐ-CP** đăng ký doanh nghiệp | ⭐ Hồ sơ + thủ tục đăng ký **hộ kinh doanh** | ❌ chưa có nội dung |
| 4 | **Thông tư 40/2021/TT-BTC** | ⭐ Ngưỡng doanh thu chịu thuế GTGT/TNCN của hộ & cá nhân kinh doanh | ❌ chưa có nội dung |

### 🚨 Hai phát hiện chặn 2 câu demo flagship — đọc trước khi viết golden set

**(a) PDF trên chinhphu.vn là bản ký số QUÉT ẢNH, không bóc được chữ.**
Đã tải 4 tệp về `landing/legal/` (12,9 MB) và kiểm bằng `pypdf` — **cả 4 đều trả về 0 ký tự** trên 5 trang đầu:

| Tệp | Trang | Ký tự bóc được |
|---|---:|---:|
| `luat-doanh-nghiep-59-2020-qh14.pdf` | 70 | 0 |
| `luat-doanh-nghiep-59-2020-qh14-tiep.pdf` | 71 | 0 |
| `nghi-dinh-01-2021-nd-cp.pdf` | 47 | 0 |
| `chinhphu-vbpq-2021-01-so-1-signed-CHUA-XAC-MINH.pdf` | 8 | 0 |

`producer` của cả 4 tệp là **`Kodak Alaris Inc.`** — máy quét tài liệu. Metadata `title` chỉ chứa ngày, không có tên văn bản.

⚠️ **Danh tính 2 tệp thư mục 2021/01 chưa xác minh được.** Chúng lấy từ `datafiles.chinhphu.vn/cpp/files/vbpq/2021/01/{01,1}.signed.pdf`; ngày trong metadata (04/01/2021) khớp ngày ban hành NĐ 01/2021/NĐ-CP, và bản 47 trang hợp với một nghị định ~90 điều. Nhưng vì là ảnh quét nên **không đọc được chữ để xác nhận**, và không OCR. Bản 8 trang chắc chắn KHÔNG phải NĐ 01/2021 nên đã đổi tên theo đúng đường dẫn nguồn thay vì khẳng định sai — gắn nhãn sai cho văn bản pháp luật nguy hiểm hơn là thiếu tệp.

→ PDF chỉ dùng làm **bằng chứng nguồn**; nguồn CHỮ của pipeline là `data/raw_crawl/*.md`. **Không OCR** — OCR tiếng Việt trên bảng biểu và dấu thanh đủ kém để sinh ra điều khoản sai mà đọc vẫn hợp lý.
→ Hệ quả: **NĐ 01/2021 vẫn chưa có nội dung** trong corpus.

**(b) Cả hai văn bản còn thiếu ĐỀU ĐÃ HẾT HIỆU LỰC.**
Tra `th1nhng0/vietnamese-legal-documents` (CC-BY-4.0, nguồn gốc vbpl.vn — Bộ Tư pháp):

| Văn bản | id | Ban hành | Tình trạng hiệu lực |
|---|---|---|---|
| Nghị định 01/2021/NĐ-CP | 153870 | 04/01/2021 | **Hết hiệu lực toàn bộ** |
| Thông tư 40/2021/TT-BTC | 151002 | 01/06/2021 | **Hết hiệu lực một phần** |

Nếu cứ index hai bản này, RAG sẽ trả lời **trung thành với tài liệu nhưng sai thực tế** — đúng loại lỗi tệ nhất cho trợ lý pháp lý, vì nó trông hoàn toàn đáng tin. Phải tìm văn bản thay thế đang có hiệu lực trước khi nạp.

→ **Việc cho Trường (golden set):** *chưa viết câu hỏi về thuế hộ kinh doanh và thủ tục đăng ký hộ kinh doanh* cho tới khi mục này chuyển sang ✅. Các mảng trả lời được ngay: thành lập TNHH/CP, vốn điều lệ, người đại diện, nghĩa vụ người bán trên sàn, hàng cấm đăng bán.

**Vì sao phải có #3 và #4:** hai câu demo flagship của nhóm **không trả lời được** nếu thiếu chúng.

- *"Doanh thu bao nhiêu thì phải nộp thuế TNCN và GTGT?"* → nằm ở TT 40/2021, **không** nằm trong LDN hay NĐ 52.
- *"Hồ sơ thủ tục đăng ký hộ kinh doanh cá thể?"* → nằm ở NĐ 01/2021. **Luật Doanh nghiệp 2020 không điều chỉnh hộ kinh doanh.**

⚠️ **Cảnh báo hiệu lực:** ngưỡng doanh thu chịu thuế của hộ kinh doanh đã được nâng khỏi mức 100 triệu/năm cũ bởi Luật Thuế GTGT 2024. **Phải kiểm con số trong bản tải về**, đừng tin trí nhớ (kể cả của tôi). RAG trả lời "đúng theo tài liệu" nhưng tài liệu hết hiệu lực thì demo vẫn sai.

### 1.2 Quy định sàn TMĐT → `data/landing/news/`

| # | Nguồn | URL | Ghi chú |
|---|---|---|---|
| 5 | Điều khoản dịch vụ người bán TikTok Shop | `seller-vn.tiktok.com/university/essay?knowledge_id=2581017870255874` | Cập nhật 09/02/2026 |
| 6 | Quy định đăng bán sản phẩm trên Shopee | `help.shopee.vn/portal/4/article/77246` | Cập nhật 14/08/2024 |

Đây là **chính sách nền tảng, không phải văn bản QPPL** — nên xếp vào `news/` chứ không phải `legal/`. Phân biệt này quan trọng khi trích dẫn: quy định sàn không có giá trị pháp lý như nghị định.

### 1.3 Ghi chú về nguồn

`thuvienphapluat.vn` đặt `ClaudeBot: Disallow: /` trong `robots.txt` kèm `Content-Signal: ai-train=no`. Hai file `.md` của LDN 2020 và NĐ 52/2013 do **người tải tay**, không phải script cào. Mọi script tự động trong repo này lấy từ `vanban.chinhphu.vn` (`robots.txt` = `Allow: /`, có PDF ký số chính thức).

---

## 2. Kết quả làm sạch

*(điền ở CP3 — cần `data/standardized/` hoàn tất)*

Bảng audit **trước** khi dọn, đo bằng script trên bản crawl gốc:

| File | Ký tự | Điều | Trùng | Nhiễu đầu | Nhiễu cuối | Dòng vụn <40 | Âm tiết tách |
|---|---:|---|---:|---:|---:|---:|---:|
| `luat_doanh_nghiep_2020.md` | 728.430 | 218/218 ✓ | 55 | 60 dòng | 284 dòng | 50% | 97 |
| `nghi_dinh_52_2013.md` | 181.788 | 80/80 ✓ | 17 | 100 dòng | **2.919 dòng (60%)** | 56% | 15 |
| `tiktok_seller_policy.md` | 211.540 | — | — | tiêu đề lặp 3× | — | 59% | 145 |
| `shopee_product_policy.md` | 21.080 | — | — | — | — | 38% | 12 |

Bốn lớp nhiễu đã xử lý, theo thứ tự tác hại:

1. **Rác đầu/cuối** — nav site + form "Thông báo cho tôi khi Văn bản bị sửa đổi". NĐ 52 có 2.919 dòng rác sau Điều 80.
2. **Mục lục trùng thân bài** — nguy hiểm nhất. Mục lục toàn từ khoá nên **khớp rất tốt** với câu hỏi, xếp hạng cao, mà **không trả lời được gì**.
3. **Dòng vụn** — 50–59% dòng <40 ký tự do thẻ `<span>` bọc thuật ngữ. Làm hỏng splitter dựa trên `\n\n`.
4. **Âm tiết bị tách** — `"khai thu ế"` thay vì `"khai thuế"`. BM25 tách token theo khoảng trắng nên `"thuế"` trong câu hỏi **không bao giờ** khớp `"thu ế"` trong văn bản, và không có lỗi nào để lần.

---

## 3. Schema metadata — hợp đồng giữa Task 4 và Task 5/6/7/8/9

ChromaDB chỉ nhận scalar (`str`/`int`/`float`/`bool`), không nhận `list`/`dict`.

| Trường | Kiểu | Ví dụ thật | Dùng để làm gì |
|---|---|---|---|
| `source` | str | `nghi-dinh-01-2021-nd-cp.md` | tên file gốc |
| `type` | str | `legal` \| `news` | phân biệt QPPL vs chính sách sàn |
| `chunk_index` | int | `0` | thứ tự chunk trong văn bản |
| `doc_id` | str | `01_2021_ND-CP` | ⭐ khoá tra cứu chính xác theo số hiệu |
| `doc_title` | str | `Nghị định 01/2021/NĐ-CP` | hiển thị + citation |
| `doc_number` | str | `01/2021/NĐ-CP` | dạng gốc, giữ nguyên chữ Đ |
| `legal_ref` | str | `Điều 87` | ⭐ citation cấp điều khoản; `""` nếu không có |
| `provision_id` | str | `01_2021_ND-CP__dieu_87` | ⭐ khoá khử trùng khi gộp kết quả |
| `issued_date` | str | `2021-01-04` | ISO, để so sánh thứ tự |
| `effective_date` | str | `2021-01-04` | ngày có hiệu lực |
| `customer_role` | str | `ho_kinh_doanh`\|`doanh_nghiep`\|`both` | lọc theo đối tượng (K4 Variant) |
| `source_url` | str | `https://...` | dẫn nguồn |

**Ba trường phải dùng, không được bỏ qua:**

- **`provision_id`** — khoá khử trùng ở Task 7/9. Code mẫu trong `task7_reranking.py` khử theo `content`; **cách đó sai** khi hai chunk con của cùng một Điều khác nhau vài ký tự.
- **`legal_ref`** — cho phép Task 10 cite `[Nghị định 01/2021/NĐ-CP, Điều 87]` thay vì `[nd-01-2021.pdf]`. Với bài pháp lý đây là khác biệt giữa "chạy được" và "thuyết phục".
- **`doc_id`** — **phải sinh bằng đúng một hàm** ở cả lúc index lẫn lúc truy vấn: `legal_utils.normalize_doc_number()`. Lệch một ký tự là không bao giờ tìm thấy, mà lỗi đó **im lặng** — chỉ ra kết quả rỗng, không ném exception.

Dùng chung `src/legal_utils.py` (đã port từ P-185): `normalize_doc_number`, `make_provision_id`, `parse_vn_date`, `extract_article_num`, `extract_citations`, `ARTICLE_RE`.

### ⭐ Embedding model — ĐÃ ĐỔI, và có một hợp đồng bắt buộc

**Model đã chốt: `intfloat/multilingual-e5-small` (384 chiều, 471 MB), KHÔNG phải `BAAI/bge-m3`.**

Lý do không phải "mạng chậm" mà là chặn kỹ thuật cứng:

| | |
|---|---|
| Máy lab | `torch 2.5.1+cu121` · `transformers 5.14.1` · `sentence-transformers 5.6.1` |
| `BAAI/bge-m3` trên Hub | **chỉ có `pytorch_model.bin`, KHÔNG có `model.safetensors`** |
| `transformers` 5.x | chặn `torch.load` trên `.bin` khi `torch < 2.6` (CVE-2025-32434) → **ném lỗi ngay** |

Giữ bge-m3 thì mỗi người phải tải 200 MB–2,5 GB torch **cộng** 2,27 GB model, và có nguy cơ phá vỡ stack đang chạy tốt. `chroma_db/` lại nằm trong `.gitignore` nên **cả 5 người đều phải tự chạy `task4`** — mọi cách vá cục bộ đều vô nghĩa.

Ai có `torch>=2.6` muốn quay lại bge-m3 thì **không cần sửa code**:
```powershell
$env:EMBEDDING_MODEL="BAAI/bge-m3"; $env:EMBEDDING_DIM="1024"
```

#### 🔴 Hợp đồng bắt buộc cho Task 5 (Đức Anh)

Họ model E5 huấn luyện với **tiền tố bắt buộc**: `"query: "` cho câu hỏi, `"passage: "` cho tài liệu. Thiếu tiền tố thì model **vẫn chạy, vẫn trả kết quả, chỉ kém hơn** — không exception, không triệu chứng nào để lần ra.

Nên đừng gọi `get_embedding_model().encode()` trực tiếp. Dùng:

```python
from .task4_chunking_indexing import embed_query, get_collection

vec = embed_query(query)                      # tự gắn "query: "
res = get_collection().query(query_embeddings=[vec], n_results=top_k,
                             include=["documents", "metadatas", "distances"])
```

`embed_query()` và `embed_passages()` tự bật/tắt tiền tố theo tên model, nên nếu sau này đổi về bge-m3 thì code Task 5 **không phải sửa gì**.

> Triệu chứng khi gắn sai: điểm cosine của **mọi** câu đều thấp bất thường (<0,6) kể cả câu chắc chắn liên quan. Gặp thì xoá `chroma_db/` và index lại, đừng index đè.

### Chunking đã dùng — ảnh hưởng trực tiếp tới cách bạn viết retrieval

**Không cắt mù 800 ký tự.** Đáp án của một câu hỏi pháp lý gần như luôn nằm gọn trong **một Điều**.

```
Tầng 1 — cắt theo cấu trúc
    Văn bản QPPL : ^Điều\s+(\d+[a-z]?)  → mỗi Điều = 1 chunk
    TikTok/Shopee: mốc mục đánh số (^\d+\.\s, ^[A-Z]\.\s)

Tầng 2 — chỉ khi 1 Điều > 800 ký tự
    RecursiveCharacterTextSplitter(800, overlap=100)
    Mọi chunk con THỪA KẾ legal_ref của Điều cha
```

Hệ quả với bạn: **một `provision_id` có thể ứng nhiều chunk**. Khử trùng theo `provision_id` sẽ gộp chúng lại — đó là hành vi mong muốn khi đếm phiếu RRF, nhưng nhớ giữ lại chunk có điểm cao nhất chứ đừng lấy chunk đầu tiên.

---

## 4. ⭐ Phương pháp truy vấn phải code — có bằng chứng, không đoán

Bảng dưới **không phải lý thuyết**. Đo trên dự án P-185 (`D:\VinUni\BUILD_PHASE\P-185`), corpus pháp luật Việt Nam 19.295 điều khoản, bộ golden 35 câu + bộ đối chứng độc lập 16 câu:

| Chế độ | R@1 | R@5 | MRR | Coverage | Thời gian |
|---|---:|---:|---:|---:|---:|
| BM25 đơn lẻ | 0,020 | 0,080 | 0,063 | 0,726 | 2s |
| Vector đơn lẻ | 0,100 | 0,560 | 0,278 | 0,851 | 19s |
| **Hybrid (BM25+vector, RRF)** | 0,380 | 0,660 | 0,498 | **0,954** | 3s |
| Hybrid + HyDE | 0,380 | 0,740 | 0,513 | 0,937 | 35s |
| **Hybrid + rerank** | **0,440** | **0,800** | **0,591** | — | 6,8s/câu |

### (1) Hybrid + rerank là đích đến — R@5 0,800

Đúng kiến trúc lab yêu cầu (Task 5 + 6 + 7 + 9). Không cần sáng tạo thêm gì.

### (2) BM25 một mình rất yếu (R@5 0,080) nhưng KHÔNG được bỏ

Coverage của nó vẫn 0,726, và nó là **đường duy nhất** bắt được số hiệu văn bản — dense search trượt token số. Người dùng gõ `"Nghị định 52"`, `"Điều 87"`, `"Thông tư 40"` thì BM25 mới bắt chính xác. Vai trò của BM25 là **bổ khuyết**, không phải chủ lực.

→ **Kỳ Anh (Task 6):** đừng lo BM25 điểm thấp khi test riêng. Nó có việc riêng của nó.

### (3) ⭐ Chuẩn hoá câu hỏi là BẮT BUỘC, không phải bonus

Câu demo flagship của nhóm viết **"thuế TNCN và GTGT"**. Văn bản luật viết **"thu nhập cá nhân"**, **"giá trị gia tăng"**. BM25 tách token nên `"TNCN"` **không bao giờ** khớp `"thu nhập cá nhân"`.

Bỏ bước này thì câu demo chính của nhóm hỏng, mà hỏng im lặng — vẫn trả về kết quả, chỉ là kết quả sai.

→ **Đức Anh (Task 5):** viết `normalize_query()` và gọi nó **trước cả** `semantic_search` lẫn `lexical_search`. Lấy `ABBREV_MAP` của P-185 (`src/agents/tools/query_signals.py`) — đã có sẵn TNCN, GTGT, TNDN, VAT, NĐ, TT, DN, MST, BHXH, UBND…

Bảng đồng nghĩa khẩu ngữ → thuật ngữ pháp lý cũng đáng lấy (`"đóng thuế"` → `"nộp thuế"`, `"bị phạt"` → `"xử phạt vi phạm hành chính"`), nhưng lưu ý P-185 ghi rõ: **THÊM** biến thể chứ không **THAY** từ gốc.

### (4) ⭐ Câu nêu đích danh số hiệu phải bỏ qua RRF

P-185 ghi lại hai lần hỏng cùng kiểu:
- *"KG tra đúng nhưng xếp hạng 6, bị `top_k=5` cắt"*
- *"thua một kết quả bm25+vector của văn bản KHÁC vì xuất hiện ở hai danh sách thì điểm RRF gấp đôi"*

Kết luận của họ, đáng chép vào comment: **"tra khoá không phải bài toán xếp hạng"**. Sửa xong: 9/9 câu nêu số hiệu đều đúng.

→ **Đức Anh (Task 9):** trong `retrieve()`, nếu `extract_doc_id(query)` khác rỗng thì lọc metadata theo `doc_id` và cho kết quả đó lên đầu **trước** khi RRF chạy, đừng thả nó vào cùng rổ xếp hạng.

### (5) Cẩn thận RRF đếm hai lần

P-185 có bug "BM25 bỏ hai phiếu trong RRF". Sửa xong: **R@5 0,520 → 0,680**, MRR 0,468 → 0,589. Nguyên nhân: cùng một tài liệu vào `ranked_lists` hai lần.

→ **Kỳ Anh (Task 7):** `rerank_rrf` phải khử trùng theo `provision_id` **bên trong từng danh sách** trước khi cộng điểm.

### (6) HyDE có tác dụng thật (+8 điểm R@5) nhưng đắt

35s so với 3s. Điều đáng học: P-185 **từng kết luận sai** là "HyDE không cải thiện gì" — hoá ra bug (5) che mất, vì HyDE chỉ tác động lên nhánh vector mà nhánh đó đang bị BM25 đè.

→ **Đức Anh:** làm `semantic_search_hyde()` cho bonus 5đ, **mặc định tắt**, chỉ bật khi demo. Giữ `semantic_search()` gốc nguyên vẹn vì Task 9 gọi nó.

### (7) Vectorless hợp với dữ liệu này hơn bạn nghĩ

→ **Kỳ Anh (Task 8):** chunk đã cắt theo Điều nên cây Chương → Điều có sẵn. Câu hỏi tổng hợp kiểu *"toàn bộ thủ tục thành lập công ty TNHH gồm những bước nào"* cần đọc **nguyên Chương**, không phải một chunk 800 ký tự — đó chính là chỗ vectorless thắng.

### Ngân sách token

P-185 đo: nâng trần token 4.000 → 8.000 kéo R@5 từ 0,640 lên 0,720. Nâng tiếp lên 16.000 thì R@5 **đứng yên** (chỉ R@10 đẹp lên). Giữ khoảng 8.000 — nâng nữa chỉ tốn ngữ cảnh và tiền mà LLM không đọc tới.

---

## 5. Thống kê corpus + số hiệu chuẩn ngưỡng

### Corpus đã index

| | |
|---|---|
| Văn bản | 4 |
| Chunk | **1.095** |
| Chunk vượt `CHUNK_SIZE × 1,1` | **0** (`TestTask4` xanh) |
| Có `legal_ref` | 871/1.095 (**79%**) |
| Độ dài chunk trung bình | 565 ký tự |
| `customer_role` | `doanh_nghiep` 548 · `both` 546 · `ho_kinh_doanh` 1 |
| Collection | `ecommerce_legal_docs`, cosine, 384 chiều |

> `ho_kinh_doanh` chỉ có 1 chunk là **đúng với corpus hiện tại** — NĐ 01/2021 (văn bản về hộ kinh doanh) chưa nạp được. Con số này sẽ tăng khi lấp xong lỗ hổng ở mục 1.

### 🔴 SCORE_THRESHOLD — số đo thật, đừng dùng 0.48 trong tài liệu

`LAB_GUIDE.md` và `day8-lab-rag-pipeline.md` ghi `0.48`. **Giá trị đó KHÔNG áp dụng cho model hiện tại** — nó tính cho model khác. Với `multilingual-e5-small`, ngưỡng 0,48 nằm dưới cả câu lạc đề nhất, nên fallback PageIndex sẽ **không bao giờ** kích hoạt.

Đo trên chính corpus này (lấy cosine cao nhất của mỗi câu):

| Nhóm | Khoảng cosine | Ví dụ |
|---|---|---|
| **Liên quan** | **0,882 – 0,923** | "Vốn điều lệ của công ty cổ phần…" → 0,923 (LDN Điều 112) |
| **Lạc đề** | **0,815 – 0,828** | "Công thức nấu phở bò…" → 0,828 · "xyzabc123nonsense" → 0,815 |

→ **Đề xuất `SCORE_THRESHOLD = 0.85`** (giữa hai cụm, biên 0,054 mỗi phía).

Đức Anh nên tự chạy lại phép đo này sau khi lấp NĐ 01/2021 + TT 40/2021, vì thêm văn bản có thể dịch dải điểm.

Kiểm chứng retrieval — cả 4 câu liên quan đều trúng đúng điều khoản:

| Câu hỏi | Trúng |
|---|---|
| Thành lập công ty TNHH một thành viên… | LDN **Điều 48** |
| Hàng hoá nào bị cấm đăng bán trên sàn… | NĐ 52 **Điều 26** |
| Nghĩa vụ của người bán trên sàn… | NĐ 52 **Điều 35** |
| Vốn điều lệ của công ty cổ phần… | LDN **Điều 112** |

### ⚠️ Hạn chế đã đo: query KHÔNG DẤU bị hỏng

Cùng một câu hỏi, gõ không dấu thì điểm mất hết khả năng phân biệt:

| Query | Cosine | Trúng |
|---|---|---|
| "Thành lập công ty TNHH một thành viên…" (có dấu) | 0,887 | LDN Điều 48 ✅ |
| "thanh lap cong ty TNHH mot thanh vien…" (không dấu) | 0,868 | TikTok Terms ❌ |
| "cong thuc nau pho bo" (không dấu, lạc đề) | 0,855 | TikTok Terms |

Không dấu thì câu đúng chủ đề (0,868) và câu lạc đề (0,855) **gần như bằng nhau** → ngưỡng nào cũng vô dụng. BM25 còn hỏng nặng hơn vì token không khớp chút nào.

→ **Việc cho Đức Anh (Task 5) và Kỳ Anh (Task 6):** nếu còn giờ, thêm bước khôi phục dấu hoặc so khớp không dấu ở tầng chuẩn hoá câu hỏi. Nếu không kịp thì **ghi vào README như hạn chế đã biết** và nhắc trong demo là hệ thống giả định người dùng gõ có dấu — nói ra một hạn chế đã đo được luôn tốt hơn để coach tự phát hiện.

---

## 6. Cạm bẫy đã biết

| # | Cạm bẫy | Hậu quả | Cách tránh |
|---|---|---|---|
| 1 | So `score_threshold` với điểm **RRF đã fuse** | RRF top-1 luôn ≈ `1/(60+1) ≈ 0,016` bất kể liên quan hay không → fallback **không bao giờ** trigger | So với **điểm cosine gốc** `dense_results[0]["score"]` |
| 2 | Khử trùng theo `content` | Hai chunk con cùng một Điều bị tính là hai kết quả | Khử theo `provision_id` |
| 3 | Sinh `doc_id` bằng hai đoạn code khác nhau | Không bao giờ tìm thấy, **im lặng**, không có exception | Chỉ gọi `legal_utils.normalize_doc_number()` |
| 4 | Quên `normalize_query()` | `"TNCN"` không khớp `"thu nhập cá nhân"` → câu demo chính hỏng | Gọi trước mọi lượt tra cứu |
| 5 | Load corpus ở module level | `import src.task9` nổ trên máy chưa có data | Load **lazy** trong hàm, cache sau lần đầu |
| 6 | Index đè lên `chroma_db/` cũ | Chunk cũ lẫn mới, retrieval trả rác | `Remove-Item -Recurse -Force chroma_db` rồi index lại |
| 7 | Chạy `python src/task9_...py` | `ImportError` do relative import | `python -m src.task9_retrieval_pipeline` từ gốc repo |
| 8 | Trích dẫn số hiệu dính markdown | LLM viết `**52/2013/NĐ-CP**` → regex bắt cả dấu sao → tra trượt, trông y như LLM bịa | Loại `*` và `_` khi bóc số hiệu; **không** loại `.` (có văn bản thật dùng `QĐ.UB`) |

---

## 7. Cách kiểm tra lại

*(điền ở CP3)*
