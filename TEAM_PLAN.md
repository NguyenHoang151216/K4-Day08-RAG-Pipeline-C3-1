# KẾ HOẠCH TRIỂN KHAI — Lab 08 RAG Pipeline (Nhóm 5 người, 180 phút)

> **Cách dùng file này**: đọc mục 1 (vai của bạn) → mục 2 (timeline) → mục 3 (quy trình git, BẮT BUỘC) → mục 4.x (chi tiết phần của bạn) → mục 7 (prompt dán vào agent của bạn).
> Quy tắc chống conflict bản rút gọn nằm ở `CLAUDE.md` — agent của bạn sẽ tự đọc file đó.

---

## Context

Repo này là **starter template**: toàn bộ hàm nghiệp vụ trong `src/task1..10` đều là stub `raise NotImplementedError`, lời giải mẫu nằm trong comment. Thư mục `data/` rỗng (chỉ có `.gitkeep`), `chroma_db/` chưa tồn tại, `golden_dataset.json` mới có 3/15 câu.

Nhóm 5 người (Tuấn Anh, Đức Anh, Kỳ Anh, Hoàng, Trường) cần hoàn thành trong **180 phút live tại lớp**, chưa có API key nào, dùng quy trình **branch riêng + PR**. Mục tiêu: **100/100** = 50đ pipeline (35/35 pytest) + 30đ bài nhóm (chatbot + RAGAS eval) + 20đ bonus.

Rủi ro lớn nhất không phải code mà là **3 thứ tốn wall-clock**: cài dependency (~10 phút), tải model `BAAI/bge-m3` (2.27 GB), và thu thập dữ liệu thật. Plan này thiết kế để 5 người chạy song song gần như không chặn nhau, và **5 vùng file tách rời hoàn toàn** để PR không bao giờ conflict.

---

## 1. Phân vai (theo Phương Án B của LAB_GUIDE — coach sẽ nhận ra)

| Người | Role | Nhiệm vụ | File sở hữu (ĐỘC QUYỀN) |
|---|---|---|---|
| **Tuấn Anh** | Role 1 — Team Leader & RAG Architect | Task 9, tích hợp, **merge captain**, README kiến trúc, thuyết trình | `src/task9_retrieval_pipeline.py`, `README.md`, `requirements.txt`, `.gitignore`, `.gitattributes`, `CLAUDE.md`, `TEAM_PLAN.md`, `.env.example`, `src/supervisor.py` |
| **Đức Anh** | Role 2 — Data & Dense Search Dev | Task 1–3 (thu thập), Task 4 (chunk+index), Task 5 (semantic + HyDE), deploy HF | `data/**`, `src/task1_*.py`, `src/task2_*.py`, `src/task3_*.py`, `src/task4_*.py`, `src/task5_*.py` |
| **Kỳ Anh** | Role 3 — Sparse Search & Reranking Dev | Task 6 (BM25 + TF-IDF), Task 7 (RRF), Task 8 (vectorless fallback) | `src/task6_*.py`, `src/task7_*.py`, `src/task8_*.py` |
| **Hoàng** | Role 4 — Frontend & Chatbot Dev + **Repo Admin** | Task 10 (generation), `app.py`, conversation memory, UI/UX | `src/task10_generation.py`, `app.py` |
| **Trường** | Role 5 — Evaluation & QA Engineer | Golden dataset, RAGAS, A/B, báo cáo, **chạy pytest cho cả team** | `group_project/**` |

**Không ai được sửa `tests/`** — đó là file chấm điểm.
**Không ai sửa file ngoài vùng của mình.** Cần đổi file người khác → nhắn trong group chat, chủ file tự sửa.

---

## 2. Timeline 7 Checkpoint

### CP0 — Setup (0:00 – 0:10) — **AI CŨNG LÀM ĐỒNG THỜI**

Mở **2 terminal** mỗi người. Terminal A chạy nền suốt CP0–CP1, Terminal B để làm việc.

**Terminal A (chạy nền, không đợi):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
> Nếu `pip install -r requirements.txt` **đứt giữa chừng** vì `pageindex` hoặc `ragas` (Python 3.12 hay xung đột), chạy đợt lõi trước — đủ để qua 35 test:
> ```powershell
> pip install python-dotenv requests numpy "markitdown[pdf]" fpdf2 langchain-text-splitters sentence-transformers chromadb rank-bm25 scikit-learn openai streamlit pytest crawl4ai
> playwright install chromium
> pip install ragas==0.1.21 datasets langchain-openai   # đợt 2, chỉ Trường bắt buộc
> ```

Ngay sau khi `sentence-transformers` cài xong, **mọi người** chạy tải model nền:
```powershell
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3')"
```
2.27 GB — cứ để chạy, sang CP1 làm việc khác.

**Terminal B — việc riêng từng người:**

| Người | Việc CP0 |
|---|---|
| **Hoàng** | GitHub repo → Settings → Collaborators → mời 4 người còn lại (**Write**), riêng Tuấn Anh cấp **Maintain** để merge PR. Bật branch protection cho `main`: *Require a pull request before merging* (0 approval để merge nhanh). |
| **Tuấn Anh** | ✅ **ĐÃ XONG** — setup commit (`.gitignore` + `.gitattributes` + `CLAUDE.md` + `TEAM_PLAN.md`) đã ở trên `main`. |
| **Cả 5** | `git clone` → `git pull origin main` → chạy mục 3.2 (config git). Đăng ký https://openrouter.ai → Keys → Create key. Copy `.env.example` → `.env`, điền `OPENROUTER_API_KEY`. Test: `python -c "import os,dotenv;dotenv.load_dotenv();print(os.getenv('OPENROUTER_API_KEY')[:12])"` |
| **Trường** | Đăng ký thêm https://pageindex.ai lấy `PAGEINDEX_API_KEY` (nếu được), gửi Kỳ Anh. Không có cũng không sao — xem Plan B Task 8. |

✅ **Pass CP0**: `import chromadb, sentence_transformers, streamlit` không lỗi; có `.env` với OpenRouter key; 4 người nhận được lời mời collaborator.

> ⚠️ **`.env` KHÔNG BAO GIỜ commit.** Chia sẻ key qua chat riêng, không qua git.

---

### CP1 — Thu thập & chuẩn hoá (0:10 – 0:35)

| Người | Việc | Branch |
|---|---|---|
| **Đức Anh** | Task 1 + 2 + 3 | `feat/ducanh-cp1-data` |
| **Tuấn Anh** | **Hỗ trợ Đức Anh**: nhận 3/5 URL crawl, gửi file JSON qua chat để Đức Anh commit (KHÔNG tự commit vào `data/`) | — |
| **Kỳ Anh** | Task 7 (`rerank_rrf` + `rerank`) — thuần thuật toán, test bằng dummy data, **không cần chờ ai** | `feat/kyanh-cp1-rerank` |
| **Hoàng** | Task 10 phần thuần: `reorder_for_llm()` + `format_context()` (không cần LLM, không cần data) | `feat/hoang-cp1-reorder` |
| **Trường** | Viết khung 15 câu `golden_dataset.json` (câu hỏi chung về chính sách TMĐT, tinh chỉnh sau khi có data thật) + đọc rubric | `feat/truong-cp1-golden` |

✅ **Pass CP1**: ≥3 file PDF/DOCX trong `data/landing/legal/` (mỗi file >1KB), ≥5 file JSON trong `data/landing/news/` (mỗi file >500 bytes, có field `url`), có `.md` tương ứng trong `data/standardized/`. PR của Đức Anh **merge đầu tiên**.

---

### CP2 — Chunking, Indexing & Search (0:35 – 1:00)

| Người | Việc | Branch |
|---|---|---|
| **Đức Anh** | Task 4 (chunk 800/100, gắn `customer_role`, index ChromaDB) → sau đó Task 5 (`semantic_search`) | `feat/ducanh-cp2-index` |
| **Kỳ Anh** | Task 6 (`build_bm25_index` + `lexical_search`) — cần `data/standardized/` từ CP1 | `feat/kyanh-cp2-bm25` |
| **Hoàng** | Task 10: gọi LLM OpenRouter với **fake chunks hardcode**, chưa nối `retrieve()` | `feat/hoang-cp2-llm` |
| **Trường** | Đọc `data/standardized/*.md`, viết lại `golden_dataset.json` **15–20 câu bám sát nội dung thật** | `feat/truong-cp2-golden` |
| **Tuấn Anh** | Viết khung Task 9 (chưa chạy được), review + merge PR CP1 | `feat/tuananh-cp2-pipeline` |

🚦 **DECISION GATE — cuối CP2 (1:00)**: nếu `bge-m3` **chưa tải xong**, Đức Anh đổi 2 dòng trong `task4_chunking_indexing.py`:
```python
EMBEDDING_MODEL = "intfloat/multilingual-e5-small"   # 471MB thay vì 2.27GB
EMBEDDING_DIM = 384
```
rồi báo cả nhóm tải model đó và index lại. Ghi lý do vào README. **Không chần chừ quá 1:00.**

✅ **Pass CP2**: `chroma_db/` tồn tại, `collection.count() > 0`; `pytest tests/test_individual.py::TestTask4 -v` và `::TestTask6` xanh.

---

### CP3 — Reranking & Fallback (1:00 – 1:20)

| Người | Việc | Branch |
|---|---|---|
| **Kỳ Anh** | Task 8 vectorless fallback (xem Plan B mục 4.2) | `feat/kyanh-cp3-pageindex` |
| **Tuấn Anh** | Task 9 `retrieve()` + **calibrate `SCORE_THRESHOLD` bằng đo thật** | `feat/tuananh-cp3-pipeline` |
| **Đức Anh** | Bonus HyDE trong `task5_semantic_search.py` | `feat/ducanh-cp3-hyde` |
| **Hoàng** | Nối `generate_with_citation()` → `retrieve()` thật, wire vào `app.py` | `feat/hoang-cp3-wire` |
| **Trường** | Viết `evaluate_with_ragas()` + `compare_configs()` | `feat/truong-cp3-ragas` |

✅ **Pass CP3**: `rerank_rrf([dense, sparse])` gộp đúng; `pageindex_search()` trả list có `source: "pageindex"`; Tuấn Anh đọc được bảng điểm cosine của query liên quan vs lạc đề.

---

### CP4 — Chốt 50đ pipeline (1:20 – 1:45) ⭐ MỐC QUAN TRỌNG NHẤT

- **Tuấn Anh**: merge toàn bộ PR → `main`, hoàn tất Task 9.
- **Trường (QA)**: trên `main` mới nhất chạy
  ```powershell
  $env:PYTHONIOENCODING="utf-8"
  python -m pytest tests/test_individual.py -v
  ```
  Ghi ra bảng **test nào fail/skip → thuộc task nào → chủ file nào**, đăng vào group chat.
- **4 người còn lại**: fix **chỉ trong file của mình**, push hotfix branch `fix/<tên>-taskN`.

✅ **Pass CP4**: `35 passed` (không có `skipped` — skip nghĩa là chưa implement, **không được điểm**).

---

### CP5 — Bài nhóm 30đ + Bonus (1:45 – 2:15)

| Người | Việc |
|---|---|
| **Trường** | Chạy RAGAS 4 metric × 2 config (A: hybrid+rerank / B: dense-only), điền `results.md`: bảng điểm, Δ, worst 3, 3 đề xuất |
| **Hoàng** | Conversation memory (multi-turn) + UI hiển thị score/highlight trong `app.py` |
| **Đức Anh** | `git add -f chroma_db/` (LFS) + deploy Hugging Face Spaces |
| **Tuấn Anh** | README: diagram kiến trúc + bảng phân công 5 người + (nếu dư giờ) `src/supervisor.py` |
| **Kỳ Anh** | Chuẩn bị slide/notes giải thích BM25 vs TF-IDF (bonus 5đ) |

⚠️ **Rate limit RAGAS**: model `:free` của OpenRouter giới hạn **50 request/ngày cho cả tài khoản**. RAGAS gọi ~4–8 lần/câu/metric. → Trường chạy **5 câu trước** để lấy số, chỉ chạy full 15 câu nếu quota còn. Dùng **key OpenRouter của người khác trong nhóm** cho config B nếu hết quota.

---

### CP6 — Demo (2:15 – 3:00)

| Người | Phần trình bày |
|---|---|
| **Tuấn Anh** | Tổng quan kiến trúc + luồng dữ liệu + phân công |
| **Đức Anh** | Nguồn data, lý do chunk 800/100, `customer_role`, HyDE |
| **Kỳ Anh** | BM25 vs TF-IDF, công thức RRF, **cái bẫy fallback** (bonus 5đ) |
| **Hoàng** | Live demo Streamlit + citation + memory |
| **Trường** | Bảng RAGAS A/B + worst performers + đề xuất |

Cuối cùng: `git push origin main`, gửi link repo + link HF Space.

---

## 3. QUY TRÌNH GITHUB — CHỐNG CONFLICT

### 3.1 Setup commit — ✅ ĐÃ XONG, đã nằm trên `main`

Ba thay đổi đã được đẩy lên `main` trước khi ai tạo branch:

**a) `.gitignore` — đã thêm `chroma_db/`** (trước đó THIẾU, đây là mìn conflict lớn nhất: file sqlite binary, mỗi lần index lại là khác, 5 người push vào = vỡ trận)

**b) `.gitattributes` — đã thêm `* text=auto` ở đầu file**, chuẩn hoá line ending. Index của repo hiện đã 100% LF nên dòng này **không gây diff giả**, chỉ chặn trường hợp ai đó có `core.autocrlf=false` commit CRLF làm cả file bị đánh dấu "thay đổi toàn bộ".

**c) `CLAUDE.md` ở root** — ⭐ **biện pháp chống conflict quan trọng nhất**: chứa bảng chủ quyền file, danh sách lệnh git bị cấm và contract giữa các module. Claude Code **tự đọc file này**, nên cả 5 agent đều bị ràng buộc mà không ai phải nhắc.

### 3.2 Cấu hình git — cả 5 người chạy 1 lần, NGAY BÂY GIỜ

```powershell
git config --global pull.rebase true          # pull = rebase, không tạo merge commit rác
git config --global core.autocrlf true        # Windows
git config --global user.name "Tên Của Bạn"
git config --global user.email "email@cua.ban"
git lfs install
```

### 3.3 Vòng lặp làm việc chuẩn — lặp lại MỖI CHECKPOINT

```powershell
# 1. Luôn bắt đầu từ main mới nhất
git checkout main
git pull --rebase origin main

# 2. Tạo branch mới cho checkpoint này (branch NGẮN HẠN, sống < 25 phút)
git checkout -b feat/kyanh-cp2-bm25

# 3. ... code ...

# 4. Commit — LIỆT KÊ FILE CỤ THỂ, không bao giờ dùng "git add ."
git add src/task6_lexical_search.py
git commit -m "feat(task6): BM25 lexical search với tokenizer tiếng Việt"

# 5. Trước khi push, đồng bộ lại main (bắt lỗi sớm khi conflict còn nhỏ)
git fetch origin
git rebase origin/main

# 6. Push
git push -u origin feat/kyanh-cp2-bm25

# 7. Mở PR
gh pr create --base main --title "[CP2][Kỳ Anh] Task 6 — BM25" --body "Files: src/task6_lexical_search.py
Test: pytest tests/test_individual.py::TestTask6 -v -> 4 passed"
```

### 3.4 Quy tắc vàng (dán vào group chat)

1. **Branch sống ngắn.** 1 branch = 1 checkpoint. Không giữ branch qua 2 checkpoint.
2. **Đặt tên branch phẳng**: `feat/tên-cpN-mô-tả`. **KHÔNG** dùng `feat/tên/cpN` — nếu ai đó lỡ tạo branch tên `feat/tên` thì mọi branch `feat/tên/...` sẽ lỗi `cannot lock ref`.
3. **Không bao giờ `git add .`** — nó sẽ nuốt `chroma_db/`, `.env`, file rác của agent.
4. **Không bao giờ force-push `main`.**
5. **Chỉ Tuấn Anh merge PR.** Người khác mở PR rồi báo trong chat.
6. **Thứ tự merge cố định**: Đức Anh (data/index) → Kỳ Anh (search) → Hoàng (gen/app) → Trường (eval) → Tuấn Anh (pipeline). Vì downstream phụ thuộc upstream.
7. **Sau mỗi lần merge**, Tuấn Anh nhắn group `"main updated"` → 4 người còn lại chạy `git pull --rebase origin main`.
8. **`chroma_db/` không vào git** cho tới CP5. Ai cần index thì tự chạy `python -m src.task4_chunking_indexing` (~2 phút).
9. **`.env` không bao giờ vào git.** Nếu lỡ commit → đổi key ngay, key đã lộ vĩnh viễn trong lịch sử git.
10. **Merge PR bằng "Squash and merge"** — lịch sử `main` sạch, dễ revert nếu hỏng.

### 3.5 Xử lý khi VẪN bị conflict

Với file ownership chặt, conflict thật sự chỉ xảy ra ở `README.md` hoặc khi ai đó phá luật.

```powershell
git fetch origin
git rebase origin/main
# → CONFLICT (content): Merge conflict in <file>

git status                       # xem file nào conflict
code <file>                      # sửa: xoá <<<<<<<, =======, >>>>>>>, GIỮ CẢ HAI PHẦN nếu là README
git add <file>
git rebase --continue
git push --force-with-lease origin feat/<tên>-cpN-...   # CHỈ trên branch riêng, KHÔNG BAO GIỜ trên main
```

**Nếu rối quá / mất phương hướng — đường thoát an toàn (không mất code):**
```powershell
git rebase --abort                      # quay về trạng thái trước rebase
git branch backup-cua-toi               # sao lưu công việc
# rồi báo Tuấn Anh, đừng tự xử lý tiếp
```

**Conflict trên file binary (`chroma_db/*.sqlite3`, `*.pdf`)** — không merge được, chọn một bên:
```powershell
git checkout --theirs chroma_db/chroma.sqlite3   # lấy bản trên main
# hoặc
git checkout --ours  chroma_db/chroma.sqlite3    # giữ bản của mình
git add chroma_db/chroma.sqlite3
```
Tốt nhất: **xoá thư mục và index lại**, đừng merge binary.

### 3.6 Nội quy riêng cho AGENT (5 agent chạy song song)

Mỗi người mở đầu phiên chat với agent bằng **prompt ở mục 7**.

Ba lỗi agent hay gây ra nhất trong repo này — nói trước để tránh:
- Agent "tiện tay" sửa `requirements.txt` khi thiếu package → **conflict 5 chiều**. Luật: báo Tuấn Anh.
- Agent sửa `tests/test_individual.py` cho test pass → **gian lận, mất điểm**. Luật: cấm tuyệt đối.
- Agent chạy `git add .` rồi commit cả `chroma_db/` 200MB → repo phình, PR không mở nổi. Luật: chỉ `git add <file cụ thể>`.

---

## 4. Nhiệm vụ chi tiết & đầu ra mong muốn

### 4.1 ĐỨC ANH — Task 1,2,3,4,5

**Task 1** → `data/landing/legal/` ≥ 3 file PDF/DOCX, mỗi file **> 1KB**.

⚠️ help.shopee.vn là SPA JavaScript — crawl thường chỉ ra tiêu đề rỗng. **Đi thẳng Plan B ngay từ đầu**, nguồn ổn định và vẫn đúng chủ đề "chính sách TMĐT":
- Nghị định 52/2013/NĐ-CP về Thương mại điện tử (PDF trên vanban.chinhphu.vn / thuvienphapluat.vn)
- Nghị định 85/2021/NĐ-CP sửa đổi NĐ 52 về TMĐT
- Luật Bảo vệ quyền lợi người tiêu dùng 2023
- Điều khoản dịch vụ / Chính sách bảo mật bản HTML tĩnh của Tiki/Lazada → dùng `fpdf2` (đã có trong requirements) chuyển thành PDF

Đặt tên không dấu: `nd-52-2013-thuong-mai-dien-tu.pdf`, `nd-85-2021-sua-doi.pdf`, `luat-bvqlntd-2023.pdf`.

**Task 2** → `data/landing/news/` ≥ 5 file JSON, mỗi file **> 500 bytes**, **bắt buộc có key `url`** (test kiểm tra). Schema:
```json
{"url": "...", "title": "...", "date_crawled": "2026-08-04T10:00:00", "content_markdown": "..."}
```
Nguồn HTML tĩnh dễ crawl: bài về TMĐT trên VnExpress Kinh doanh, Tuổi Trẻ, Vietnamnet. Nếu `crawl4ai` lỗi browser → `playwright install chromium`; nếu vẫn lỗi, fallback `requests` + `BeautifulSoup`, vẫn ghi đủ metadata.

**Task 3** → `data/standardized/legal/*.md` + `data/standardized/news/*.md`, mỗi file **> 200 ký tự**. Bỏ 2 dòng `raise NotImplementedError`, bật code mẫu trong comment. Header metadata cho news như comment đã gợi ý.

**Task 4** → `chroma_db/` với `collection.count() > 0`. Sửa config:
```python
CHUNK_SIZE = 800        # docs & CP2 pass criteria dùng 800, không phải 500 như stub
CHUNK_OVERLAP = 100
```
Thêm 2 hàm module-level để Task 5 import lại (đừng để Task 5 khởi tạo model lần nữa):
```python
def get_embedding_model():   # cache module-level, tải 1 lần
def get_collection():        # chromadb.PersistentClient(str(CHROMA_DIR)).get_collection(COLLECTION_NAME)
```
Gắn `customer_role` vào metadata mỗi chunk (`buyer`/`seller`/`both`) — yêu cầu K4 Variant, có trong bảng troubleshooting, coach hay hỏi:
```python
"metadata": {**doc["metadata"], "chunk_index": i, "customer_role": role}
```
Quy tắc suy ra `role`: file có "nguoi-ban"/"seller" → `seller`; "nguoi-mua"/"buyer" → `buyer`; còn lại → `both`.

**Task 5** → `semantic_search(query, top_k)` trả list sorted desc theo cosine `[0,1]`. Dùng code mẫu trong comment (`score = max(0.0, 1.0 - distance)`).
**Bonus HyDE (5đ)**: thêm `semantic_search_hyde(query, top_k)` — gọi LLM sinh 1 đoạn trả lời giả định rồi embed đoạn đó thay vì embed câu hỏi. Giữ `semantic_search()` gốc nguyên vẹn (Task 9 gọi nó).

✅ Nghiệm thu: `pytest tests/test_individual.py::TestTask1 ::TestTask2 ::TestTask3 ::TestTask4 ::TestTask5 -v` → **19 passed**.

---

### 4.2 KỲ ANH — Task 6,7,8

**Task 6** → `lexical_search(query, top_k)`, BM25Okapi trên `data/standardized/**/*.md`.
- `CORPUS` phải load **lazy** (hàm `_load_corpus()` gọi lần đầu), không load ở module level — nếu không, `import src.task9` sẽ nổ khi chưa có data.
- Tokenizer tiếng Việt: `text.lower()` rồi tách theo regex `\w+` (bỏ dấu câu) — đủ tốt, đừng cài `underthesea` (mất 5 phút cài).
- Test yêu cầu score sorted desc **và** có ít nhất 1 score > 0 với query `"payment methods"`. Nếu corpus thuần tiếng Việt, đảm bảo `lexical_search` trả `[]` khi không match (test sẽ `skipTest`, không fail) — **nhưng để được điểm hãy chèn ít nhất 1 tài liệu song ngữ/tiếng Anh**, phối hợp với Đức Anh.

**Task 7** → `rerank_rrf(ranked_lists, top_k, k=60)` theo `RRF(d) = Σ 1/(k + rank)`.
⚠️ **Hàm `rerank()` hiện tại raise NotImplementedError ở cả 3 nhánh** — test gọi `rerank(query, candidates, top_k)` với **1 list phẳng**. Sửa nhánh `rrf` để nhận list phẳng:
```python
elif method == "rrf":
    return rerank_rrf([candidates], top_k=top_k)
```
**Bonus 5đ**: thêm `lexical_search_tfidf()` dùng `sklearn.feature_extraction.text.TfidfVectorizer` (đã có trong requirements) và chuẩn bị giải thích khác biệt TF-IDF vs BM25 (BM25 có bão hoà TF `k1` và chuẩn hoá độ dài `b`; TF-IDF thì không) cho demo CP6.

**Task 8** → `pageindex_search(query, top_k)` trả list có `'source': 'pageindex'`.
**Plan B (không có API key — khả năng cao)**: implement **local vectorless retriever** cùng interface:
```python
# Đọc data/standardized/**/*.md, cắt theo heading markdown (#, ##, ###) thành cây mục lục,
# chấm điểm mỗi section bằng độ trùng từ khoá query vs (tiêu đề section × 2 + nội dung),
# trả về nguyên cả section (KHÔNG chunk) — đúng tinh thần "vectorless, structure-based".
# Ghi rõ trong docstring: "Local implementation of vectorless structural retrieval
# (PageIndex-compatible interface). Không dùng embedding/vector store."
```
Giữ `source: "pageindex"` để đúng contract Task 9. **Phải trả `[]` (không raise) khi không có data** — Task 9 test gọi với `score_threshold=0.99` sẽ ép chạy nhánh này.

✅ Nghiệm thu: `pytest tests/test_individual.py::TestTask6 ::TestTask7 ::TestTask8 -v` → **9 passed**.

---

### 4.3 TUẤN ANH — Task 9 + tích hợp

**Task 9** → `retrieve()` theo đúng code mẫu trong comment. Điểm mấu chốt:

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

**Calibrate `SCORE_THRESHOLD` bằng đo thật** (đừng copy 0.3 hay 0.48 mù quáng) — chạy và ghi số vào comment:
```powershell
python -c "from src.task5_semantic_search import semantic_search as s; [print(round(s(q,1)[0]['score'],3), q) for q in ['chính sách hoàn tiền','phương thức thanh toán','xyzabc123nonsense','công thức nấu phở']]"
```
→ chọn ngưỡng nằm giữa 2 cụm điểm. Ghi rõ: `SCORE_THRESHOLD = 0.48  # đo được: liên quan 0.62-0.71, lạc đề 0.21-0.33`.

**Ràng buộc test**: mọi item trả về phải có `content`, `score`, `source ∈ {"hybrid","pageindex"}`; `len(result) <= top_k`; gọi với query rác + threshold 0.99 **không được crash**.

**Việc tích hợp** (quan trọng ngang Task 9): merge PR đúng thứ tự, giữ `main` luôn xanh, thông báo `"main updated"` sau mỗi merge, và ở CP4 điều phối fix theo bảng lỗi của Trường.

**README (CP5)**: điền diagram kiến trúc + bảng phân công 5 người + ghi rõ config đã chọn (chunk 800/100, model gì, threshold bao nhiêu và **vì sao**).

**Tuỳ chọn nếu dư giờ**: `src/supervisor.py` ~40 dòng chạy `semantic_search` và `lexical_search` song song bằng `concurrent.futures.ThreadPoolExecutor` — LAB_GUIDE có nhắc file này trong mô tả Role 1, coach có thể hỏi.

---

### 4.4 HOÀNG — Task 10 + app.py + Repo Admin

**Task 10** — 3 hàm:
- `reorder_for_llm(chunks)`: `front = chunks[::2]; back = chunks[1::2]; return front + back[::-1]`. Test kiểm tra **giữ nguyên số lượng** và **phần tử đầu vẫn là chunk 0**.
- `format_context(chunks)`: **bắt buộc chèn `metadata['source']`** vào string output (test assert tên file có trong context).
- `generate_with_citation(query, top_k)` → `{'answer', 'sources', 'retrieval_source'}`, `answer` là str không rỗng.

Gọi OpenRouter qua OpenAI SDK:
```python
client = OpenAI(api_key=os.getenv("OPENROUTER_API_KEY"), base_url="https://openrouter.ai/api/v1")
```
Chọn `LLM_MODEL` là model `:free` (xem https://openrouter.ai/models?max_price=0). Bọc `try/except` quanh lời gọi LLM: hết quota thì trả `answer` báo lỗi rõ ràng thay vì raise — để test Task 10 vẫn pass và app không sập giữa demo.

**`app.py`** đã hoàn thiện ~90% (sidebar, slider top_k, expander nguồn, đã import sẵn `generate_with_citation`). Việc cần làm:
- Xoá khối TODO chết ở dòng 113–118.
- **Bonus conversation memory (3đ)**: truyền 4 lượt hội thoại gần nhất từ `st.session_state.messages` vào prompt; với follow-up ngắn ("còn phí ship thì sao?"), ghép câu hỏi trước vào query gửi `retrieve()`.
- **Bonus UI/UX (3đ)**: `st.progress(score)` cho từng nguồn, badge màu phân biệt `hybrid` vs `pageindex`, highlight từ khoá query trong đoạn trích, hiện thời gian retrieve.

**Repo Admin**: mời collaborator ở CP0, bật branch protection, hỗ trợ ai kẹt git.

✅ Nghiệm thu: `pytest tests/test_individual.py::TestTask10 -v` → **3 passed**; `streamlit run app.py` trả lời có citation `[Nguồn, Năm]` + hiện nguồn.

---

### 4.5 TRƯỜNG — Evaluation & QA

**`golden_dataset.json`** — **15–20 câu**, mỗi câu `{question, expected_answer, expected_context}`. **Phải bám nội dung `data/standardized/` thật** (3 câu mẫu sẵn có đang nói về Shopee — nếu nhóm chuyển sang nguồn nghị định thì viết lại toàn bộ). Phân bố: ~60% câu trả lời được trực tiếp, ~25% cần tổng hợp 2 nguồn, ~15% câu ngoài domain (để test fallback).

**`eval_pipeline.py`** — implement `evaluate_with_ragas()`, `compare_configs()`, `export_results()`. RAGAS 0.1.21 cần LLM + embeddings judge; trỏ về OpenRouter:
```python
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(model=..., base_url="https://openrouter.ai/api/v1", api_key=os.getenv("OPENROUTER_API_KEY"))
result = evaluate(dataset, metrics=[...], llm=llm)
```
A/B: **Config A** = `retrieve(use_reranking=True)`; **Config B** = chỉ `semantic_search()` (dense-only).

**`results.md`** — điền đủ 4 phần: bảng 4 metric × 2 config + cột Δ, mô tả config, worst 3 câu kèm **failure stage** (retrieval hay generation) + root cause, 3 đề xuất cải tiến kèm expected impact.

**Vai trò QA (xuyên suốt)**: sau mỗi merge chạy `pytest tests/test_individual.py -v`, đăng bảng *test fail → task → chủ file*. Ở CP4 đây là việc quan trọng nhất của cả nhóm.

⚠️ Chạy **5 câu trước** để lấy số thật, chỉ mở rộng 15 câu nếu quota còn (50 req/ngày/tài khoản).

✅ Nghiệm thu: `golden_dataset.json` ≥15 câu; `python -m group_project.evaluation.eval_pipeline` chạy xong; `results.md` không còn ô trống.

---

## 5. Bảng cạm bẫy đã biết trong repo (đọc trước khi code)

| # | Vấn đề | Chỗ | Ai xử lý |
|---|---|---|---|
| 1 | `data/` **rỗng** dù README:30 và codelab:173 nói "có sẵn 11 file mẫu" | `data/landing/*` | Đức Anh — tự thu thập, dùng Plan B nguồn nghị định |
| 2 | `CHUNK_SIZE=500/50` trong code vs **800/100** trong mọi tài liệu | `task4:44-45` | Đức Anh — đổi thành 800/100 |
| 3 | `SCORE_THRESHOLD=0.3` trong code vs **0.48** trong tài liệu | `task9:41` | Tuấn Anh — calibrate bằng đo thật, ghi lý do |
| 4 | `rerank()` raise NotImplementedError ở **cả 3 nhánh**, nhưng test gọi nó | `task7:175-184` | Kỳ Anh — nhánh `rrf` nhận list phẳng |
| 5 | `chroma_db/` **không nằm trong `.gitignore`** → mìn conflict binary | `.gitignore` | ✅ Tuấn Anh đã xử lý ở setup commit |
| 6 | `src/supervisor.py` được nhắc trong README:57 + mô tả Role 1 nhưng **không tồn tại** | — | Tuấn Anh — tuỳ chọn CP5 |
| 7 | `golden_dataset.json` chỉ có **3/15** câu, nội dung Shopee | `group_project/evaluation/` | Trường — viết lại theo data thật |
| 8 | Task 9/10 dùng **relative import** → bắt buộc `python -m src.taskX`, không được `python src/taskX.py` | `task9:28-31`, `task10:21` | Cả nhóm — luôn chạy từ root repo bằng `-m` |
| 9 | Test **skip** khi gặp `NotImplementedError` → chưa làm gì vẫn "không đỏ". Cần `35 passed`, **`skipped` = mất điểm** | `tests/` | Trường (QA) — báo cả skip lẫn fail |
| 10 | `UnicodeEncodeError` khi print tiếng Việt trên Windows | terminal | Cả nhóm — `$env:PYTHONIOENCODING="utf-8"` |
| 11 | Đổi corpus mà không xoá `chroma_db/` → chunk cũ lẫn mới, retrieval trả rác | `chroma_db/` | Đức Anh — `Remove-Item -Recurse -Force chroma_db` trước khi reindex |

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

**Smoke test end-to-end (Tuấn Anh, CP4):**
```powershell
python -m src.task9_retrieval_pipeline      # 4 query, query cuối "xyzabc123nonsense" phải rơi vào [pageindex]
python -m src.task10_generation             # 3 câu, output phải có citation dạng [Nguồn, Năm]
```

**Chatbot (Hoàng, CP5):**
```powershell
streamlit run app.py
```
Kiểm: hỏi 1 câu trong domain → có citation + expander nguồn hiện score; hỏi follow-up ngắn → vẫn hiểu ngữ cảnh; hỏi câu ngoài domain → trả "Tôi không thể xác minh thông tin này từ nguồn hiện có".

**Evaluation (Trường, CP5):**
```powershell
python -m group_project.evaluation.eval_pipeline
```
Kiểm: `results.md` có đủ 4 metric × 2 config + Δ, worst 3, 3 đề xuất.

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

Mỗi người dán **đúng khối của mình**, ngay sau khi mở Claude Code tại thư mục repo.

**Tuấn Anh (Role 1):**
> Đọc `CLAUDE.md` ở root repo trước khi làm bất cứ gì. Tôi là **Tuấn Anh — Team Leader & RAG Architect**. Tôi CHỈ được sửa: `src/task9_retrieval_pipeline.py`, `README.md`, `requirements.txt`, `.gitignore`, `.gitattributes`, `CLAUDE.md`, `TEAM_PLAN.md`, `.env.example`, `src/supervisor.py`. Tuyệt đối không sửa/tạo/xoá file nào khác — kể cả khi bạn thấy nó có bug; hãy báo tôi thay vì tự sửa. Không chạy `git add .`, `git add -A`, `git push --force`, `git reset --hard`. Không sửa `tests/`. Nhiệm vụ: implement `retrieve()` trong Task 9 — so `score_threshold` với **điểm cosine gốc của `dense_results[0]`**, KHÔNG phải điểm RRF đã fuse (RRF luôn ≈0.016 nên fallback sẽ không bao giờ chạy). Đọc kỹ docstring cảnh báo ở đầu file. Chạy `python -m src.task9_retrieval_pipeline` để test (relative import — bắt buộc dùng `-m` từ root).

**Đức Anh (Role 2):**
> Đọc `CLAUDE.md` ở root repo trước. Tôi là **Đức Anh — Data & Dense Search Dev**. Tôi CHỈ được sửa: `data/**`, `src/task1_collect_legal_docs.py`, `src/task2_crawl_news.py`, `src/task3_convert_markdown.py`, `src/task4_chunking_indexing.py`, `src/task5_semantic_search.py`. Không sửa file nào khác, không sửa `tests/`, không sửa `requirements.txt` (báo Tuấn Anh). Không `git add .` (sẽ nuốt `chroma_db/` 200MB). Nhiệm vụ: Task 1–5. Lưu ý: help.shopee.vn là SPA nên crawl ra rỗng — dùng nguồn nghị định TMĐT (NĐ 52/2013, NĐ 85/2021, Luật BVQLNTD 2023) dạng PDF. Đổi `CHUNK_SIZE=800`, `CHUNK_OVERLAP=100`. Gắn `customer_role` (`buyer`/`seller`/`both`) vào metadata mỗi chunk. Thêm `get_embedding_model()` và `get_collection()` ở module level để Task 5 dùng lại. File JSON news bắt buộc có key `url`.

**Kỳ Anh (Role 3):**
> Đọc `CLAUDE.md` ở root repo trước. Tôi là **Kỳ Anh — Sparse Search & Reranking Dev**. Tôi CHỈ được sửa: `src/task6_lexical_search.py`, `src/task7_reranking.py`, `src/task8_pageindex_vectorless.py`. Không sửa file nào khác, không sửa `tests/`, không `git add .`. Nhiệm vụ: (1) Task 6 BM25 — load `CORPUS` **lazy** trong hàm, không ở module level, nếu không `import src.task9` sẽ nổ khi chưa có data. (2) Task 7 RRF — hàm `rerank()` hiện raise NotImplementedError ở cả 3 nhánh nhưng test gọi nó với 1 list phẳng, hãy sửa nhánh `"rrf"` thành `return rerank_rrf([candidates], top_k=top_k)`. (3) Task 8 — nhóm chưa có PAGEINDEX_API_KEY, hãy implement local vectorless retriever: cắt `data/standardized/**/*.md` theo heading markdown thành cây mục lục, chấm điểm theo độ trùng từ khoá (tiêu đề nhân hệ số 2), trả nguyên section không chunk, giữ `'source': 'pageindex'`, và trả `[]` thay vì raise khi không có data.

**Hoàng (Role 4):**
> Đọc `CLAUDE.md` ở root repo trước. Tôi là **Hoàng — Frontend & Chatbot Dev**. Tôi CHỈ được sửa: `src/task10_generation.py` và `app.py`. Không sửa file nào khác, không sửa `tests/`, không `git add .`. Nhiệm vụ: (1) `reorder_for_llm` = `chunks[::2] + chunks[1::2][::-1]`. (2) `format_context` BẮT BUỘC chèn `metadata['source']` vào string output (test assert tên file có trong context). (3) `generate_with_citation` gọi OpenRouter qua OpenAI SDK với `base_url="https://openrouter.ai/api/v1"`, model `:free`, bọc try/except để hết quota thì trả message lỗi chứ không raise. (4) `app.py` đã hoàn thiện ~90% — xoá khối TODO chết dòng 113–118, thêm conversation memory (4 lượt gần nhất) và UI hiển thị score/badge nguồn/highlight từ khoá. Chạy `python -m src.task10_generation` để test.

**Trường (Role 5):**
> Đọc `CLAUDE.md` ở root repo trước. Tôi là **Trường — Evaluation & QA Engineer**. Tôi CHỈ được sửa file trong `group_project/**`. Không sửa `src/`, không sửa `app.py`, TUYỆT ĐỐI không sửa `tests/` (đó là file chấm điểm — sửa là gian lận). Không `git add .`. Nhiệm vụ: (1) Viết lại `golden_dataset.json` 15–20 câu bám sát nội dung thật trong `data/standardized/` (60% trả lời trực tiếp, 25% cần tổng hợp 2 nguồn, 15% ngoài domain để test fallback). (2) Implement `evaluate_with_ragas`, `compare_configs` (A: `retrieve(use_reranking=True)` vs B: dense-only `semantic_search`), `export_results` — RAGAS judge trỏ về OpenRouter qua `ChatOpenAI(base_url=...)`. (3) Điền `results.md` đủ 4 phần. Lưu ý quota OpenRouter free 50 req/ngày cho CẢ tài khoản: chạy 5 câu trước để lấy số, chỉ mở rộng 15 câu nếu còn quota. Ngoài ra tôi là QA: sau mỗi lần `main` cập nhật, chạy `python -m pytest tests/test_individual.py -v` và báo bảng *test fail/skip → task → chủ file*.
