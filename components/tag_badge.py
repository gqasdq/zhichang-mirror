"""关键词与 STAR 标签组件。"""

from __future__ import annotations

import html
from typing import Any

import streamlit as st


def _escape(text: str) -> str:
    return html.escape(text, quote=True)


def render_tags(
    matched: list[str],
    missing: list[str],
    star_pending: list[dict[str, Any]],
) -> None:
    """渲染关键词标签组。"""
    st.markdown(
        """
<style>
.jd-tag-section { margin: 14px 0 6px; }
.jd-tag-section-title {
    color: #8C8279;
    font-size: 13px;
    font-weight: 600;
    margin-bottom: 8px;
}
.jd-tag-wrap {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 4px;
}
.jd-tag {
    display: inline-flex;
    align-items: center;
    padding: 5px 12px;
    border-radius: 20px;
    font-size: 13px;
    line-height: 1.4;
    border: 1px solid transparent;
}
.jd-tag-green {
    background: #E8F5E9;
    color: #2E7D32;
    border-color: rgba(46, 125, 50, 0.12);
}
.jd-tag-red {
    background: #FFEBEE;
    color: #C62828;
    border-color: rgba(198, 40, 40, 0.12);
}
.jd-tag-yellow {
    background: #FFF8E1;
    color: #F57F17;
    border-color: rgba(245, 127, 23, 0.15);
}
</style>
""",
        unsafe_allow_html=True,
    )

    if matched:
        tags_html = "".join(
            f'<span class="jd-tag jd-tag-green">✅ {_escape(tag)}</span>' for tag in matched
        )
        st.markdown(
            f'<div class="jd-tag-section"><div class="jd-tag-section-title">已匹配</div>'
            f'<div class="jd-tag-wrap">{tags_html}</div></div>',
            unsafe_allow_html=True,
        )

    if missing:
        tags_html = "".join(
            f'<span class="jd-tag jd-tag-red">❌ {_escape(tag)}</span>' for tag in missing
        )
        st.markdown(
            f'<div class="jd-tag-section"><div class="jd-tag-section-title">待补充</div>'
            f'<div class="jd-tag-wrap">{tags_html}</div></div>',
            unsafe_allow_html=True,
        )

    if star_pending:
        tags_html = ""
        for item in star_pending:
            content = _escape(str(item.get("content", "")).strip())
            suggestion = _escape(str(item.get("suggestion", "")).strip())
            label = f'⚠️ "{content}"'
            if suggestion:
                label += f" → {suggestion}"
            tags_html += f'<span class="jd-tag jd-tag-yellow">{label}</span>'

        st.markdown(
            f'<div class="jd-tag-section"><div class="jd-tag-section-title">STAR 待改写</div>'
            f'<div class="jd-tag-wrap">{tags_html}</div></div>',
            unsafe_allow_html=True,
        )


def render_quality_tags(
    star_pending: list[dict[str, Any]],
    quant_pending: list[dict[str, Any]],
    expression_pending: list[dict[str, Any]],
) -> None:
    """简历质量报告的标签组。"""
    st.markdown(
        """
<style>
.jd-tag-orange {
    background: #FFF3E0;
    color: #E65100;
    border-color: rgba(230, 81, 0, 0.15);
}
.jd-tag-blue {
    background: #E3F2FD;
    color: #1565C0;
    border-color: rgba(21, 101, 192, 0.12);
}
</style>
""",
        unsafe_allow_html=True,
    )

    if star_pending:
        tags_html = ""
        for item in star_pending:
            content = _escape(str(item.get("content", "")).strip())
            suggestion = _escape(str(item.get("suggestion", "")).strip())
            label = f'⚠️ "{content}"'
            if suggestion:
                label += f" → {suggestion}"
            tags_html += f'<span class="jd-tag jd-tag-yellow">{label}</span>'

        st.markdown(
            f'<div class="jd-tag-section"><div class="jd-tag-section-title">STAR 待改写</div>'
            f'<div class="jd-tag-wrap">{tags_html}</div></div>',
            unsafe_allow_html=True,
        )

    if quant_pending:
        tags_html = ""
        for item in quant_pending:
            content = _escape(str(item.get("content", "")).strip())
            suggestion = _escape(str(item.get("suggestion", "")).strip())
            label = f'🔶 "{content}"'
            if suggestion:
                label += f" → {suggestion}"
            tags_html += f'<span class="jd-tag jd-tag-orange">{label}</span>'

        st.markdown(
            f'<div class="jd-tag-section"><div class="jd-tag-section-title">量化待补充</div>'
            f'<div class="jd-tag-wrap">{tags_html}</div></div>',
            unsafe_allow_html=True,
        )

    if expression_pending:
        tags_html = ""
        for item in expression_pending:
            content = _escape(str(item.get("content", "")).strip())
            suggestion = _escape(str(item.get("suggestion", "")).strip())
            label = f'🔵 "{content}"'
            if suggestion:
                label += f" → {suggestion}"
            tags_html += f'<span class="jd-tag jd-tag-blue">{label}</span>'

        st.markdown(
            f'<div class="jd-tag-section"><div class="jd-tag-section-title">表达待优化</div>'
            f'<div class="jd-tag-wrap">{tags_html}</div></div>',
            unsafe_allow_html=True,
        )
