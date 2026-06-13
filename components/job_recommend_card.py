"""岗位方向推荐卡片组件。"""

from __future__ import annotations

import html
from urllib.parse import quote

import streamlit as st

from engines.job_recommender import JobRecommendResult


def render_job_recommendations(result: JobRecommendResult, city: str = "全国") -> None:
    """渲染岗位推荐卡片。"""
    if not result.recommendations:
        return

    st.markdown("### 🧭 推荐岗位方向")
    if result.summary:
        safe_summary = html.escape(result.summary, quote=True)
        st.markdown(
            f'<div style="color:#8C8279; font-size:13px; margin-bottom:12px;">{safe_summary}</div>',
            unsafe_allow_html=True,
        )

    medals = ["🏆", "🥈", "3️⃣", "4️⃣", "5️⃣"]
    safe_city = quote(city, safe="")

    for i, rec in enumerate(result.recommendations):
        medal = medals[i] if i < len(medals) else "·"
        safe_title = html.escape(rec.title, quote=True)
        safe_salary = html.escape(rec.salary_range, quote=True)
        safe_reason = html.escape(rec.match_reason, quote=True)
        safe_matched = html.escape(" · ".join(rec.ability_match), quote=True)
        safe_gap = html.escape(" · ".join(rec.ability_gap), quote=True)
        safe_keyword = html.escape(rec.search_keyword, quote=True)
        search_url = (
            f"https://sou.zhaopin.com/?jl={safe_city}&kw={quote(rec.search_keyword, safe='')}"
        )

        st.markdown(
            f"""
<div style="background:rgba(255,255,255,0.55); border:1px solid rgba(61,56,51,0.06);
            border-radius:14px; padding:16px; margin-bottom:12px;">
    <div style="display:flex; justify-content:space-between; align-items:center;">
        <span style="font-size:16px; font-weight:600; color:#2C2420;">
            {medal} {safe_title}
        </span>
        <span style="font-size:14px; color:#B8908A; font-weight:500;">{safe_salary}</span>
    </div>
    <div style="color:#6B5B52; font-size:13px; margin-top:6px;">{safe_reason}</div>
    <div style="margin-top:8px;">
        <span style="font-size:12px; color:#5DAE8B;">✅ 已匹配：</span>
        <span style="font-size:12px; color:#2C2420;">{safe_matched or "—"}</span>
    </div>
    <div style="margin-top:4px;">
        <span style="font-size:12px; color:#C62828;">❌ 待补强：</span>
        <span style="font-size:12px; color:#2C2420;">{safe_gap or "—"}</span>
    </div>
</div>
""",
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<a href="{search_url}" target="_blank" rel="noopener noreferrer" '
            f'style="display:inline-block; font-size:12px; color:#4A90D9; '
            f'text-decoration:none; margin-top:-8px; margin-bottom:12px; margin-left:4px;">'
            f"🔗 去智联招聘搜索「{safe_keyword}」→</a>",
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div style="color:#B8AFA5; font-size:11px;">'
        "💡 推荐基于AI分析，非真实岗位。点击可跳转智联招聘搜索真实职位。"
        "</div>",
        unsafe_allow_html=True,
    )
