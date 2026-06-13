"""优化效果对比报告 — 优化前 vs 优化后分数。"""

from __future__ import annotations

import html
from typing import Any

import plotly.graph_objects as go
import streamlit as st

from core.constants import PASS_RATE_TIERS

COLOR_BEFORE = "#C4B5AD"
COLOR_AFTER = "#5DAE8B"


def _estimate_pass_rate(overall: float) -> int:
    score = float(overall)
    for threshold, rate in PASS_RATE_TIERS:
        if score >= threshold:
            return rate
    return 1


def _pct_change(before: float, after: float) -> str:
    if before <= 0:
        return "+—"
    delta = (after - before) / before * 100
    sign = "+" if delta >= 0 else ""
    return f"{sign}{delta:.0f}%"


def _inject_report_styles() -> None:
    if st.session_state.get("_optimization_report_styles"):
        return
    st.session_state["_optimization_report_styles"] = True
    st.markdown(
        """
<style>
.opt-report-shell {
  margin: 24px 0;
  padding: 22px 24px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(184, 144, 138, 0.16);
  border-radius: 14px;
}
.opt-report-title {
  font-size: 16px;
  font-weight: 650;
  color: #2C2420;
  margin-bottom: 16px;
}
.opt-score-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 20px;
}
.opt-score-card {
  flex: 0 1 120px;
  text-align: center;
  padding: 16px;
  border-radius: 12px;
}
.opt-score-card--before {
  background: rgba(196, 181, 173, 0.2);
  color: #8C8279;
}
.opt-score-card--after {
  background: rgba(93, 174, 139, 0.14);
  color: #5DAE8B;
}
.opt-score-card--delta {
  flex: 0 1 100px;
  color: #5DAE8B;
}
.opt-score-big {
  font-size: 32px;
  font-weight: 700;
  line-height: 1.1;
}
.opt-score-label {
  font-size: 12px;
  margin-top: 4px;
  color: #8C8279;
}
.opt-pass-rate {
  margin-top: 16px;
  padding: 12px 14px;
  background: rgba(247, 243, 239, 0.8);
  border-radius: 10px;
  font-size: 13px;
  color: #5C4F47;
  line-height: 1.55;
}
.opt-disclaimer {
  font-size: 11px;
  color: #9E8E83;
  margin-top: 10px;
}
</style>
""",
        unsafe_allow_html=True,
    )


def _build_bar_chart(before: dict[str, Any], after: dict[str, Any]) -> go.Figure:
    dims = [
        ("STAR", before.get("star", 0), after.get("star", 0)),
        ("量化", before.get("quantify", 0), after.get("quantify", 0)),
        ("关键词", before.get("keyword", 0), after.get("keyword", 0)),
    ]
    labels = [d[0] for d in dims]
    before_vals = [float(d[1]) for d in dims]
    after_vals = [float(d[2]) for d in dims]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            name="优化前",
            x=labels,
            y=before_vals,
            marker_color=COLOR_BEFORE,
            text=[f"{int(v)}" for v in before_vals],
            textposition="outside",
        )
    )
    fig.add_trace(
        go.Bar(
            name="优化后",
            x=labels,
            y=after_vals,
            marker_color=COLOR_AFTER,
            text=[f"{int(v)}" for v in after_vals],
            textposition="outside",
        )
    )
    fig.update_layout(
        barmode="group",
        height=280,
        margin=dict(l=20, r=20, t=30, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Microsoft YaHei, sans-serif", color="#2C2420", size=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        yaxis=dict(range=[0, 105], gridcolor="rgba(61,56,51,0.06)"),
    )
    return fig


def render_optimization_report(
    before_scores: dict[str, Any],
    after_scores: dict[str, Any],
) -> None:
    """展示优化效果对比报告。"""
    _inject_report_styles()

    before_overall = float(before_scores.get("overall", 0))
    after_overall = float(after_scores.get("overall", 0))
    delta_pct = _pct_change(before_overall, after_overall)
    pass_before = _estimate_pass_rate(before_overall)
    pass_after = _estimate_pass_rate(after_overall)

    st.markdown(
        f"""
<div class="opt-report-shell mirror-reveal">
  <div class="opt-report-title">📈 优化效果报告</div>
  <div class="opt-score-row">
    <div class="opt-score-card opt-score-card--before">
      <div class="opt-score-big">{before_overall:.0f}</div>
      <div class="opt-score-label">优化前</div>
    </div>
    <div class="opt-score-card opt-score-card--delta">
      <div class="opt-score-big">{html.escape(delta_pct)}</div>
      <div class="opt-score-label">提升</div>
    </div>
    <div class="opt-score-card opt-score-card--after">
      <div class="opt-score-big">{after_overall:.0f}</div>
      <div class="opt-score-label">优化后</div>
    </div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    fig = _build_bar_chart(before_scores, after_scores)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    st.markdown(
        f"""
<div class="opt-pass-rate">
  📊 <strong>简历筛选通过率估算</strong>（简化模型，仅供参考）<br/>
  优化前约 <strong>{pass_before}/10</strong> 个岗位 → 优化后约 <strong>{pass_after}/10</strong> 个岗位
</div>
<p class="opt-disclaimer">* 通过率基于综合分的经验估算，实际结果因行业、岗位、竞争程度而异。</p>
<p class="opt-disclaimer">* 优化后分数随采纳项即时更新，无需重新分析整份简历。</p>
""",
        unsafe_allow_html=True,
    )
