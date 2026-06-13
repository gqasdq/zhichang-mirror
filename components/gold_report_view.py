"""金子探测器 · 报告正文与优势区渲染。"""

from __future__ import annotations

import html
import re

import markdown
import streamlit as st


def _strip_leading_meta(text: str) -> str:
    """去掉报告开头的寒暄与分隔线。"""
    lines = text.splitlines()
    start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped == "---":
            start = i + 1
            continue
        if "小苏" in stripped and ("开始" in stripped or "仔细看" in stripped):
            start = i + 1
            continue
        break
    cleaned = "\n".join(lines[start:]).strip()
    return cleaned or text.strip()


def format_report_html(text: str) -> str:
    """将 Markdown 报告转为带样式的 HTML。"""
    body = _strip_leading_meta(text or "")
    if not body:
        return '<div class="gold-report-prose"><p class="gold-prose-empty">暂无报告内容</p></div>'

    rendered = markdown.markdown(
        body,
        extensions=["nl2br", "sane_lists"],
    )

    # 给标题加 class，便于样式控制
    rendered = re.sub(r"<h2>", '<h2 class="gold-prose-h2">', rendered)
    rendered = re.sub(r"<h3>", '<h3 class="gold-prose-h3">', rendered)
    rendered = re.sub(r"<hr\s*/?>", '<hr class="gold-prose-divider"/>', rendered)
    rendered = re.sub(r"<p>", '<p class="gold-prose-p">', rendered)
    rendered = re.sub(r"<li>", '<li class="gold-prose-li">', rendered)
    rendered = re.sub(r"<ol>", '<ol class="gold-prose-ol">', rendered)
    rendered = re.sub(r"<ul>", '<ul class="gold-prose-ul">', rendered)

    return f'<div class="gold-report-prose">{rendered}</div>'


def render_report_body(text: str) -> None:
    """渲染排版后的报告正文。"""
    st.markdown(format_report_html(text), unsafe_allow_html=True)


def render_strengths(strengths: list[str]) -> None:
    """渲染核心优势区块。"""
    if not strengths:
        return

    items_html = ""
    for item in strengths:
        safe = html.escape(item.strip(), quote=True)
        if "：" in safe:
            name, desc = safe.split("：", 1)
            inner = f'<span class="gold-strength-name">{name}</span><span class="gold-strength-desc">{desc}</span>'
        else:
            inner = f'<span class="gold-strength-desc">{safe}</span>'
        items_html += f'<li class="gold-strength-item">{inner}</li>'

    st.markdown(
        f"""
<div class="gold-strengths-block">
  <div class="gold-section-label">核心优势</div>
  <ul class="gold-strength-list">{items_html}</ul>
</div>
""",
        unsafe_allow_html=True,
    )


def render_report_header() -> None:
    """报告区顶部标题。"""
    st.markdown(
        """
<div class="gold-report-header">
  <div class="gold-report-eyebrow">翻案报告</div>
  <div class="gold-report-title">小苏的诊断与建议</div>
  <div class="gold-report-subtitle">基于你的简历，帮你看见被低估的价值</div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_section_divider(label: str = "") -> None:
    """区块分隔线。"""
    safe_label = html.escape(label, quote=True) if label else ""
    label_html = f'<span class="gold-section-divider-label">{safe_label}</span>' if label else ""
    st.markdown(
        f'<div class="gold-section-divider">{label_html}</div>',
        unsafe_allow_html=True,
    )
