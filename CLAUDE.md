# QUY TẮC BẮT BUỘC CHO MỌI AGENT TRONG REPO NÀY

Repo này có **5 người làm song song, mỗi người một AI agent riêng**. Toàn bộ quy tắc dưới đây tồn tại để 5 nhánh không bao giờ đụng nhau. Đọc hết trước khi sửa bất cứ file nào.

---

## 1. Chủ quyền file — TUYỆT ĐỐI không sửa file ngoài vùng của mình

| Vùng file | Chủ sở hữu | Role |
|---|---|---|
| `data/**`, `src/task1_*.py`, `src/task2_*.py`, `src/task3_*.py`, `src/task4_*.py`, `src/task5_*.py` | **Đức Anh** | Data & Dense Search |
| `src/task6_*.py`, `src/task7_*.py`, `src/task8_*.py` | **Kỳ Anh** | Sparse Search & Reranking |
| `src/task9_*.py`, `src/supervisor.py`, `README.md`, `requirements.txt`, `.gitignore`, `.gitattributes`, `CLAUDE.md`, `.env.example` | **Tuấn Anh** | Team Leader & RAG Architect |
| `src/task10_*.py`, `app.py` | **Hoàng** | Frontend & Chatbot |
| `group_project/**` | **Trường** | Evaluation & QA |
| `tests/**` | **KHÔNG AI** — file chấm điểm, sửa là gian lận | — |
| `LAB_GUIDE.md`, `day8-lab-rag-pipeline.md`, `checkpoint_timer.html` | **KHÔNG AI** — tài liệu đề bài | — |

**Nếu cần thay đổi file không thuộc vùng của mình: DỪNG LẠI**, báo người dùng nhắn cho chủ file. Không tự sửa. Không tạo file mới trùng chức năng để "lách". Không copy code sang file của mình rồi sửa bản copy.

Thấy bug trong file người khác? **Báo, đừng sửa.** Một dòng sửa "cho tiện" = một conflict giữa buổi lab.

---

## 2. Git — các lệnh BỊ CẤM

| Cấm | Lý do |
|---|---|
| `git add .` , `git add -A` , `git commit -am` | Sẽ nuốt `chroma_db/` (hàng trăm MB), `.env` (lộ API key), file rác của agent. **Luôn liệt kê đường dẫn cụ thể.** |
| `git push --force` , `git push -f` | Xoá công việc người khác. Trên branch riêng nếu buộc phải dùng thì chỉ `--force-with-lease`. |
| `git reset --hard` , `git checkout main -- <file>` | Mất code chưa commit, ghi đè file người khác. |
| `git merge` / `git rebase` hộ người khác, tự merge PR vào `main` | Chỉ **Tuấn Anh** merge. |
| Commit `.env`, `chroma_db/`, `.venv/`, `__pycache__/` | Đã có trong `.gitignore` — đừng force-add. |
| Sửa `requirements.txt` | 5 người cùng sửa = conflict 5 chiều. Thiếu package → báo Tuấn Anh. |
| Sửa bất cứ gì trong `tests/` | Gian lận, mất điểm toàn bài. |

**Không tự chạy `git commit` / `git push` nếu người dùng chưa yêu cầu.**

---

## 3. Vòng lặp làm việc chuẩn — lặp lại mỗi checkpoint

```powershell
git checkout main
git pull --rebase origin main
git checkout -b feat/<tên>-cp<N>-<mô-tả>      # vd: feat/kyanh-cp2-bm25

# ... code ...

git add src/task6_lexical_search.py            # LIỆT KÊ FILE CỤ THỂ
git commit -m "feat(task6): BM25 lexical search"

git fetch origin
git rebase origin/main                         # đồng bộ trước khi push
git push -u origin feat/kyanh-cp2-bm25
```

Quy ước tên branch: **`feat/tên-cpN-mô-tả`** — dấu gạch ngang, không dùng `feat/tên/cpN` (sẽ gây lỗi `cannot lock ref`).
Branch sống ngắn: 1 branch = 1 checkpoint, không giữ qua 2 checkpoint.

---

## 4. Contract giữa các module — KHÔNG được đổi signature

Task 9 gọi Task 5/6/7/8; Task 10 gọi Task 9; `app.py` và eval gọi Task 10. Đổi một signature là gãy dây chuyền của 4 người khác.

```python
semantic_search(query: str, top_k: int = 10) -> list[dict]
    # [{'content': str, 'score': float (cosine 0..1), 'metadata': dict}], sorted desc

lexical_search(query: str, top_k: int = 10) -> list[dict]
    # [{'content': str, 'score': float (BM25), 'metadata': dict}], sorted desc

rerank_rrf(ranked_lists: list[list[dict]], top_k: int = 5, k: int = 60) -> list[dict]
rerank(query: str, candidates: list[dict], top_k: int = 5, method: str = "rrf") -> list[dict]

pageindex_search(query: str, top_k: int = 5) -> list[dict]
    # [{'content','score','metadata','source': 'pageindex'}]; trả [] khi không có data, KHÔNG raise

retrieve(query: str, top_k: int = 5, score_threshold: float = ..., use_reranking: bool = True) -> list[dict]
    # [{'content','score','metadata','source': 'hybrid' | 'pageindex'}]

generate_with_citation(query: str, top_k: int = 5) -> dict
    # {'answer': str, 'sources': list[dict], 'retrieval_source': str}
```

Muốn đổi → báo cả nhóm trước, Tuấn Anh chốt.

---

## 5. Lưu ý kỹ thuật của repo này

- **Chạy module bằng `-m` từ thư mục gốc**: `src/task9`, `src/task10` dùng relative import (`from .task5_... import`). `python src/task9_retrieval_pipeline.py` sẽ lỗi `ImportError`. Đúng: `python -m src.task9_retrieval_pipeline`.
- **Tiếng Việt trên Windows console**: đặt `$env:PYTHONIOENCODING="utf-8"` trước khi chạy, nếu không sẽ `UnicodeEncodeError`.
- **Load dữ liệu phải lazy**: đừng đọc `data/standardized/` hay mở ChromaDB ở module level — sẽ làm `import` gãy khi máy người khác chưa có data. Bọc trong hàm, cache sau lần gọi đầu.
- **Đổi corpus thì phải xoá index cũ**: `Remove-Item -Recurse -Force chroma_db` rồi chạy lại Task 4, nếu không chunk cũ và mới lẫn lộn.
- **Bẫy fallback ở Task 9**: điểm RRF sau khi fuse luôn ≈ `1/(60+1) ≈ 0.016` bất kể nội dung có liên quan hay không. So `score_threshold` với **điểm cosine gốc `dense_results[0]["score"]`**, KHÔNG phải điểm RRF.
- **Test skip ≠ test pass**: `tests/` bắt `NotImplementedError` và chuyển thành `skipTest`. Mục tiêu là **35 passed, 0 skipped** — `skipped` nghĩa là chưa làm và không được điểm.
- **Không hardcode API key**: đọc từ `.env` qua `os.getenv()`. `.env` không bao giờ vào git.
