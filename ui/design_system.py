"""职场镜子 · 统一 UI 设计系统（Claude 温暖编辑风 + 产品级组件）。"""

from __future__ import annotations

import html

import streamlit as st


# 设计令牌 — 与现有暖色主题一致
TOKENS = {
    "bg": "#F7F3EF",
    "bg_sidebar": "#F0EBE3",
    "surface": "rgba(255, 255, 255, 0.78)",
    "surface_muted": "rgba(255, 255, 255, 0.55)",
    "ink": "#2C2420",
    "ink_secondary": "#5C4F47",
    "muted": "#6B5B52",
    "muted_light": "#8C8279",
    "accent": "#B8908A",
    "accent_hover": "#A07A74",
    "border": "rgba(61, 56, 51, 0.08)",
    "border_accent": "rgba(184, 144, 138, 0.18)",
    "radius_sm": "8px",
    "radius_md": "12px",
    "radius_lg": "16px",
    "content_max": "1080px",
}


def render_page_header(title: str, subtitle: str = "", eyebrow: str = "") -> None:
    """各模块统一的页面标题区。"""
    eyebrow_html = (
        f'<div class="mirror-page-eyebrow">{html.escape(eyebrow)}</div>' if eyebrow else ""
    )
    subtitle_html = (
        f'<div class="mirror-page-subtitle">{html.escape(subtitle)}</div>' if subtitle else ""
    )
    st.markdown(
        f"""
<div class="mirror-page-header mirror-reveal">
  {eyebrow_html}
  <div class="mirror-page-title">{html.escape(title)}</div>
  {subtitle_html}
</div>
""",
        unsafe_allow_html=True,
    )


def render_section_title(title: str) -> None:
    """区块小标题。"""
    st.markdown(
        f'<div class="mirror-section-title mirror-reveal">{html.escape(title)}</div>',
        unsafe_allow_html=True,
    )


def render_insight_card(title: str, body: str, tag: str = "") -> None:
    """洞察/说明卡片（替代 border-left 侧条）。"""
    title_html = (
        f'<div class="mirror-insight-title">{html.escape(title)}</div>' if title.strip() else ""
    )
    body_html = (
        f'<div class="mirror-insight-body">{html.escape(body)}</div>' if body.strip() else ""
    )
    tag_html = (
        f'<div class="mirror-insight-tag">{html.escape(tag)}</div>' if tag else ""
    )
    st.markdown(
        f"""
<div class="mirror-insight-card mirror-reveal">
  {title_html}
  {body_html}
  {tag_html}
</div>
""",
        unsafe_allow_html=True,
    )
