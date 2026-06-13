"""投递方向雷达 — 多 JD 对比匹配组件。"""

from __future__ import annotations

import html
from typing import Optional

import streamlit as st


def _result_data(item: dict) -> dict:
    """统一取出匹配结果 dict（兼容已序列化与 dataclass）。"""
    result = item.get("result") or {}
    if hasattr(result, "model_dump"):
        return result.model_dump()
    if isinstance(result, dict):
        return result
    return {}


def _score_badge(score: float) -> str:
    if score >= 70:
        return "🏆"
    if score < 55:
        return "⚠️"
    return "🟡"


def render_radar_compare(match_results: list[dict]) -> Optional[str]:
    """
    渲染投递方向雷达对比。
    返回用户选择的岗位名称；只有 1 个 JD 时返回 None（走原有逻辑）。
    """
    if len(match_results) <= 1:
        return None

    parsed = [
        {"name": item["name"], "data": _result_data(item)}
        for item in match_results
    ]
    best = max(parsed, key=lambda x: float(x["data"].get("overall_score", 0)))

    st.markdown(
        '<div class="jd-match-title" style="margin-bottom:16px;">🧭 投递方向雷达</div>',
        unsafe_allow_html=True,
    )

    cols = st.columns(len(parsed))
    for i, item in enumerate(parsed):
        name = item["name"]
        score = float(item["data"].get("overall_score", 0))
        is_best = item["name"] == best["name"]
        border_color = "#B8908A" if is_best else "rgba(61,56,51,0.1)"
        badge = _score_badge(score)
        safe_name = html.escape(name, quote=True)

        with cols[i]:
            st.markdown(
                f"""
<div style="text-align:center; padding:16px; border-radius:12px;
            border:2px solid {border_color}; background:rgba(255,255,255,0.55);">
    <div style="font-size:32px; font-weight:700; color:#2C2420;">{score:.0f}</div>
    <div style="font-size:13px; color:#8C8279; margin-top:4px;">{safe_name}</div>
    <div style="margin-top:8px;">{badge}</div>
</div>
""",
                unsafe_allow_html=True,
            )

    best_score = float(best["data"].get("overall_score", 0))
    best_matched = best["data"].get("keyword_matched") or []
    matched_text = "、".join(best_matched[:5]) if best_matched else "综合维度表现突出"
    st.markdown(
        f"🏆 **最佳匹配：{best['name']}（{best_score:.0f}分）**  \n"
        f"你的简历在 **{best['name']}** 方向匹配度最高，核心优势：{matched_text}"
    )

    for item in parsed:
        if item["name"] == best["name"]:
            continue
        score = float(item["data"].get("overall_score", 0))
        badge = _score_badge(score)
        missing = item["data"].get("keyword_missing") or []
        missing_text = "、".join(missing[:5]) if missing else "部分岗位要求尚未覆盖"
        level = "差距较大" if score < 55 else "中等匹配"
        st.markdown(f"{badge} **{item['name']}（{score:.0f}分）**：{level}  \n缺少：{missing_text}")

    st.markdown("---")
    st.markdown("**详细对比**")

    names = [item["name"] for item in parsed]
    header = "| 指标 | " + " | ".join(names) + " |"
    sep = "| --- | " + " | ".join(["---"] * len(names)) + " |"

    def _row(label: str, key: str) -> str:
        cells = []
        for item in parsed:
            val = int(item["data"].get(key, 0))
            cells.append(f"{val}%")
        return "| " + label + " | " + " | ".join(cells) + " |"

    table = "\n".join([
        header,
        sep,
        _row("关键词匹配", "keyword_score"),
        _row("STAR 结构", "star_score"),
        _row("量化表达", "quant_score"),
    ])
    st.markdown(table)
    st.caption("STAR 结构与量化表达为简历自身属性，不同岗位方向下分数相同。")

    default_idx = names.index(best["name"]) if best["name"] in names else 0
    selected = st.selectbox(
        "选择岗位方向，进入金子工坊优化",
        options=names,
        index=default_idx,
        key="radar_jd_select",
    )
    return selected
