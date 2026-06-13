"""模型路由决策展示 — 成本感知 + 健康检查。"""

from __future__ import annotations

import html
from typing import Any

import streamlit as st

from components.ai_surface import inject_ai_surface_styles


def render_model_route_badge(routing: dict[str, Any] | None) -> None:
    """展示最近一次模型路由决策（供思考链 / 调试面板使用）。"""
    if not routing or not isinstance(routing, dict):
        return

    selected = str(routing.get("selected", "")).strip()
    if not selected:
        return

    inject_ai_surface_styles()
    preferred = html.escape(str(routing.get("preferred", "")))
    reason = html.escape(str(routing.get("reason", "")))
    cost_tier = html.escape(str(routing.get("cost_tier", "")))
    healthy = routing.get("healthy_models") or []

    healthy_text = "、".join(html.escape(str(m)) for m in healthy) if healthy else "—"
    st.markdown(
        f"""
<div class="ai-route-foot">
  路由：<span class="ai-surface-badge">{html.escape(selected)}</span>
  · 首选 {preferred or "—"}
  · 健康池 {healthy_text}
  {f"· {cost_tier}" if cost_tier else ""}
  {f"<br><span style='opacity:0.92'>{reason}</span>" if reason else ""}
</div>
""",
        unsafe_allow_html=True,
    )
