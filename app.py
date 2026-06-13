"""职场镜子 - 主应用入口。"""

# 多用户隔离说明：每个用户通过 SessionManager.get_user_id() 获取匿名 ID
# 数据存储在 data/sessions/{uid}/ 和 data/faiss/{uid}/ 下
# Streamlit Cloud 多进程环境下 session_state 天然隔离，无需额外处理

import logging
import traceback
import json
from datetime import datetime

import streamlit as st

from core.analytics import export_analytics, init_analytics
from core.session_manager import SessionManager

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


def _handle_uncaught_exception(exc_type, exc_value, exc_tb):
    """全局异常兜底，防止Python traceback直接暴露给用户。"""
    logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_tb))


# 不替换sys.excepthook，Streamlit有自己的异常处理
# 但在每个页面调用入口加 try/except

from ui.sidebar import render_sidebar


st.set_page_config(
    page_title="职场镜子 | Career Mirror",
    page_icon="🪞",
    layout="wide",
    initial_sidebar_state="expanded",
)


def init_session_state() -> None:
    defaults = {
        "current_page": "🏠 首页",
        "chat_history": [],
        "emotion_session": None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def _normalize_page_name(page: str) -> str:
    normalized = (page or "").strip()
    if " " in normalized:
        normalized = normalized.split(" ", 1)[1]
    return normalized


def _render_current_page(page_name: str) -> None:
    """按需加载页面模块，避免启动时导入全部重依赖（FAISS、Plotly 等）。"""
    if page_name == "首页":
        from ui.pages.home import render as home_page

        home_page()
    elif page_name == "情绪急救站":
        from ui.pages.emotion import render as emotion_page

        emotion_page()
    elif page_name == "金子探测器":
        from ui.pages.gold_detector import render as gold_page

        gold_page()
    elif page_name == "金子工坊":
        from ui.pages.gold_workshop import render as workshop_page

        workshop_page()
    elif page_name == "平行宇宙":
        from ui.pages.parallel import render as parallel_page

        parallel_page()
    elif page_name == "职业基因":
        from ui.pages.gene import render as gene_page

        gene_page()
    elif page_name == "人才共情链":
        from ui.pages.empathy import render as empathy_page

        empathy_page()
    elif page_name == "历史记录":
        from ui.pages.history import render as history_page

        history_page()
    else:
        from ui.pages.home import render as home_page

        home_page()


init_session_state()
SessionManager.auto_cleanup_on_start()
try:
    init_analytics()
except Exception:
    pass
render_sidebar()

with st.sidebar:
    if st.button("📊 导出体验数据", use_container_width=True):
        st.session_state.show_analytics_export = True
    if st.session_state.get("show_analytics_export"):
        data = export_analytics(include_persisted=True)
        st.caption(
            f"累计 {data.get('total_events', 0)} 条（持久化 {data.get('persisted_events', 0)} + "
            f"本会话 {data.get('session_events', 0)}）"
        )
        st.download_button(
            "下载数据",
            data=json.dumps(data, ensure_ascii=False, indent=2),
            file_name=f"zhijing_analytics_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
            mime="application/json",
            use_container_width=True,
        )

page = st.session_state.get("current_page", "🏠 首页")
page_name = _normalize_page_name(page)

try:
    _render_current_page(page_name)
except Exception as e:
    from ui.error_handler import handle_api_error

    handle_api_error(e, context="page_render")
