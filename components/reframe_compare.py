"""翻案 Before/After 对比卡片 — 金子探测器报告。"""

from __future__ import annotations

import html
import json
import re
from typing import Any

import streamlit as st


def _inject_reframe_styles() -> None:
    if st.session_state.get("_reframe_styles"):
        return
    st.session_state["_reframe_styles"] = True
    st.markdown(
        """
<style>
.reframe-shell { margin: 20px 0; }
.reframe-title {
  font-size: 16px; font-weight: 650; color: #2C2420;
  margin-bottom: 14px;
}
.reframe-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 14px;
}
.reframe-card {
  border-radius: 14px;
  overflow: hidden;
  border: 1px solid rgba(61, 56, 51, 0.08);
  animation: mirror-rise 0.5s cubic-bezier(0.22, 1, 0.36, 1) both;
}
.reframe-card-head {
  padding: 10px 14px;
  font-size: 12px;
  font-weight: 650;
  letter-spacing: 0.03em;
}
.reframe-head-before {
  background: rgba(196, 181, 173, 0.25);
  color: #6B5B52;
}
.reframe-head-after {
  background: rgba(93, 174, 139, 0.18);
  color: #3D8A6A;
}
.reframe-card-body {
  padding: 14px 16px;
  font-size: 13px;
  line-height: 1.65;
  color: #2C2420;
  background: rgba(255, 255, 255, 0.72);
  min-height: 72px;
}
.reframe-pair-wrap {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0;
  border-radius: 14px;
  overflow: hidden;
  border: 1px solid rgba(184, 144, 138, 0.16);
  margin-bottom: 12px;
}
.reframe-pair-wrap .reframe-card { border: none; border-radius: 0; animation: none; }
.reframe-arrow {
  display: flex; align-items: center; justify-content: center;
  background: rgba(247, 243, 239, 0.9);
  color: #B8908A; font-size: 18px; padding: 8px 0;
}
@media (max-width: 640px) {
  .reframe-pair-wrap { grid-template-columns: 1fr; }
}
</style>
""",
        unsafe_allow_html=True,
    )


def _parse_json_block(raw: str) -> dict[str, Any]:
    if not raw:
        return {}
    cleaned = raw.strip()
    if "```json" in cleaned:
        cleaned = cleaned.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in cleaned:
        cleaned = cleaned.split("```", 1)[1].split("```", 1)[0].strip()
    try:
        data = json.loads(cleaned)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", raw)
        if match:
            try:
                data = json.loads(match.group(0))
                return data if isinstance(data, dict) else {}
            except json.JSONDecodeError:
                pass
    return {}


def extract_reframe_pairs(result: dict[str, Any]) -> list[dict[str, str]]:
    """从分析/匹配结果提取 Before/After 翻案对。"""
    pairs: list[dict[str, str]] = []

    for source_key in ("analysis", "match"):
        block = result.get(source_key) or {}
        raw = block.get("raw_content", "") if isinstance(block, dict) else ""
        data = _parse_json_block(raw)

        for item in data.get("gap_reframes") or []:
            if not isinstance(item, dict):
                continue
            before = str(item.get("gap") or item.get("before") or "").strip()
            after = str(item.get("reframe") or item.get("after") or item.get("reframe_angle") or "").strip()
            if before and after:
                pairs.append({"before": before, "after": after, "label": "差距翻案"})

        for item in data.get("reframe_strategies") or []:
            if not isinstance(item, dict):
                continue
            before = str(item.get("gap") or item.get("weakness") or item.get("issue") or "").strip()
            after = str(item.get("reframe_talk_track") or item.get("reframe_strategy") or "").strip()
            if before and after:
                pairs.append({"before": before, "after": after, "label": "面试翻案"})

        for item in data.get("hard_gaps") or []:
            if not isinstance(item, dict):
                continue
            before = str(item.get("gap") or item.get("skill") or "").strip()
            after = str(item.get("reframe_angle") or item.get("reframe_strategy") or "").strip()
            if before and after:
                pairs.append({"before": before, "after": after, "label": "技能翻案"})

    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, str]] = []
    for p in pairs:
        key = (p["before"][:80], p["after"][:80])
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique[:4]


def render_reframe_compare(pairs: list[dict[str, str]]) -> None:
    """渲染翻案 Before/After 卡片组。"""
    if not pairs:
        return
    _inject_reframe_styles()
    st.markdown(
        '<div class="reframe-shell mirror-reveal"><div class="reframe-title">🔏 翻案时刻 · 看看差距怎么变成优势</div>',
        unsafe_allow_html=True,
    )
    for idx, pair in enumerate(pairs):
        before = html.escape(pair.get("before", ""))
        after = html.escape(pair.get("after", ""))
        label = html.escape(pair.get("label", "翻案"))
        delay = idx * 0.08
        st.markdown(
            f"""
<div class="reframe-pair-wrap mirror-reveal" style="animation-delay:{delay}s;">
  <div class="reframe-card">
    <div class="reframe-card-head reframe-head-before">Before · {label}</div>
    <div class="reframe-card-body">{before}</div>
  </div>
  <div class="reframe-card">
    <div class="reframe-card-head reframe-head-after">After · AI 翻案</div>
    <div class="reframe-card-body">{after}</div>
  </div>
</div>
""",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)
