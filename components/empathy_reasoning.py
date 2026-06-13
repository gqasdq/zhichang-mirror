"""Chain-of-Empathy 共情推理链 UI 展示。"""

from __future__ import annotations

import html
from typing import Any

import streamlit as st

from components.ai_surface import inject_ai_surface_styles


_STEP_FIELDS = (
    ("emotion_analysis", "① 情绪识别"),
    ("reflection", "② 反思"),
    ("support_type", "③ 支持类型"),
    ("strategy", "④ 回应策略"),
    ("self_check", "⑤ 自检"),
)


def render_empathy_reasoning(reasoning_chain: dict[str, Any] | None) -> None:
    """展示小镜的思考过程（Chain-of-Empathy）。"""
    if not reasoning_chain or not isinstance(reasoning_chain, dict):
        return

    steps: list[str] = []
    for idx, (key, label) in enumerate(_STEP_FIELDS, start=1):
        text = str(reasoning_chain.get(key, "")).strip()
        if not text:
            continue
        delay = (idx - 1) * 0.08
        steps.append(
            f"""
<div class="ai-step-row" style="animation-delay:{delay:.2f}s;">
  <div class="ai-step-index">{idx}</div>
  <div>
    <div class="ai-step-label">{html.escape(label)}</div>
    <div class="ai-step-text">{html.escape(text)}</div>
  </div>
</div>"""
        )

    if not steps:
        return

    inject_ai_surface_styles()
    st.markdown(
        f"""
<div class="ai-surface mirror-fade-in">
  <div class="ai-surface-head">
    <span>小镜的思考过程</span>
    <span class="ai-surface-badge">Chain-of-Empathy</span>
  </div>
  {"".join(steps)}
</div>
""",
        unsafe_allow_html=True,
    )


def render_empathy_reasoning_expander(reasoning_chain: dict[str, Any] | None) -> None:
    """可折叠版思考过程展示。"""
    if not reasoning_chain or not isinstance(reasoning_chain, dict):
        return
    if not any(str(reasoning_chain.get(k, "")).strip() for k, _ in _STEP_FIELDS):
        return
    with st.expander("查看小镜的思考过程（Chain-of-Empathy）", expanded=False):
        render_empathy_reasoning(reasoning_chain)
