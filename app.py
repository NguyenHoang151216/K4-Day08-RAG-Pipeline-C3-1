"""Streamlit UI cho Trợ lý Pháp lý Khởi nghiệp & Thương mại điện tử.

Chạy từ thư mục gốc:
    streamlit run app.py
"""

import re
import sys
import time
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

st.set_page_config(
    page_title="Trợ lý Pháp lý Khởi nghiệp & TMĐT",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)


SUGGESTED_QUESTIONS = [
    "Bán hàng online trên TikTok Shop đạt doanh thu bao nhiêu thì phải nộp thuế TNCN và GTGT?",
    "Hồ sơ và thủ tục đăng ký Hộ kinh doanh cá thể gồm những giấy tờ gì?",
    "Nên chọn Hộ kinh doanh hay Công ty TNHH khi bán hàng trên sàn TMĐT?",
    "Thủ tục thành lập Công ty TNHH một thành viên gồm những bước nào?",
    "Người bán trên sàn thương mại điện tử có những nghĩa vụ pháp lý nào?",
]

DISCLAIMER = (
    "Nội dung do hệ thống cung cấp chỉ mang tính tham khảo, "
    "không thay thế ý kiến tư vấn pháp lý chính thức."
)


def build_contextual_query(query: str, messages: list[dict]) -> str:
    """Bổ sung ngữ cảnh cho câu follow-up ngắn từ tối đa 4 lượt gần nhất."""
    query = query.strip()
    if len(query.split()) > 15 or not messages:
        return query

    recent_user_questions = [
        item.get("content", "").strip()
        for item in messages[-8:]
        if item.get("role") == "user" and item.get("content")
    ][-4:]
    if not recent_user_questions:
        return query

    history = "\n".join(f"- {question}" for question in recent_user_questions)
    return (
        "Ngữ cảnh các câu hỏi trước:\n"
        f"{history}\n"
        f"Câu hỏi tiếp nối: {query}"
    )


def _safe_score(value) -> float:
    try:
        return max(0.0, min(float(value), 1.0))
    except (TypeError, ValueError):
        return 0.0


def _preview_content(content: str, query: str, limit: int = 500) -> str:
    """Tạo preview ngắn và nhấn mạnh từ khóa an toàn cho Markdown."""
    preview = str(content or "").strip()
    if len(preview) > limit:
        preview = preview[:limit].rsplit(" ", 1)[0] + "…"

    keywords = {
        word.lower()
        for word in re.findall(r"[\wÀ-ỹ]+", query)
        if len(word) >= 5
    }
    for keyword in sorted(keywords, key=len, reverse=True)[:8]:
        preview = re.sub(
            rf"(?i)(?<!\w)({re.escape(keyword)})(?!\w)",
            r"**\1**",
            preview,
        )
    return preview


def render_sources(sources: list[dict], query: str) -> None:
    """Hiển thị metadata, điểm và trích đoạn của các nguồn RAG."""
    if not sources:
        return

    with st.expander(f"📚 Nguồn tham khảo ({len(sources)} trích đoạn)"):
        for index, source in enumerate(sources, 1):
            metadata = source.get("metadata") or {}
            source_name = metadata.get("source", "Không rõ nguồn")
            doc_title = metadata.get("doc_title") or source_name
            legal_ref = metadata.get("legal_ref")
            doc_type = metadata.get("type", "unknown")
            retrieval_type = source.get("source", "hybrid")
            score = _safe_score(source.get("score", 0))

            badge = "🟦 HYBRID" if retrieval_type == "hybrid" else "🟧 PAGEINDEX"
            st.markdown(f"**[{index}] {doc_title}** &nbsp; `{badge}` &nbsp; `{doc_type}`")
            details = [f"Tệp: `{source_name}`", f"Điểm: `{score:.4f}`"]
            if legal_ref:
                details.insert(0, f"**⚖️ {legal_ref}**")
            st.markdown(" · ".join(details))
            st.progress(score)
            st.markdown(_preview_content(source.get("content", ""), query))
            if index < len(sources):
                st.divider()


if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_query" not in st.session_state:
    st.session_state.pending_query = None


with st.sidebar:
    st.title("⚖️ Trợ lý Pháp lý")
    st.caption("Dành cho khởi nghiệp, hộ kinh doanh, doanh nghiệp và người bán hàng trên sàn TMĐT.")

    st.divider()
    st.subheader("💡 Câu hỏi gợi ý")
    for index, suggestion in enumerate(SUGGESTED_QUESTIONS):
        if st.button(suggestion, use_container_width=True, key=f"suggestion_{index}"):
            st.session_state.pending_query = suggestion

    st.divider()
    st.subheader("⚙️ Thiết lập")
    top_k = st.slider("Số trích đoạn tra cứu", 3, 10, 5)
    if st.button("🗑️ Xóa lịch sử trò chuyện", use_container_width=True):
        st.session_state.messages = []
        st.session_state.pending_query = None
        st.rerun()

    st.divider()
    st.caption("**Kiến trúc:** Semantic + BM25 → Reranking → PageIndex fallback → Groq GPT-OSS 120B")
    st.warning(DISCLAIMER)


st.title("⚖️ Trợ Lý Pháp Lý Khởi Nghiệp & Thương Mại Điện Tử")
st.caption("Tra cứu quy định pháp lý có dẫn nguồn cho hoạt động khởi nghiệp và kinh doanh trực tuyến.")
st.info(DISCLAIMER, icon="ℹ️")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant":
            elapsed = message.get("elapsed_seconds")
            retrieval_source = message.get("retrieval_source")
            if elapsed is not None:
                st.caption(f"⏱️ {elapsed:.2f} giây · Pipeline: {retrieval_source or 'none'}")
            render_sources(message.get("sources", []), message.get("query", ""))


user_input = st.chat_input("Nhập câu hỏi về thuế, hộ kinh doanh, doanh nghiệp hoặc TMĐT…")
query = user_input or st.session_state.pending_query

if query:
    st.session_state.pending_query = None
    contextual_query = build_contextual_query(query, st.session_state.messages)
    st.session_state.messages.append({"role": "user", "content": query})

    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        started_at = time.perf_counter()
        with st.spinner("Đang tra cứu văn bản pháp luật và tổng hợp câu trả lời…"):
            try:
                from src.task10_generation import generate_with_citation

                response = generate_with_citation(contextual_query, top_k=top_k)
                answer = response.get("answer") or "Chưa thể tạo câu trả lời."
                sources = response.get("sources") or []
                retrieval_source = response.get("retrieval_source", "none")
            except Exception as exc:
                answer = f"❌ **Không thể chạy RAG pipeline:** {exc}"
                sources = []
                retrieval_source = "error"

        elapsed_seconds = time.perf_counter() - started_at
        st.markdown(answer)
        st.caption(f"⏱️ {elapsed_seconds:.2f} giây · Pipeline: {retrieval_source}")
        render_sources(sources, query)

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer,
            "sources": sources,
            "retrieval_source": retrieval_source,
            "elapsed_seconds": elapsed_seconds,
            "query": query,
        }
    )
