"""认知偏差可视化卡片 — 自评 vs 客观对比。"""

from __future__ import annotations

import html

import streamlit as st

from engines.cognitive_bias_detector import BiasResult, detect_cognitive_bias, should_show_bias_detection
from utils.emotion_adapter import EmotionAdapter, normalize_emotion_state


def _inject_bias_styles() -> None:
    if st.session_state.get("_cognitive_bias_styles"):
        return
    st.session_state["_cognitive_bias_styles"] = True
    st.markdown(
        """
<style>
.bias-card-shell {
  margin: 0 0 20px;
  padding: 22px 24px;
  background: linear-gradient(145deg, rgba(255,252,249,0.96), rgba(247,243,239,0.9));
  border: 1px solid rgba(184, 144, 138, 0.2);
  border-radius: 14px;
}
.bias-card-title {
  font-size: 15px;
  font-weight: 650;
  color: #2C2420;
  margin-bottom: 6px;
}
.bias-card-sub {
  font-size: 13px;
  color: #8C8279;
  margin-bottom: 16px;
  line-height: 1.5;
}
.bias-compare-row {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
  margin: 16px 0;
}
.bias-score-card {
  flex: 1 1 140px;
  text-align: center;
  padding: 18px 14px;
  border-radius: 12px;
  border: 1px solid rgba(61, 56, 51, 0.08);
}
.bias-score-card--self {
  background: rgba(196, 181, 173, 0.18);
}
.bias-score-card--obj {
  background: rgba(93, 174, 139, 0.12);
  border-color: rgba(93, 174, 139, 0.28);
}
.bias-score-label {
  font-size: 12px;
  color: #8C8279;
  margin-bottom: 6px;
}
.bias-score-num {
  font-size: 36px;
  font-weight: 700;
  line-height: 1.1;
}
.bias-score-num--self { color: #8C8279; }
.bias-score-num--obj { color: #5DAE8B; }
.bias-value-block {
  text-align: center;
  margin: 12px 0 16px;
}
.bias-value-num {
  font-size: 28px;
  font-weight: 700;
}
.bias-value-num--neg { color: #C45C5C; }
.bias-value-num--pos { color: #D4956A; }
.bias-value-num--ok { color: #5DAE8B; }
.bias-severity-tag {
  display: inline-block;
  margin-top: 6px;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
}
.bias-severity--severe-under {
  background: rgba(196, 92, 92, 0.12);
  color: #A04545;
}
.bias-severity--mild-under {
  background: rgba(212, 149, 106, 0.15);
  color: #9E6B40;
}
.bias-severity--ok {
  background: rgba(93, 174, 139, 0.15);
  color: #3D8A6A;
}
.bias-severity--over {
  background: rgba(212, 149, 106, 0.15);
  color: #9E6B40;
}
.bias-correction {
  padding: 14px 16px;
  margin: 14px 0;
  background: rgba(93, 174, 139, 0.08);
  border: 1px solid rgba(93, 174, 139, 0.35);
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  color: #2C5A44;
  line-height: 1.55;
}
.bias-data-note {
  font-size: 12px;
  color: #8C8279;
  margin-top: 10px;
  line-height: 1.55;
}
</style>
""",
        unsafe_allow_html=True,
    )


def _severity_class(severity: str) -> tuple[str, str]:
    if severity == "严重低估":
        return "bias-severity--severe-under", "bias-value-num--neg"
    if severity == "轻度低估":
        return "bias-severity--mild-under", "bias-value-num--neg"
    if severity in ("轻度高估", "严重高估"):
        return "bias-severity--over", "bias-value-num--pos"
    return "bias-severity--ok", "bias-value-num--ok"


def _resolve_emotion() -> str:
    raw = (
        st.session_state.get("workshop_emotion_state")
        or st.session_state.get("emotion_state")
        or EmotionAdapter.CALM
    )
    return normalize_emotion_state(str(raw))


def render_cognitive_bias_gate(
    objective_score: int,
    report_key: str = "default",
) -> bool:
    """
    认知偏差检测门禁。
    返回 True 表示可以展示正式匹配报告；False 表示仍在自评阶段。
    """
    emotion = _resolve_emotion()
    if not should_show_bias_detection(emotion):
        return True

    _inject_bias_styles()
    revealed_key = f"gold_bias_revealed_{report_key}"
    self_key = f"gold_self_match_{report_key}"

    if not st.session_state.get(revealed_key):
        st.markdown(
            """
<div class="bias-card-shell mirror-reveal">
  <div class="bias-card-title">🪞 先别急着看分数</div>
  <div class="bias-card-sub">在揭晓 AI 分析之前，凭直觉估一下你和这个岗位的匹配度——</div>
</div>
""",
            unsafe_allow_html=True,
        )
        self_score = st.slider(
            "凭直觉估一下你的匹配度",
            min_value=0,
            max_value=100,
            value=int(st.session_state.get(self_key, 30)),
            key=f"bias_slider_{report_key}",
        )
        st.session_state[self_key] = self_score

        if st.button("揭晓真实匹配度 →", key=f"bias_reveal_{report_key}", type="primary"):
            st.session_state[revealed_key] = True
            st.rerun()
        return False

    self_score = int(st.session_state.get(self_key, 30))
    result = detect_cognitive_bias(self_score, objective_score, emotion)
    _render_bias_result(result, emotion)
    return True


def _render_bias_result(result: BiasResult, emotion: str) -> None:
    sev_class, val_class = _severity_class(result.severity)
    bias_sign = f"{result.bias_value:+.0f}"

    st.markdown(
        f"""
<div class="bias-card-shell mirror-reveal">
  <div class="bias-card-title">🪞 认知偏差检测</div>
  <div class="bias-card-sub">你的直觉 vs AI 客观评估——看看差距在哪里</div>
  <div class="bias-compare-row">
    <div class="bias-score-card bias-score-card--self">
      <div class="bias-score-label">你的自评</div>
      <div class="bias-score-num bias-score-num--self">{result.self_score}<small style="font-size:16px;">%</small></div>
    </div>
    <div class="bias-score-card bias-score-card--obj">
      <div class="bias-score-label">AI 客观评估</div>
      <div class="bias-score-num bias-score-num--obj">{result.objective_score}<small style="font-size:16px;">%</small></div>
    </div>
  </div>
  <div class="bias-value-block">
    <div class="bias-value-num {val_class}">{bias_sign}<span style="font-size:14px;font-weight:500;"> 分</span></div>
    <div class="bias-severity-tag {sev_class}">{html.escape(result.severity)}</div>
  </div>
  <div class="bias-correction">💚 {html.escape(result.correction_one_liner)}</div>
  <div class="bias-data-note">
    {html.escape(emotion)}状态下求职者平均低估自己 {abs({'焦虑':23,'挫败':18,'迷茫':12}.get(emotion, 5))}%，
    你的偏差比 {result.percentile}% 的人严重。
  </div>
</div>
""",
        unsafe_allow_html=True,
    )

    with st.expander("为什么会低估自己？"):
        st.markdown(result.detailed_analysis)


def render_severe_under_hint() -> None:
    st.markdown(
        '<p style="color:#5DAE8B;font-size:14px;font-weight:600;margin:8px 0 16px;">'
        "👇 看看你的真实匹配度，比你以为的要好</p>",
        unsafe_allow_html=True,
    )
