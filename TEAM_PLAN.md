# KẾ HOẠCH TRIỂN KHAI — Lab 08 RAG Pipeline (Nhóm 5 người, 180 phút)

> **Cách dùng file này**: đọc mục 0 (chủ đề) → mục 1 (vai của bạn) → mục 2 (timeline) → mục 3 (quy trình git, BẮT BUỘC) → mục 4.x (chi tiết phần của bạn) → mục 7 (prompt dán vào agent của bạn).
> Quy tắc chống conflict bản rút gọn nằm ở `CLAUDE.md` — agent của bạn sẽ tự đọc file đó.

---

## Context

Repo này là **starter template**: toàn bộ hàm nghiệp vụ trong `src/task1..10` đều là stub `raise NotImplementedError`, lời giải mẫu nằm trong comment. Thư mục `data/` rỗng (chỉ có `.gitkeep`), `chroma_db/` chưa tồn tại, `golden_dataset.json` mới có 3/15 câu và **nội dung cũ (Shopee) không còn khớp chủ đề nhóm chọn**.

Nhóm 5 người (Tuấn Anh, Đức Anh, Kỳ Anh, Hoàng, Trường) hoàn thành trong **180 phút live tại lớp**, chưa có API key, quy trình **branch riêng + PR**. Mục tiêu **100/100** = 50đ pipeline (35/35 pytest) + 30đ bài nhóm + 20đ bonus.

Rủi ro lớn nhất không phải code mà là **3 thứ tốn wall-clock**: cài dependency (~10 phút), tải model `BAAI/bge-m3` (2.27 GB), và thu thập dữ liệu thật. Plan thiết kế để 5 người chạy song song gần như không chặn nhau, **5 vùng file tách rời hoàn toàn**.

---

## 0. CHỦ ĐỀ & NGUỒN DỮ LIỆU

### 🏛️ Trợ Lý Pháp Lý Khởi Nghiệp & Thương Mại Điện Tử

Tra cứu quy định pháp lý khi bán hàng trên TikTok Shop / Shopee, đăng ký Hộ kinh doanh cá thể, hoặc thành lập Công ty TNHH / Cổ phần.

**Câu hỏi truy vấn mẫu (dùng làm demo CP6):**
- *"Bán hàng online trên TikTok Shop đạt doanh thu bao nhiêu thì phải nộp thuế TNCN và GTGT?"*
- *"Hồ sơ và thủ tục đăng ký Hộ kinh doanh cá thể gồm những giấy tờ gì?"*

### ⚠️ CẢNH BÁO NGUỒN — đọc kỹ, đây là thứ làm hỏng demo

**Hai câu hỏi mẫu ở trên KHÔNG trả lời được nếu chỉ dùng 3 nguồn ban đầu (LDN 2020 + NĐ 52 + quy định sàn):**

1. **Luật Doanh nghiệp 2020 KHÔNG điều chỉnh hộ kinh doanh.** Thủ tục, hồ sơ đăng ký hộ kinh doanh nằm ở **Nghị định 01/2021/NĐ-CP** về đăng ký doanh nghiệp.
2. **Ngưỡng doanh thu chịu thuế GTGT/TNCN không nằm trong LDN hay NĐ 52** — nó ở **Thông tư 40/2021/TT-BTC** (thuế với hộ kinh doanh, cá nhân kinh doanh) và pháp luật thuế GTGT.
3. **Ngưỡng doanh thu này ĐÃ THAY ĐỔI** — Luật Thuế GTGT 2024 nâng mức doanh thu không chịu thuế của hộ/cá nhân kinh doanh lên cao hơn mức 100 triệu/năm cũ. **Bắt buộc tải bản đang có hiệu lực và tự kiểm tra con số khi tải về.** RAG trả lời "đúng theo tài liệu" nhưng tài liệu hết hiệu lực thì demo vẫn sai trước mặt coach.

→ Vì vậy Task 1 thu thập **6 văn bản**, không phải 3.

### 📄 Task 1 — Danh sách văn bản bắt buộc tải

| # | Văn bản | Phục vụ câu hỏi gì | Tên file lưu |
|---|---|---|---|
| 1 | **Luật Doanh nghiệp 2020** (59/2020/QH14) | Thành lập TNHH/Cổ phần, loại hình, vốn điều lệ, người đại diện | `luat-doanh-nghiep-2020.pdf` |
| 2 | **Nghị định 01/2021/NĐ-CP** về đăng ký doanh nghiệp | ⭐ Hồ sơ + thủ tục đăng ký **hộ kinh doanh**, đăng ký DN | `nd-01-2021-dang-ky-doanh-nghiep.pdf` |
| 3 | **Thông tư 40/2021/TT-BTC** | ⭐ Thuế GTGT/TNCN với hộ & cá nhân kinh doanh, ngưỡng doanh thu, tỷ lệ % | `tt-40-2021-thue-ho-kinh-doanh.pdf` |
| 4 | **Nghị định 52/2013/NĐ-CP** về TMĐT | Nghĩa vụ người bán trên sàn, website TMĐT | `nd-52-2013-thuong-mai-dien-tu.pdf` |
| 5 | **Nghị định 85/2021/NĐ-CP** sửa đổi NĐ 52 | Cập nhật quy định sàn TMĐT (NĐ 52 đã cũ, thiếu cái này là lỗi thời) | `nd-85-2021-sua-doi-nd52.pdf` |
| 6 | **Quy định người bán TikTok Shop / Shopee** | Chính sách sàn (không phải luật) — hàng cấm, nghĩa vụ seller | `quy-dinh-nguoi-ban-tiktok-shop.pdf` |

**Nguồn tải**: `thuvienphapluat.vn`, `vanban.chinhphu.vn`, `luatvietnam.vn` (văn bản luật) · `seller-vn.tiktok.com`, `banhang.shopee.vn` (quy định sàn).
Nếu trang chỉ có HTML, dùng `fpdf2` (đã có trong `requirements.txt`) chuyển text → PDF. Ưu tiên bản PDF gốc nếu có.

> ✅ Test chỉ cần ≥3 file >1KB, nhưng **chất lượng demo phụ thuộc đủ 6 văn bản này**. Ưu tiên tải theo thứ tự #2, #3, #1 trước (2 câu demo flagship), rồi mới #4, #5, #6.

### 📰 Task 2 — Chủ đề bài viết cần crawl (≥5)

Nguồn HTML tĩnh, dễ crawl: **VnExpress Kinh doanh, Tuổi Trẻ, Thanh Niên, VietnamNet, CafeF, baochinhphu.vn**.

Chủ đề nên tìm:
- Thuế với người bán hàng online / livestream trên TikTok Shop, Shopee
- Sàn TMĐT khấu trừ và nộp thuế thay người bán
- Hướng dẫn đăng ký hộ kinh doanh cá thể — nên chọn hộ KD hay công ty?
- So sánh hộ kinh doanh vs công ty TNHH (thuế, trách nhiệm, thủ tục)
- Xử phạt bán hàng online không đăng ký kinh doanh / không xuất hoá đơn

### 🏷️ Metadata schema (chốt ở Task 4, cả nhóm dùng chung)

ChromaDB chỉ nhận giá trị scalar (str/int/float/bool) trong metadata.

```python
{
    "source": "nd-01-2021-dang-ky-doanh-nghiep.pdf",  # tên file
    "type": "legal" | "news",
    "chunk_index": 0,
    "doc_title": "Nghị định 01/2021/NĐ-CP",           # để LLM cite đẹp
    "legal_ref": "Điều 87",                            # ⭐ điều/khoản, "" nếu không parse được
    "customer_role": "ho_kinh_doanh" | "doanh_nghiep" | "both",
}
```

- `legal_ref` là **điểm ăn tiền của bài này**: citation `[Nghị định 01/2021/NĐ-CP, Điều 87]` thuyết phục hơn hẳn `[nd-01-2021.pdf]`. Parse bằng regex `Điều\s+\d+` trên đầu mỗi chunk.
- `customer_role` giữ **nguyên tên field** theo yêu cầu K4 Variant (coach hay hỏi), chỉ đổi **giá trị** cho hợp domain. Ghi rõ lý do trong README.

---

## 1. Phân vai (theo Phương Án B của LAB_GUIDE)

| Người | Role | Nhiệm vụ | File sở hữu (ĐỘC QUYỀN) |
|---|---|---|---|
| **Tuấn Anh** | **Data & Indexing Lead** + **Merge Captain** | Task 1–3 (thu thập, chuẩn hoá), Task 4 (chunk + index + metadata), điều phối merge, README | `data/**`, `src/task1_*.py`, `src/task2_*.py`, `src/task3_*.py`, `src/task4_*.py`, `README.md`, `requirements.txt`, `.gitignore`, `.gitattributes`, `CLAUDE.md`, `TEAM_PLAN.md`, `.env.example` |
| **Đức Anh** | **RAG Architect & Dense Search** | Task 5 (semantic + HyDE), Task 9 (pipeline hoàn chỉnh), deploy HF | `src/task5_*.py`, `src/task9_*.py`, `src/supervisor.py` |
| **Kỳ Anh** | Sparse Search & Reranking | Task 6 (BM25 + TF-IDF), Task 7 (RRF), Task 8 (vectorless fallback) | `src/task6_*.py`, `src/task7_*.py`, `src/task8_*.py` |
| **Hoàng** | Frontend & Chatbot + **Repo Admin** | Task 10 (generation), `app.py`, conversation memory, UI/UX | `src/task10_generation.py`, `app.py` |
| **Trường** | Evaluation & QA | Golden dataset, RAGAS, A/B, báo cáo, **chạy pytest cho cả team** | `group_project/**` |

> 🔄 **Đã đổi so với bản trước**: Tuấn Anh chuyển sang phụ trách dữ liệu + indexing (Task 1–4); Đức Anh nhận Task 5 + Task 9. Tuấn Anh vẫn giữ vai Merge Captain và các file cấu hình chung.

**Không ai được sửa `tests/`** — file chấm điểm.
**Không ai sửa file ngoài vùng của mình.** Cần đổi file người khác → nhắn group chat, chủ file tự sửa.

---

## 2. Timeline 7 Checkpoint

### CP0 — Setup (0:00 – 0:10) — **AI CŨNG LÀM ĐỒNG THỜI**

Mở **2 terminal**. Terminal A chạy nền suốt CP0–CP1, Terminal B để làm việc.

**Terminal A (chạy nền, không đợi):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
> Nếu đứt giữa chừng vì `pageindex` / `ragas` (Python 3.12 hay xung đột), cài đợt lõi trước — đủ qua 35 test:
> ```powershell
> pip install python-dotenv requests numpy "markitdown[pdf]" fpdf2 langchain-text-splitters sentence-transformers chromadb rank-bm25 scikit-learn openai streamlit pytest crawl4ai beautifulsoup4
> playwright install chromium
> pip install ragas==0.1.21 datasets langchain-openai   # đợt 2, chỉ Trường bắt buộc
> ```

Ngay khi `sentence-transformers` cài xong, **mọi người** tải model nền:
```powershell
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3')"
```
2.27 GB — cứ để chạy, sang CP1 làm việc khác.

**Terminal B — việc riêng:**

| Người | Việc CP0 |
|---|---|
| **Hoàng** | GitHub → Settings → Collaborators → mời 4 người (**Write**), Tuấn Anh cấp **Maintain**. Bật branch protection `main`: *Require a pull request before merging* (0 approval). |
| **Tuấn Anh** | ✅ **ĐÃ XONG** — setup commit đã ở trên `main`. |
| **Cả 5** | `git pull origin main` → chạy mục 3.2. Đăng ký https://openrouter.ai → tạo key → copy `.env.example` thành `.env`, điền `OPENROUTER_API_KEY`. Test: `python -c "import os,dotenv;dotenv.load_dotenv();print(os.getenv('OPENROUTER_API_KEY')[:12])"` |
| **Trường** | Đăng ký thêm https://pageindex.ai lấy `PAGEINDEX_API_KEY` (nếu được), gửi Kỳ Anh. Không có cũng không sao — xem Plan B Task 8. |

✅ **Pass CP0**: `import chromadb, sentence_transformers, streamlit` không lỗi; có `.env`; 4 người nhận lời mời collaborator.

> ⚠️ **`.env` KHÔNG BAO GIỜ commit.** Chia sẻ key qua chat riêng.

---

### CP1 — Thu thập & chuẩn hoá (0:10 – 0:35)

| Người | Việc | Branch |
|---|---|---|
| **Tuấn Anh** | Task 1 + 2 + 3. Ưu tiên tải NĐ 01/2021 và TT 40/2021 TRƯỚC | `feat/tuananh-cp1-data` |
| **Đức Anh** | **Không đụng `data/`.** Tìm & gửi link 6 văn bản + 5 bài báo qua chat cho Tuấn Anh; viết khung Task 9 + `supervisor.py` | `feat/ducanh-cp1-skeleton` |
| **Kỳ Anh** | Task 7 (`rerank_rrf` + `rerank`) — thuần thuật toán, test bằng dummy, **không chờ ai** | `feat/kyanh-cp1-rerank` |
| **Hoàng** | Task 10 phần thuần: `reorder_for_llm()` + `format_context()` (không cần LLM/data) | `feat/hoang-cp1-reorder` |
| **Trường** | Khung 15 câu `golden_dataset.json` theo chủ đề pháp lý (tinh chỉnh sau khi có data) | `feat/truong-cp1-golden` |

✅ **Pass CP1**: ≥3 (mục tiêu 6) file PDF trong `data/landing/legal/` mỗi file >1KB; ≥5 JSON trong `data/landing/news/` mỗi file >500 bytes **có field `url`**; có `.md` tương ứng trong `data/standardized/`. PR Tuấn Anh **merge đầu tiên**.

---

### CP2 — Chunking, Indexing & Search (0:35 – 1:00)

| Người | Việc | Branch |
|---|---|---|
| **Tuấn Anh** | Task 4: chunk 800/100, parse `legal_ref`, gắn `customer_role`, index ChromaDB. **Push `get_embedding_model()` + `get_collection()` sớm trong PR nhỏ** để Đức Anh code song song | `feat/tuananh-cp2-index` |
| **Đức Anh** | Task 5 `semantic_search()` — code trước theo contract, test ngay khi Task 4 merge | `feat/ducanh-cp2-semantic` |
| **Kỳ Anh** | Task 6 (`build_bm25_index` + `lexical_search`) — cần `data/standardized/` từ CP1 | `feat/kyanh-cp2-bm25` |
| **Hoàng** | Task 10: gọi LLM OpenRouter với **fake chunks hardcode**, chưa nối `retrieve()` | `feat/hoang-cp2-llm` |
| **Trường** | Đọc `data/standardized/*.md`, viết lại `golden_dataset.json` **15–20 câu bám văn bản thật** | `feat/truong-cp2-golden` |

🚦 **DECISION GATE — cuối CP2 (1:00)**: nếu `bge-m3` chưa tải xong, Tuấn Anh đổi 2 dòng trong `task4_chunking_indexing.py`:
```python
EMBEDDING_MODEL = "intfloat/multilingual-e5-small"   # 471MB thay vì 2.27GB
EMBEDDING_DIM = 384
```
báo cả nhóm tải model đó, index lại, ghi lý do vào README. **Không chần chừ quá 1:00.**

✅ **Pass CP2**: `chroma_db/` tồn tại, `collection.count() > 0`; `pytest ...::TestTask4 -v` và `::TestTask6` xanh.

---

### CP3 — Reranking & Fallback (1:00 – 1:20)

| Người | Việc | Branch |
|---|---|---|
| **Kỳ Anh** | Task 8 vectorless fallback (Plan B mục 4.3) | `feat/kyanh-cp3-pageindex` |
| **Đức Anh** | Task 9 `retrieve()` + **calibrate `SCORE_THRESHOLD` bằng đo thật** | `feat/ducanh-cp3-pipeline` |
| **Tuấn Anh** | Kiểm tra chất lượng chunk (điều/khoản có bị cắt đôi không), reindex nếu cần | `feat/tuananh-cp3-fix` |
| **Hoàng** | Nối `generate_with_citation()` → `retrieve()` thật, wire vào `app.py` | `feat/hoang-cp3-wire` |
| **Trường** | Viết `evaluate_with_ragas()` + `compare_configs()` | `feat/truong-cp3-ragas` |

✅ **Pass CP3**: `rerank_rrf([dense, sparse])` gộp đúng; `pageindex_search()` trả list có `source: "pageindex"`; Đức Anh đọc được bảng điểm cosine query liên quan vs lạc đề.

---

### CP4 — Chốt 50đ pipeline (1:20 – 1:45) ⭐ MỐC QUAN TRỌNG NHẤT

- **Tuấn Anh**: merge toàn bộ PR → `main` theo đúng thứ tự, giữ `main` xanh.
- **Đức Anh**: hoàn tất Task 9, chạy smoke test end-to-end.
- **Trường (QA)**: trên `main` mới nhất chạy
  ```powershell
  $env:PYTHONIOENCODING="utf-8"
  python -m pytest tests/test_individual.py -v
  ```
  Ghi bảng **test nào fail/skip → thuộc task nào → chủ file nào**, đăng group chat.
- **3 người còn lại**: fix **chỉ trong file của mình**, push branch `fix/<tên>-taskN`.

✅ **Pass CP4**: `35 passed` (không có `skipped` — skip = chưa implement = **không được điểm**).

---

### CP5 — Bài nhóm 30đ + Bonus (1:45 – 2:15)

| Người | Việc |
|---|---|
| **Trường** | RAGAS 4 metric × 2 config (A: hybrid+rerank / B: dense-only), điền `results.md`: bảng điểm, Δ, worst 3, 3 đề xuất |
| **Hoàng** | Conversation memory + UI hiển thị score/highlight; **đổi câu hỏi gợi ý trong sidebar sang chủ đề pháp lý** |
| **Đức Anh** | `git add -f chroma_db/` (LFS) + deploy Hugging Face Spaces |
| **Tuấn Anh** | **README: đổi tiêu đề/frontmatter HF từ "E-commerce Support" sang "Trợ lý Pháp lý Khởi nghiệp & TMĐT"** + diagram kiến trúc + bảng phân công + giải thích config (chunk 800/100, model, threshold, metadata schema) |
| **Kỳ Anh** | Chuẩn bị notes giải thích BM25 vs TF-IDF (bonus 5đ) |

⚠️ **Rate limit RAGAS**: model `:free` OpenRouter giới hạn **50 request/ngày cho cả tài khoản**. RAGAS gọi ~4–8 lần/câu/metric → Trường chạy **5 câu trước**, chỉ full 15 câu nếu quota còn. Hết quota thì mượn key người khác trong nhóm cho config B.

---

### CP6 — Demo (2:15 – 3:00)

| Người | Phần trình bày |
|---|---|
| **Tuấn Anh** | Chủ đề, nguồn 6 văn bản, **vì sao phải thêm NĐ 01/2021 + TT 40/2021**, metadata schema `legal_ref`, chunk 800/100 |
| **Đức Anh** | Kiến trúc pipeline, hybrid retrieval, **cái bẫy fallback** (cosine gốc vs RRF), HyDE |
| **Kỳ Anh** | BM25 vs TF-IDF, công thức RRF, vectorless retrieval (bonus 5đ) |
| **Hoàng** | Live demo Streamlit — chạy đúng 2 câu hỏi flagship + citation có điều/khoản + memory |
| **Trường** | Bảng RAGAS A/B + worst performers + đề xuất |

Cuối cùng: `git push origin main`, gửi link repo + link HF Space.

---

## 3. QUY TRÌNH GITHUB — CHỐNG CONFLICT

### 3.1 Setup commit — ✅ ĐÃ XONG, đã nằm trên `main`

**a) `.gitignore` — đã thêm `chroma_db/`** (trước đó THIẾU — mìn conflict lớn nhất: sqlite binary, đổi sau mỗi lần index, 5 người push vào = vỡ trận)

**b) `.gitattributes` — đã thêm `* text=auto`**. Index repo hiện đã 100% LF nên dòng này **không gây diff giả**, chỉ chặn trường hợp ai có `core.autocrlf=false` commit CRLF làm cả file bị đánh dấu "thay đổi toàn bộ".

**c) `CLAUDE.md` ở root** — ⭐ **biện pháp chống conflict quan trọng nhất**: bảng chủ quyền file, lệnh git bị cấm, contract giữa các module. Claude Code **tự đọc file này** nên cả 5 agent đều bị ràng buộc.

### 3.2 Cấu hình git — cả 5 người chạy 1 lần, NGAY BÂY GIỜ

```powershell
git config --global pull.rebase true
git config --global core.autocrlf true
git config --global user.name "Tên Của Bạn"
git config --global user.email "email@cua.ban"
git lfs install
```

### 3.3 Vòng lặp làm việc chuẩn — lặp lại MỖI CHECKPOINT

```powershell
git checkout main
git pull --rebase origin main
git checkout -b feat/kyanh-cp2-bm25          # branch NGẮN HẠN, sống < 25 phút

# ... code ...

git add src/task6_lexical_search.py           # LIỆT KÊ FILE CỤ THỂ, không bao giờ "git add ."
git commit -m "feat(task6): BM25 lexical search với tokenizer tiếng Việt"

git fetch origin
git rebase origin/main                        # đồng bộ trước khi push, bắt lỗi sớm
git push -u origin feat/kyanh-cp2-bm25

gh pr create --base main --title "[CP2][Kỳ Anh] Task 6 — BM25" --body "Files: src/task6_lexical_search.py
Test: pytest tests/test_individual.py::TestTask6 -v -> 4 passed"
```

### 3.4 Quy tắc vàng (dán vào group chat)

1. **Branch sống ngắn.** 1 branch = 1 checkpoint.
2. **Tên branch phẳng**: `feat/tên-cpN-mô-tả`. **KHÔNG** dùng `feat/tên/cpN` — nếu ai lỡ tạo branch `feat/tên` thì mọi branch `feat/tên/...` sẽ lỗi `cannot lock ref`.
3. **Không bao giờ `git add .`** — sẽ nuốt `chroma_db/`, `.env`, file rác của agent.
4. **Không bao giờ force-push `main`.**
5. **Chỉ Tuấn Anh merge PR.**
6. **Thứ tự merge cố định**: Tuấn Anh (data/index) → Kỳ Anh (search) → Đức Anh (semantic/pipeline) → Hoàng (gen/app) → Trường (eval). Downstream phụ thuộc upstream.
7. **Sau mỗi merge**, Tuấn Anh nhắn `"main updated"` → 4 người còn lại `git pull --rebase origin main`.
8. **`chroma_db/` không vào git** tới CP5. Ai cần index thì tự chạy `python -m src.task4_chunking_indexing` (~2 phút).
9. **`.env` không bao giờ vào git.** Lỡ commit → đổi key ngay, key đã lộ vĩnh viễn trong lịch sử git.
10. **Merge PR bằng "Squash and merge"** — lịch sử `main` sạch, dễ revert.

### 3.5 Xử lý khi VẪN bị conflict

Với file ownership chặt, conflict thật chỉ xảy ra ở `README.md` hoặc khi ai đó phá luật.

```powershell
git fetch origin
git rebase origin/main
# → CONFLICT (content): Merge conflict in <file>

git status                       # xem file nào conflict
code <file>                      # xoá <<<<<<<, =======, >>>>>>>, GIỮ CẢ HAI PHẦN nếu là README
git add <file>
git rebase --continue
git push --force-with-lease origin feat/<tên>-cpN-...   # CHỈ trên branch riêng, KHÔNG BAO GIỜ trên main
```

**Nếu rối quá — đường thoát an toàn (không mất code):**
```powershell
git rebase --abort
git branch backup-cua-toi
# rồi báo Tuấn Anh
```

**Conflict file binary (`*.sqlite3`, `*.pdf`)** — không merge được, chọn một bên:
```powershell
git checkout --theirs chroma_db/chroma.sqlite3   # lấy bản trên main
git checkout --ours  chroma_db/chroma.sqlite3    # giữ bản của mình
git add chroma_db/chroma.sqlite3
```
Tốt nhất: **xoá thư mục và index lại**, đừng merge binary.

### 3.6 Nội quy cho AGENT (5 agent chạy song song)

Mỗi người mở đầu phiên chat với agent bằng **prompt ở mục 7**.

Ba lỗi agent hay gây nhất trong repo này:
- Agent "tiện tay" sửa `requirements.txt` khi thiếu package → **conflict 5 chiều**. Luật: báo Tuấn Anh.
- Agent sửa `tests/test_individual.py` cho test pass → **gian lận, mất điểm**. Luật: cấm tuyệt đối.
- Agent chạy `git add .` rồi commit `chroma_db/` 200MB → repo phình, PR không mở nổi. Luật: chỉ `git add <file cụ thể>`.

---

## 4. Nhiệm vụ chi tiết & đầu ra mong muốn

### 4.1 TUẤN ANH — Task 1, 2, 3, 4 (Data & Indexing Lead)

Bạn là **đầu nguồn của cả pipeline**: 4 người còn lại đều bị chặn cho tới khi bạn giao được `data/standardized/` và `chroma_db/`. Ưu tiên **tốc độ giao hàng hơn sự hoàn hảo** — đủ 3 file để unblock trước, bổ sung 3 file còn lại sau.

**Task 1** → `data/landing/legal/` — tải 6 văn bản ở **mục 0**, thứ tự ưu tiên `#2 → #3 → #1 → #4 → #5 → #6`. Mỗi file **> 1KB**. Tên file không dấu.
Nếu trang chỉ có HTML: `requests` + `BeautifulSoup` lấy text → `fpdf2` xuất PDF. Font mặc định của fpdf2 **không có tiếng Việt** — nhúng font Unicode (DejaVuSans) hoặc lưu `.docx` (test chấp nhận `.pdf/.docx/.doc`), tránh PDF ra toàn dấu hỏi.

**Task 2** → `data/landing/news/` ≥5 file JSON, mỗi file **> 500 bytes**, **bắt buộc có key `url`** (test kiểm tra):
```json
{"url": "...", "title": "...", "date_crawled": "2026-08-04T10:00:00", "content_markdown": "..."}
```
Chủ đề ở **mục 0**. Nếu `crawl4ai` lỗi browser → `playwright install chromium`; vẫn lỗi thì fallback `requests` + `BeautifulSoup`, vẫn ghi đủ metadata.

**Task 3** → `data/standardized/legal/*.md` + `data/standardized/news/*.md`, mỗi file **> 200 ký tự**. Bỏ 2 dòng `raise NotImplementedError`, bật code mẫu trong comment.
⚠️ Kiểm tra mắt thường 1 file legal sau convert: PDF văn bản luật hay dính header/footer lặp lại và số trang chen giữa câu. Nếu bẩn nặng, viết vài dòng regex dọn — chunk bẩn làm hỏng cả retrieval lẫn citation.

**Task 4** → `chroma_db/` với `collection.count() > 0`. Sửa config:
```python
CHUNK_SIZE = 800        # docs & CP2 pass criteria dùng 800, không phải 500 như stub
CHUNK_OVERLAP = 100
```
Thêm 2 hàm module-level (Đức Anh sẽ import — **push sớm trong PR nhỏ để anh ấy code song song**):
```python
def get_embedding_model():   # cache module-level, tải model 1 lần
def get_collection():        # chromadb.PersistentClient(str(CHROMA_DIR)).get_or_create_collection(COLLECTION_NAME)
```
Gắn metadata theo schema ở **mục 0** — đặc biệt `legal_ref` (regex `Điều\s+\d+`) và `customer_role`.

💡 **Cân nhắc `MarkdownHeaderTextSplitter` cho văn bản luật**: văn bản pháp luật có cấu trúc Chương/Điều rất rõ. Tách theo heading rồi mới `RecursiveCharacterTextSplitter` trong từng Điều sẽ giữ được ranh giới điều khoản — chunk không bị cắt giữa 2 điều luật, và `legal_ref` gán chính xác hơn nhiều. Nếu kịp giờ thì làm, không kịp thì `recursive` thuần vẫn qua test.

✅ Nghiệm thu: `pytest tests/test_individual.py::TestTask1 ::TestTask2 ::TestTask3 ::TestTask4 -v` → **15 passed**.
✅ Kiểm tra thủ công: `python -c "from src.task4_chunking_indexing import get_collection; c=get_collection(); print(c.count()); print(c.peek(2)['metadatas'])"` — metadata phải thấy `legal_ref`, `customer_role`.

---

### 4.2 ĐỨC ANH — Task 5, Task 9 (RAG Architect & Dense Search)

**Task 5** → `semantic_search(query, top_k)` trả list sorted desc theo cosine `[0,1]`. Dùng code mẫu trong comment (`score = max(0.0, 1.0 - distance)`), import `get_embedding_model()` / `get_collection()` từ Task 4 (**đừng khởi tạo model lần nữa** — tốn thêm 2.27GB RAM).
**Bonus HyDE (5đ)**: thêm `semantic_search_hyde(query, top_k)` — LLM sinh 1 đoạn trả lời pháp lý giả định rồi embed đoạn đó thay vì embed câu hỏi. Rất hợp domain này: câu hỏi đời thường ("bán TikTok bao nhiêu thì đóng thuế") khác xa văn phong luật ("doanh thu từ hoạt động sản xuất, kinh doanh trong năm dương lịch"). **Giữ `semantic_search()` gốc nguyên vẹn** (Task 9 gọi nó).

**Task 9** → `retrieve()` theo code mẫu trong comment. Điểm mấu chốt:
```python
dense_results  = semantic_search(query, top_k=top_k*2)   # GIỮ điểm cosine gốc
sparse_results = lexical_search(query, top_k=top_k*2)
merged = rerank_rrf([dense_results, sparse_results], top_k=top_k*2)
for item in merged: item["source"] = "hybrid"
final = rerank(query, merged, top_k=top_k) if use_reranking else merged[:top_k]

# ⚠️ SO THRESHOLD VỚI COSINE GỐC, KHÔNG PHẢI ĐIỂM RRF
best = dense_results[0]["score"] if dense_results else 0.0
if best < score_threshold:
    fb = pageindex_search(query, top_k=top_k)
    if fb: return fb
return final[:top_k]
```

**Calibrate `SCORE_THRESHOLD` bằng đo thật** (đừng copy 0.3 hay 0.48 mù quáng):
```powershell
python -c "from src.task5_semantic_search import semantic_search as s; [print(round(s(q,1)[0]['score'],3), q) for q in ['hồ sơ đăng ký hộ kinh doanh','doanh thu bao nhiêu phải nộp thuế','xyzabc123nonsense','công thức nấu phở']]"
```
→ chọn ngưỡng giữa 2 cụm điểm, ghi rõ: `SCORE_THRESHOLD = 0.48  # đo được: liên quan 0.62-0.71, lạc đề 0.21-0.33`.

**Ràng buộc test**: mọi item phải có `content`, `score`, `source ∈ {"hybrid","pageindex"}`; `len(result) <= top_k`; query rác + threshold 0.99 **không được crash**.

**Tuỳ chọn nếu dư giờ**: `src/supervisor.py` ~40 dòng chạy `semantic_search` và `lexical_search` song song bằng `concurrent.futures.ThreadPoolExecutor` — LAB_GUIDE có nhắc file này, coach có thể hỏi.

✅ Nghiệm thu: `pytest tests/test_individual.py::TestTask5 ::TestTask9 -v` → **8 passed**; `python -m src.task9_retrieval_pipeline` chạy 4 query, query rác rơi vào `[pageindex]`.

---

### 4.3 KỲ ANH — Task 6, 7, 8

**Task 6** → `lexical_search(query, top_k)`, BM25Okapi trên `data/standardized/**/*.md`.
- `CORPUS` load **lazy** (hàm `_load_corpus()` gọi lần đầu), **không** ở module level — nếu không `import src.task9` sẽ nổ trên máy chưa có data.
- Tokenizer tiếng Việt: `text.lower()` rồi tách regex `\w+` (bỏ dấu câu). Đừng cài `underthesea` (mất 5 phút).
- **BM25 rất mạnh với domain này**: người dùng gõ đúng "Nghị định 52", "Điều 87", "Thông tư 40" — dense search hay trượt số hiệu văn bản, BM25 bắt chính xác. Nêu điểm này khi demo.

**Task 7** → `rerank_rrf(ranked_lists, top_k, k=60)` theo `RRF(d) = Σ 1/(k + rank)`.
⚠️ **`rerank()` hiện raise NotImplementedError ở cả 3 nhánh** nhưng test gọi nó với **1 list phẳng**. Sửa nhánh `rrf`:
```python
elif method == "rrf":
    return rerank_rrf([candidates], top_k=top_k)
```
**Bonus 5đ**: thêm `lexical_search_tfidf()` dùng `sklearn.feature_extraction.text.TfidfVectorizer` (đã có trong requirements), chuẩn bị giải thích TF-IDF vs BM25 (BM25 có bão hoà TF `k1` và chuẩn hoá độ dài `b`; TF-IDF không có) cho demo CP6.

**Task 8** → `pageindex_search(query, top_k)` trả list có `'source': 'pageindex'`.
**Plan B (không có API key — khả năng cao)**: implement **local vectorless retriever** cùng interface:
```python
# Đọc data/standardized/**/*.md, cắt theo heading markdown (#, ##, ###) thành cây mục lục,
# chấm điểm mỗi section bằng độ trùng từ khoá query vs (tiêu đề section × 2 + nội dung),
# trả nguyên cả section (KHÔNG chunk) — đúng tinh thần "vectorless, structure-based".
# Docstring ghi rõ: "Local implementation of vectorless structural retrieval
# (PageIndex-compatible interface). Không dùng embedding/vector store."
```
Rất hợp domain luật: câu hỏi tổng hợp kiểu *"toàn bộ thủ tục thành lập công ty TNHH gồm những bước nào?"* cần đọc nguyên Chương chứ không phải 1 chunk 800 ký tự.
Giữ `source: "pageindex"` để đúng contract Task 9. **Phải trả `[]` (không raise) khi không có data** — test Task 9 gọi với `score_threshold=0.99` ép chạy nhánh này.

✅ Nghiệm thu: `pytest tests/test_individual.py::TestTask6 ::TestTask7 ::TestTask8 -v` → **9 passed**.

---

### 4.4 HOÀNG — Task 10 + app.py + Repo Admin

**Task 10** — 3 hàm:
- `reorder_for_llm(chunks)`: `front = chunks[::2]; back = chunks[1::2]; return front + back[::-1]`. Test kiểm tra **giữ nguyên số lượng** và **phần tử đầu vẫn là chunk 0**.
- `format_context(chunks)`: **bắt buộc chèn `metadata['source']`** vào string output (test assert tên file có trong context). Nên chèn thêm `doc_title` và `legal_ref` để LLM cite được `[Nghị định 01/2021/NĐ-CP, Điều 87]`.
- `generate_with_citation(query, top_k)` → `{'answer', 'sources', 'retrieval_source'}`, `answer` là str không rỗng.

```python
client = OpenAI(api_key=os.getenv("OPENROUTER_API_KEY"), base_url="https://openrouter.ai/api/v1")
```
Chọn `LLM_MODEL` là model `:free` (https://openrouter.ai/models?max_price=0). **Bọc `try/except` quanh lời gọi LLM**: hết quota thì trả `answer` báo lỗi rõ ràng thay vì raise — để test Task 10 vẫn pass và app không sập giữa demo.

⚠️ **Sửa `SYSTEM_PROMPT` cho domain pháp lý**: prompt hiện tại nói về "chính sách TMĐT, đổi trả, giao hàng". Đổi sang trợ lý pháp lý khởi nghiệp, yêu cầu citation dạng `[Tên văn bản, Điều X]`, và **bắt buộc thêm câu miễn trừ**: đây là thông tin tham khảo, không thay thế tư vấn pháp lý chính thức.

**`app.py`** đã hoàn thiện ~90% (sidebar, slider top_k, expander nguồn, đã import sẵn `generate_with_citation`). Cần làm:
- Xoá khối TODO chết ở dòng 113–118.
- **Đổi 5 câu hỏi gợi ý trong sidebar** sang chủ đề pháp lý, gồm 2 câu flagship ở mục 0.
- Đổi tiêu đề/emoji: 🛒 → 🏛️, "E-commerce Support" → "Trợ lý Pháp lý Khởi nghiệp & TMĐT".
- **Bonus memory (3đ)**: truyền 4 lượt gần nhất từ `st.session_state.messages` vào prompt; follow-up ngắn ("thế còn công ty cổ phần thì sao?") ghép câu hỏi trước vào query gửi `retrieve()`.
- **Bonus UI/UX (3đ)**: `st.progress(score)` mỗi nguồn, badge phân biệt `hybrid` vs `pageindex`, hiện `legal_ref` nổi bật, highlight từ khoá query, hiện thời gian retrieve.

**Repo Admin**: mời collaborator ở CP0, bật branch protection, hỗ trợ ai kẹt git.

✅ Nghiệm thu: `pytest tests/test_individual.py::TestTask10 -v` → **3 passed**; `streamlit run app.py` trả lời 2 câu flagship có citation kèm điều/khoản.

---

### 4.5 TRƯỜNG — Evaluation & QA

**`golden_dataset.json`** — **15–20 câu**, mỗi câu `{question, expected_answer, expected_context}`.
⚠️ **3 câu mẫu sẵn có nói về Shopee — phải xoá và viết lại toàn bộ theo chủ đề pháp lý.** Phải bám nội dung `data/standardized/` thật.
Phân bố gợi ý:
- ~60% trả lời trực tiếp từ 1 văn bản: hồ sơ đăng ký hộ KD, vốn điều lệ TNHH, ngưỡng thuế, hàng cấm bán trên sàn
- ~25% cần tổng hợp 2 nguồn: *"nên chọn hộ kinh doanh hay công ty TNHH khi bán trên TikTok Shop?"* (LDN 2020 + NĐ 01/2021 + TT 40/2021)
- ~15% ngoài domain để test fallback: *"cách nấu phở bò"*, *"thủ tục ly hôn"*

**`eval_pipeline.py`** — implement `evaluate_with_ragas()`, `compare_configs()`, `export_results()`. RAGAS 0.1.21 cần LLM judge, trỏ về OpenRouter:
```python
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(model=..., base_url="https://openrouter.ai/api/v1", api_key=os.getenv("OPENROUTER_API_KEY"))
result = evaluate(dataset, metrics=[...], llm=llm)
```
A/B: **Config A** = `retrieve(use_reranking=True)`; **Config B** = chỉ `semantic_search()` (dense-only).
💡 Giả thuyết đáng kiểm chứng để viết vào phân tích: hybrid sẽ thắng rõ ở câu hỏi chứa **số hiệu văn bản** ("Điều 87", "Nghị định 52") vì BM25 bắt chính xác token số, còn dense search hay trượt.

**`results.md`** — đủ 4 phần: bảng 4 metric × 2 config + cột Δ, mô tả config, worst 3 câu kèm **failure stage** (retrieval hay generation) + root cause, 3 đề xuất cải tiến kèm expected impact.

**Vai trò QA (xuyên suốt)**: sau mỗi merge chạy `pytest tests/test_individual.py -v`, đăng bảng *test fail/skip → task → chủ file*. Ở CP4 đây là việc quan trọng nhất của cả nhóm.

⚠️ Chạy **5 câu trước** để lấy số thật, chỉ mở rộng 15 câu nếu quota còn (50 req/ngày/tài khoản).

✅ Nghiệm thu: `golden_dataset.json` ≥15 câu đúng chủ đề; `python -m group_project.evaluation.eval_pipeline` chạy xong; `results.md` không còn ô trống.

---

## 5. Bảng cạm bẫy đã biết (đọc trước khi code)

| # | Vấn đề | Chỗ | Ai xử lý |
|---|---|---|---|
| 1 | **2 câu demo flagship không trả lời được từ 3 nguồn ban đầu** — thiếu NĐ 01/2021 (hộ KD) và TT 40/2021 (thuế) | `data/landing/legal/` | Tuấn Anh — tải đủ 6 văn bản ở mục 0 |
| 2 | **Ngưỡng doanh thu chịu thuế đã thay đổi** — dùng bản hết hiệu lực thì demo sai dù RAG chạy đúng | nguồn Task 1 | Tuấn Anh — tải bản đang hiệu lực, tự verify con số |
| 3 | `data/` **rỗng** dù README:30 và codelab:173 nói "có sẵn 11 file mẫu" | `data/landing/*` | Tuấn Anh |
| 4 | `CHUNK_SIZE=500/50` trong code vs **800/100** trong mọi tài liệu | `task4:44-45` | Tuấn Anh — đổi 800/100 |
| 5 | `SCORE_THRESHOLD=0.3` trong code vs **0.48** trong tài liệu | `task9:41` | Đức Anh — calibrate bằng đo thật |
| 6 | `rerank()` raise NotImplementedError ở **cả 3 nhánh** nhưng test gọi nó | `task7:175-184` | Kỳ Anh — nhánh `rrf` nhận list phẳng |
| 7 | `chroma_db/` không nằm trong `.gitignore` → mìn conflict binary | `.gitignore` | ✅ đã xử lý ở setup commit |
| 8 | `golden_dataset.json` chỉ có **3/15** câu và **sai chủ đề** (Shopee) | `group_project/evaluation/` | Trường — viết lại toàn bộ |
| 9 | `SYSTEM_PROMPT` + sidebar `app.py` + frontmatter README vẫn là chủ đề "E-commerce Support" cũ | `task10`, `app.py`, `README.md` | Hoàng (2 file đầu) + Tuấn Anh (README) |
| 10 | Task 9/10 dùng **relative import** → bắt buộc `python -m src.taskX` | `task9:28-31`, `task10:21` | Cả nhóm |
| 11 | Test **skip** khi gặp `NotImplementedError` → chưa làm gì vẫn "không đỏ". Cần `35 passed`, **`skipped` = mất điểm** | `tests/` | Trường (QA) |
| 12 | `UnicodeEncodeError` khi print tiếng Việt trên Windows | terminal | Cả nhóm — `$env:PYTHONIOENCODING="utf-8"` |
| 13 | Đổi corpus mà không xoá `chroma_db/` → chunk cũ lẫn mới, retrieval trả rác | `chroma_db/` | Tuấn Anh — `Remove-Item -Recurse -Force chroma_db` trước khi reindex |
| 14 | `fpdf2` font mặc định **không có tiếng Việt** → PDF ra toàn dấu hỏi | Task 1 | Tuấn Anh — nhúng font Unicode hoặc xuất `.docx` |
| 15 | `src/supervisor.py` được nhắc trong README:57 + mô tả Role 1 nhưng không tồn tại | — | Đức Anh — tuỳ chọn CP5 |

---

## 6. Verification — cách nghiệm thu

**Từng người, sau mỗi checkpoint:**
```powershell
$env:PYTHONIOENCODING="utf-8"
python -m pytest tests/test_individual.py::TestTask6 -v      # đổi số theo task của mình
```

**Toàn pipeline (Trường chạy ở CP4, trên `main`):**
```powershell
git checkout main; git pull --rebase origin main
python -m pytest tests/test_individual.py -v
# MỤC TIÊU: 35 passed, 0 failed, 0 skipped
```

**Smoke test end-to-end (Đức Anh, CP4):**
```powershell
python -m src.task9_retrieval_pipeline      # query cuối "xyzabc123nonsense" phải rơi vào [pageindex]
python -m src.task10_generation             # output phải có citation dạng [Tên văn bản, Điều X]
```

**Chatbot (Hoàng, CP5):** `streamlit run app.py`
Kiểm 4 thứ: (1) 2 câu flagship trả lời đúng + có citation điều/khoản; (2) expander nguồn hiện score; (3) follow-up ngắn vẫn hiểu ngữ cảnh; (4) câu ngoài domain trả "Tôi không thể xác minh thông tin này từ nguồn hiện có".

**Evaluation (Trường, CP5):** `python -m group_project.evaluation.eval_pipeline`
Kiểm: `results.md` đủ 4 metric × 2 config + Δ, worst 3, 3 đề xuất.

**Bảng đối chiếu điểm cuối cùng (tham chiếu README mục "Chấm Điểm"):**

| Hạng mục | Điểm | Bằng chứng |
|---|---|---|
| Task 1–10 | 50 | `35 passed` |
| Chatbot demo + tích hợp + kiến trúc + chất lượng | 18 | Streamlit chạy live, README có diagram |
| Evaluation | 12 | `results.md` đủ 4 phần |
| Bonus: TF-IDF vs BM25 (5) + HyDE (5) + Deploy HF (4) + Memory (3) + UI/UX (3) | 20 | Demo CP6 + link HF Space |
| **Tổng** | **100** | |

---

## 7. Prompt khởi động cho từng agent (dán nguyên khối vào đầu phiên chat)

**Tuấn Anh (Data & Indexing Lead):**
> Đọc `CLAUDE.md` và mục 0 + 4.1 của `TEAM_PLAN.md` trước khi làm gì. Tôi là **Tuấn Anh — Data & Indexing Lead**. Tôi CHỈ được sửa: `data/**`, `src/task1_collect_legal_docs.py`, `src/task2_crawl_news.py`, `src/task3_convert_markdown.py`, `src/task4_chunking_indexing.py`, `README.md`, `requirements.txt`, `.gitignore`, `.gitattributes`, `CLAUDE.md`, `TEAM_PLAN.md`, `.env.example`. Tuyệt đối không sửa/tạo/xoá file khác — kể cả khi thấy có bug, hãy báo tôi. Không `git add .`, không `git push --force`, không sửa `tests/`. Chủ đề: **Trợ lý Pháp lý Khởi nghiệp & TMĐT**. Nhiệm vụ: Task 1–4. Tải 6 văn bản theo bảng ở mục 0, ưu tiên NĐ 01/2021 và TT 40/2021 trước (2 câu demo flagship phụ thuộc chúng). Task 4: `CHUNK_SIZE=800`, `CHUNK_OVERLAP=100`, gắn metadata `doc_title`, `legal_ref` (regex `Điều\s+\d+`), `customer_role`; thêm `get_embedding_model()` và `get_collection()` ở module level cho Đức Anh import. Lưu ý `fpdf2` font mặc định không có tiếng Việt.

**Đức Anh (RAG Architect & Dense Search):**
> Đọc `CLAUDE.md` và mục 4.2 của `TEAM_PLAN.md` trước. Tôi là **Đức Anh — RAG Architect & Dense Search**. Tôi CHỈ được sửa: `src/task5_semantic_search.py`, `src/task9_retrieval_pipeline.py`, `src/supervisor.py`. Không sửa file khác, không sửa `tests/`, không sửa `requirements.txt` (báo Tuấn Anh), không `git add .`. Nhiệm vụ: (1) Task 5 `semantic_search` — import `get_embedding_model()`/`get_collection()` từ `task4_chunking_indexing`, đừng khởi tạo model lần nữa. (2) Task 9 `retrieve()` — so `score_threshold` với **điểm cosine gốc `dense_results[0]["score"]`**, KHÔNG phải điểm RRF đã fuse (RRF luôn ≈0.016 nên fallback sẽ không bao giờ chạy). Calibrate threshold bằng cách đo thật vài query liên quan vs lạc đề. Chạy `python -m src.task9_retrieval_pipeline` (relative import, bắt buộc `-m` từ root).

**Kỳ Anh (Sparse Search & Reranking):**
> Đọc `CLAUDE.md` và mục 4.3 của `TEAM_PLAN.md` trước. Tôi là **Kỳ Anh — Sparse Search & Reranking Dev**. Tôi CHỈ được sửa: `src/task6_lexical_search.py`, `src/task7_reranking.py`, `src/task8_pageindex_vectorless.py`. Không sửa file khác, không sửa `tests/`, không `git add .`. Chủ đề: trợ lý pháp lý (văn bản luật VN). Nhiệm vụ: (1) Task 6 BM25 — load `CORPUS` **lazy** trong hàm, không ở module level, nếu không `import src.task9` sẽ nổ khi chưa có data. (2) Task 7 RRF — `rerank()` hiện raise NotImplementedError ở cả 3 nhánh nhưng test gọi nó với 1 list phẳng, sửa nhánh `"rrf"` thành `return rerank_rrf([candidates], top_k=top_k)`. (3) Task 8 — nhóm chưa có PAGEINDEX_API_KEY, implement local vectorless retriever: cắt `data/standardized/**/*.md` theo heading markdown thành cây mục lục, chấm điểm theo độ trùng từ khoá (tiêu đề nhân hệ số 2), trả nguyên section không chunk, giữ `'source': 'pageindex'`, trả `[]` thay vì raise khi không có data.

**Hoàng (Frontend & Chatbot):**
> Đọc `CLAUDE.md` và mục 4.4 của `TEAM_PLAN.md` trước. Tôi là **Hoàng — Frontend & Chatbot Dev**. Tôi CHỈ được sửa: `src/task10_generation.py` và `app.py`. Không sửa file khác, không sửa `tests/`, không `git add .`. Chủ đề nhóm đã đổi sang **Trợ lý Pháp lý Khởi nghiệp & TMĐT** — phải sửa `SYSTEM_PROMPT`, tiêu đề và 5 câu hỏi gợi ý trong sidebar cho khớp. Nhiệm vụ: (1) `reorder_for_llm` = `chunks[::2] + chunks[1::2][::-1]`. (2) `format_context` BẮT BUỘC chèn `metadata['source']` (test assert tên file có trong context), nên chèn thêm `doc_title` + `legal_ref` để LLM cite dạng `[Nghị định 01/2021/NĐ-CP, Điều 87]`. (3) `generate_with_citation` gọi OpenRouter qua OpenAI SDK `base_url="https://openrouter.ai/api/v1"`, model `:free`, bọc try/except để hết quota thì trả message lỗi chứ không raise. (4) `app.py` đã xong ~90% — xoá TODO chết dòng 113–118, thêm conversation memory 4 lượt và UI hiển thị score/badge nguồn/legal_ref. Chạy `python -m src.task10_generation` để test.

**Trường (Evaluation & QA):**
> Đọc `CLAUDE.md` và mục 4.5 của `TEAM_PLAN.md` trước. Tôi là **Trường — Evaluation & QA Engineer**. Tôi CHỈ được sửa file trong `group_project/**`. Không sửa `src/`, không sửa `app.py`, TUYỆT ĐỐI không sửa `tests/` (file chấm điểm — sửa là gian lận). Không `git add .`. Chủ đề nhóm là **Trợ lý Pháp lý Khởi nghiệp & TMĐT** (Luật Doanh nghiệp 2020, NĐ 01/2021, TT 40/2021, NĐ 52/2013, NĐ 85/2021, quy định TikTok Shop/Shopee). Nhiệm vụ: (1) **Xoá 3 câu mẫu Shopee cũ**, viết `golden_dataset.json` 15–20 câu mới bám `data/standardized/` thật — 60% trả lời trực tiếp, 25% cần tổng hợp 2 nguồn, 15% ngoài domain để test fallback. (2) Implement `evaluate_with_ragas`, `compare_configs` (A: `retrieve(use_reranking=True)` vs B: dense-only `semantic_search`), `export_results` — RAGAS judge trỏ về OpenRouter qua `ChatOpenAI(base_url=...)`. (3) Điền `results.md` đủ 4 phần. Quota OpenRouter free 50 req/ngày cho CẢ tài khoản: chạy 5 câu trước, chỉ mở rộng nếu còn quota. Tôi cũng là QA: sau mỗi lần `main` cập nhật, chạy `python -m pytest tests/test_individual.py -v` và báo bảng *test fail/skip → task → chủ file*.
