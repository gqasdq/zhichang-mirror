"""职场镜子 - 陪你走过最难熬的求职路"""
import streamlit as st

st.set_page_config(
    page_title="职场镜子 | Career Mirror",
    page_icon="🪞",
    layout="wide",
    initial_sidebar_state="expanded",
)


def init_session_state() -> None:
    defaults = {
        "current_page": "🏠 首页",
        "user_id": None,
        "chat_history": [],
        "emotion_session": None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


init_session_state()

from ui.sidebar import render_sidebar

render_sidebar()

page = st.session_state.current_page
page_modules = {
    "🏠 首页": "ui.pages.home",
    "💙 情绪急救站": "ui.pages.emotion",
    "✨ 金子探测器": "ui.pages.gold_detector",
    "🌌 平行宇宙": "ui.pages.parallel",
    "🧬 职业基因": "ui.pages.gene",
    "🔗 人才共情链": "ui.pages.empathy_chain",
}

module_name = page_modules.get(page, "ui.pages.home")
mod = __import__(module_name, fromlist=["render"])
mod.render()
