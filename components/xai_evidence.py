"""XAI 可解释性证据展示组件。"""

from __future__ import annotations

import html
from typing import Any

import streamlit as st

from components.ai_surface import inject_ai_surface_styles


def render_xai_evidence_section(
    title: str,
    evidence: list[dict[str, Any]],
    *,
    empty_hint: str = "",
) -> None:
    """渲染带原文高亮的 XAI 证据列表。"""
    if not evidence:
        if empty_hint:
            st.caption(empty_hint)
        return

    inject_ai_surface_styles()
    items_html: list[str] = []
    for idx, item in enumerate(evidence):
        if not isinstance(item, dict):
            continue
        original = html.escape(str(item.get("original_text", item.get("content", ""))).strip())
        if not original:
            continue
        issue = html.escape(str(item.get("issue", item.get("reason", item.get("status", "")))).strip())
        suggestion = html.escape(str(item.get("suggestion", "")).strip())
        dim = html.escape(str(item.get("dimension", "")).strip())
        dim_badge = f'<span class="ai-surface-badge">{dim}</span> ' if dim else ""
        issue_line = f'<div class="ai-step-label">问题：{issue}</div>' if issue else ""
        suggestion_line = (
            f'<div class="ai-step-text">建议：{suggestion}</div>' if suggestion else ""
        )
        delay = idx * 0.06
        items_html.append(
            f"""
<div class="ai-step-row" style="animation-delay:{delay:.2f}s;">
  <div class="ai-step-index">{idx + 1}</div>
  <div>
    {dim_badge}<span class="ai-highlight">「{original}」</span>
    {issue_line}
    {suggestion_line}
  </div>
</div>"""
        )

    if not items_html:
        return

    safe_title = html.escape(title)
    st.markdown(
        f"""
<div class="ai-surface mirror-fade-in">
  <div class="ai-surface-head">
    <span>{safe_title}</span>
    <span class="ai-surface-badge">XAI 可解释评分</span>
  </div>
  {"".join(items_html)}
</div>
""",
        unsafe_allow_html=True,
    )
