import streamlit as st
from textwrap import dedent

from core.session_manager import SessionManager


PAGE_ROUTE_MAP = {
    "home": "🏠 首页",
    "emotion": "💙 情绪急救站",
    "gold": "✨ 金子探测器",
    "workshop": "🔨 金子工坊",
    "parallel": "🌌 平行宇宙",
    "gene": "🧬 职业基因",
    "empathy": "🔗 人才共情链",
    "history": "📜 历史记录",
}


def _get_query_value(key: str):
    if hasattr(st, "query_params"):
        value = st.query_params.get(key)
    else:
        value = st.experimental_get_query_params().get(key)
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _clear_query_params() -> None:
    if hasattr(st, "query_params"):
        st.query_params.clear()
    else:
        st.experimental_set_query_params()


def _consume_nav_query() -> None:
    nav = _get_query_value("nav")
    if nav in PAGE_ROUTE_MAP:
        target_page = PAGE_ROUTE_MAP[nav]
        current_page = st.session_state.get("current_page")
        if current_page != target_page:
            st.session_state.current_page = target_page


def navigate_to_page(route: str) -> None:
    """程序化跳转页面，同步 URL query，避免 ?nav=gold 等旧参数覆盖目标页。"""
    if route not in PAGE_ROUTE_MAP:
        return
    st.session_state.current_page = PAGE_ROUTE_MAP[route]
    if hasattr(st, "query_params"):
        st.query_params["nav"] = route
    else:
        st.experimental_set_query_params(nav=route)


def render_sidebar() -> None:
    from ui.styles import inject_styles

    inject_styles()
    _consume_nav_query()

    with st.sidebar:
        current = st.session_state.get("current_page", "🏠 首页")
        nav_items = [
            ("home", "首页"),
            ("emotion", "情绪急救站"),
            ("gold", "金子探测器"),
            ("workshop", "金子工坊"),
            ("parallel", "平行宇宙"),
            ("gene", "职业基因"),
            ("empathy", "人才共情链"),
            ("history", "历史记录"),
        ]

        nav_html = []
        for route, label in nav_items:
            active = "active" if PAGE_ROUTE_MAP[route] == current else ""
            nav_html.append(
                f'<a class="sidebar-nav-item {active}" href="?nav={route}" target="_self">{label}</a>'
            )

        st.markdown(
            dedent(
                f"""
            <div class="sidebar-shell">
                <div class="sidebar-top">
                    <div class="sidebar-brand-title">职场镜子</div>
                    <div class="sidebar-brand-subtitle">Career Mirror</div>
                </div>
                <div class="sidebar-divider"></div>
                <div class="sidebar-nav-list">
                    {''.join(nav_html)}
                </div>
            </div>
            """
            ),
            unsafe_allow_html=True,
        )

        st.caption("DeepSeek V3 · 智谱GLM-4-Flash")

        if st.button("🗑️ 清除我的所有数据", use_container_width=True):
            SessionManager.clear_session()
            st.success("✅ 数据已清除！")
            st.rerun()

        st.markdown("---")
        st.markdown(
            "🔒 **隐私承诺**\n"
            "· 数据不落地，关闭即清除\n"
            "· AI分析前自动脱敏\n"
            "· 随时一键清除数据\n"
            "· 无需注册，用完即走"
        )
