"""平行宇宙后悔值可视化。"""

from __future__ import annotations

import html

import streamlit as st

from engines.regret_calculator import RegretComparison, compare_mirrors
from ui.design_system import TOKENS

_PATH_STYLES = {
    "a": ("regret-fill--a", TOKENS["accent"], "路径 A"),
    "b": ("regret-fill--b", "#5DAE8B", "路径 B"),
    "c": ("regret-fill--c", "#8B9EB5", "路径 C"),
}


def _inject_regret_styles() -> None:
    if st.session_state.get("_regret_styles"):
        return
    st.session_state["_regret_styles"] = True
    st.markdown(
        f"""
<style>
.regret-shell {{
  margin: 20px 0;
  padding: 20px 22px;
  background: {TOKENS["surface"]};
  border: 1px solid {TOKENS["border_accent"]};
  border-radius: 14px;
}}
.regret-title {{ font-size: 15px; font-weight: 650; color: {TOKENS["ink"]}; margin-bottom: 14px; }}
.regret-bars {{ display: flex; gap: 16px; flex-wrap: wrap; }}
.regret-col {{ flex: 1 1 180px; min-width: 0; }}
.regret-label {{ font-size: 13px; font-weight: 600; color: {TOKENS["ink_secondary"]}; margin-bottom: 8px; }}
.regret-track {{
  height: 10px; background: rgba(61,56,51,0.08); border-radius: 5px; overflow: hidden;
}}
.regret-fill {{ height: 100%; border-radius: 5px; transition: width 0.6s cubic-bezier(0.22,1,0.36,1); }}
.regret-fill--a {{ background: linear-gradient(90deg, #B8908A, #D4956A); }}
.regret-fill--b {{ background: linear-gradient(90deg, #7B9E87, #5DAE8B); }}
.regret-fill--c {{ background: linear-gradient(90deg, #8B9EB5, #6B8FA8); }}
.regret-pct {{ font-size: 22px; font-weight: 700; margin-top: 6px; }}
.regret-insight {{
  margin-top: 14px; padding: 12px 14px;
  background: rgba(93, 174, 139, 0.1);
  border-radius: 10px; font-size: 13px; color: #2C5A44; line-height: 1.55;
}}
.regret-note {{ font-size: 11px; color: {TOKENS["muted_light"]}; margin-top: 8px; }}
.regret-lowest {{
  display: inline-block; margin-left: 6px; padding: 1px 7px;
  font-size: 10px; font-weight: 600; color: #2C5A44;
  background: rgba(93, 174, 139, 0.18); border-radius: 999px;
}}
</style>
""",
        unsafe_allow_html=True,
    )


def _render_path_column(item_key: str, label: str, regret: int, is_lowest: bool) -> str:
    css_class, color, prefix = _PATH_STYLES.get(item_key, _PATH_STYLES["a"])
    badge = '<span class="regret-lowest">最低</span>' if is_lowest else ""
    # 注意：HTML 不能有行首缩进，否则 Streamlit Markdown 会当成代码块展示
    return (
        f'<div class="regret-col">'
        f'<div class="regret-label">{prefix} · {html.escape(label)}{badge}</div>'
        f'<div class="regret-track">'
        f'<div class="regret-fill {css_class}" style="width:{regret}%;"></div>'
        f"</div>"
        f'<div class="regret-pct" style="color:{color};">{regret}%</div>'
        f'<div class="regret-note">可能后悔的概率（估算）</div>'
        f"</div>"
    )


def render_regret_meter(result: dict) -> RegretComparison:
    """渲染 A/B/C 三条路径后悔值对比。"""
    comp = compare_mirrors(result)
    _inject_regret_styles()

    min_val = min((p.regret for p in comp.paths), default=0)
    lowest_count = sum(1 for p in comp.paths if p.regret == min_val)
    show_lowest_badge = not comp.is_tied and lowest_count == 1

    columns_html = "".join(
        _render_path_column(
            p.key,
            p.label,
            p.regret,
            show_lowest_badge and p.regret == min_val,
        )
        for p in comp.paths
    )

    st.markdown(
        (
            '<div class="regret-shell mirror-reveal">'
            '<div class="regret-title">⚖️ 后悔值对比 · 三条路径</div>'
            f'<div class="regret-bars">{columns_html}</div>'
            f'<div class="regret-insight">💡 {html.escape(comp.insight)}</div>'
            '<div class="regret-note">* 基于风险项、稳定性与成长空间的简化模型，供决策参考，非预测。</div>'
            "</div>"
        ),
        unsafe_allow_html=True,
    )
    return comp
