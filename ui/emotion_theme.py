"""情绪界面呼吸 — 各页面统一注入入口。"""

from __future__ import annotations

import html

import streamlit.components.v1 as components

from utils.emotion_adapter import EmotionAdapter, resolve_emotion_source


_EMOTION_BADGE = {
    "anxious": ("🫂", "舒缓模式", "界面已放慢 · 信息已简化"),
    "frustrated": ("🌱", "鼓励模式", "先看亮点 · 再慢慢改"),
    "confused": ("🧭", "引导模式", "跟着步骤 · 一步步来"),
}


def inject_emotion_bridge(adapter: EmotionAdapter) -> None:
    """在 .stApp 上设置 data-emotion（iframe 内执行，不占可见空间）。"""
    key = adapter.get_emotion_key()
    theme = adapter.get_theme()
    primary = html.escape(theme["primary_color"])
    accent = html.escape(theme["accent_color"])

    if key == "calm":
        body = """
            app.removeAttribute('data-emotion');
            app.classList.remove('emotion-active');
            root.style.removeProperty('--emotion-primary');
            root.style.removeProperty('--emotion-accent');
            root.style.removeProperty('--mirror-accent');
        """
    else:
        body = f"""
            app.setAttribute('data-emotion', '{key}');
            app.classList.add('emotion-active');
            root.style.setProperty('--emotion-primary', '{primary}');
            root.style.setProperty('--emotion-accent', '{accent}');
            root.style.setProperty('--mirror-accent', '{primary}');
        """

    components.html(
        f"""<script>
(function() {{
  try {{
    const doc = window.parent.document;
    const app = doc.querySelector('.stApp');
    const root = doc.documentElement;
    if (!app) return;
    {body}
  }} catch (e) {{}}
}})();
</script>""",
        height=0,
        scrolling=False,
    )


def render_emotion_badge(adapter: EmotionAdapter) -> None:
    """非平稳时显示情绪模式标识（让用户感知界面已切换）。"""
    key = adapter.get_emotion_key()
    if key == "calm":
        return
    badge = _EMOTION_BADGE.get(key)
    if not badge:
        return
    emoji, label, hint = badge
    theme = adapter.get_theme()
    primary = theme["primary_color"]
    accent = theme["accent_color"]
    import streamlit as st

    st.markdown(
        f"""
<div class="emotion-mode-badge emotion-mode-badge--{key}" style="
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 6px 14px;
    margin-bottom: 12px;
    border-radius: 999px;
    background: linear-gradient(135deg, {theme['card_bg']}, rgba(255,255,255,0.7));
    border: 1px solid {accent}55;
    box-shadow: 0 2px 12px {primary}22;
    animation: emotionBadgeIn 0.7s cubic-bezier(0.22, 1, 0.36, 1) both;
">
    <span style="font-size:15px;">{emoji}</span>
    <span style="font-size:12px; font-weight:650; color:#5C4B45; letter-spacing:0.02em;">{label}</span>
    <span style="font-size:11px; color:#8C8279;">· {hint}</span>
</div>
""",
        unsafe_allow_html=True,
    )


def render_score_context(adapter: EmotionAdapter) -> None:
    """温度计驱动且为平稳时，提示用户为何没有舒缓主题。"""
    _, source, score = resolve_emotion_source()
    if source != "score" or score is None:
        return
    if adapter.get_emotion_key() != "calm":
        return
    import streamlit as st

    st.markdown(
        f"""
<div style="
    display:inline-flex; align-items:center; gap:6px;
    padding:5px 12px; margin-bottom:10px;
    border-radius:999px; font-size:12px; color:#8C8279;
    background:rgba(255,255,255,0.6); border:1px solid rgba(61,56,51,0.08);
">
    ✨ 求职状态 {score} 度 · 状态不错，界面保持标准模式
</div>
""",
        unsafe_allow_html=True,
    )


def apply_emotion_breath(*, show_encouragement: bool = True, show_badge: bool = True) -> EmotionAdapter:
    """注入情绪主题 CSS、整页标记、鼓励语，返回当前 adapter。"""
    adapter = EmotionAdapter.from_session()
    adapter.inject_page_theme()
    inject_emotion_bridge(adapter)
    if show_badge and adapter.get_emotion_key() != "calm":
        render_emotion_badge(adapter)
    else:
        render_score_context(adapter)
    if show_encouragement:
        adapter.render_encouragement()
    return adapter
