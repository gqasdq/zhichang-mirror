"""AI 技术特性 UI 共享样式 — 对齐 ui/design_system.py 令牌。"""

from __future__ import annotations

import streamlit as st

from ui.design_system import TOKENS


def inject_ai_surface_styles() -> None:
    """注入 AI 推理 / XAI / 路由等模块的统一样式（仅注入一次）。"""
    if st.session_state.get("_ai_surface_styles"):
        return
    st.session_state["_ai_surface_styles"] = True

    ink = TOKENS["ink"]
    muted = TOKENS["muted_light"]
    accent = TOKENS["accent"]
    border = TOKENS["border_accent"]
    surface = TOKENS["surface"]
    bg = TOKENS["bg"]

    st.markdown(
        f"""
<style>
@keyframes ai-rise {{
  from {{ opacity: 0; transform: translateY(6px); }}
  to {{ opacity: 1; transform: translateY(0); }}
}}
.ai-surface {{
  margin: 12px 0 16px;
  padding: 16px 18px;
  background: {surface};
  border: 1px solid {border};
  border-radius: {TOKENS["radius_md"]};
  box-shadow: 0 1px 0 rgba(255,255,255,0.6) inset;
}}
.ai-surface-head {{
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 650;
  color: {ink};
  margin-bottom: 12px;
  letter-spacing: 0.01em;
}}
.ai-surface-badge {{
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 600;
  color: {TOKENS["muted"]};
  background: rgba(184, 144, 138, 0.12);
  border: 1px solid {border};
}}
.ai-step-row {{
  display: grid;
  grid-template-columns: 28px 1fr;
  gap: 10px;
  padding: 10px 12px;
  margin-bottom: 8px;
  background: rgba(255,255,255,0.55);
  border: 1px solid {TOKENS["border"]};
  border-radius: {TOKENS["radius_sm"]};
  animation: ai-rise 0.42s cubic-bezier(0.22, 1, 0.36, 1) both;
}}
.ai-step-row:last-child {{ margin-bottom: 0; }}
.ai-step-index {{
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  color: {accent};
  background: rgba(184, 144, 138, 0.14);
}}
.ai-step-label {{
  font-size: 11px;
  font-weight: 650;
  color: {muted};
  margin-bottom: 2px;
}}
.ai-step-text {{
  font-size: 12px;
  color: {TOKENS["ink_secondary"]};
  line-height: 1.55;
}}
.ai-highlight {{
  display: inline;
  padding: 1px 6px;
  border-radius: 4px;
  background: rgba(184, 144, 138, 0.16);
  color: {TOKENS["muted"]};
  font-weight: 600;
}}
.ai-route-foot {{
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed {border};
  font-size: 11px;
  color: {muted};
}}
@media (prefers-reduced-motion: reduce) {{
  .ai-step-row {{ animation: none !important; }}
}}
</style>
""",
        unsafe_allow_html=True,
    )
