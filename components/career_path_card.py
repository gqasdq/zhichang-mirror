"""成长路径图组件。"""

from __future__ import annotations

import html

import streamlit as st

from engines.career_path_engine import CareerPathResult, GrowthPath

ACCENT = "#B8908A"
TEXT = "#2C2420"
MUTED = "#8C8279"
GREEN = "#5DAE8B"


def _stars(count: int) -> str:
    count = max(1, min(5, count))
    return "⭐" * count + "☆" * (5 - count)


def _level_salary(path: GrowthPath, level_num: int) -> str:
    for item in path.levels:
        if item.level == level_num:
            return item.salary_range
    return "-"


def _render_single_path(path: GrowthPath) -> None:
    primary_badge = " 🏆首选" if path.is_primary else ""
    stars = _stars(path.match_stars)

    st.markdown(f"#### {html.escape(path.path_name)}{primary_badge}")
    reason = html.escape(path.path_match_reason)
    st.markdown(
        f'<div style="color:{MUTED}; font-size:12px; margin-bottom:8px;">'
        f"匹配度 {stars} · {reason}</div>",
        unsafe_allow_html=True,
    )

    cols = st.columns(5)
    for i, level in enumerate(path.levels[:5]):
        is_current = level.level == path.current_level
        is_past = level.level < path.current_level
        if is_current:
            bg = "rgba(184,144,138,0.2)"
            border = f"2px solid {ACCENT}"
            indicator = " ⭐"
        elif is_past:
            bg = "rgba(93,174,139,0.1)"
            border = "1px solid rgba(61,56,51,0.06)"
            indicator = " ✓"
        else:
            bg = "rgba(255,255,255,0.55)"
            border = "1px solid rgba(61,56,51,0.06)"
            indicator = ""

        with cols[i]:
            st.markdown(
                f"""
<div style="text-align:center; padding:10px 6px; border-radius:10px;
            background:{bg}; border:{border}; margin-bottom:4px;">
    <div style="font-size:11px; color:{MUTED};">L{level.level}{indicator}</div>
    <div style="font-size:12px; font-weight:600; color:{TEXT}; margin-top:2px;">
        {html.escape(level.title)}
    </div>
    <div style="font-size:11px; color:{ACCENT}; margin-top:4px;">
        {html.escape(level.salary_range)}
    </div>
</div>
""",
                unsafe_allow_html=True,
            )

    next_level = min(path.current_level + 1, 5)
    next_title = next(
        (lv.title for lv in path.levels if lv.level == next_level),
        f"L{next_level}",
    )
    if path.current_level >= 5:
        position_text = f"你目前在 L{path.current_level}（{path.levels[-1].title if path.levels else ''}）"
    else:
        position_text = (
            f"你目前在 L{path.current_level}-L{next_level} 之间，升到 L{next_level}（{next_title}）需要："
        )

    st.markdown(f"**📍 {position_text}**")

    for skill in path.skills_met:
        st.markdown(f"✅ {skill}")
    for skill in path.skills_gap:
        st.markdown(f"⚠️ {skill}")

    if path.actions:
        st.markdown("**💡 建议行动：**")
        for idx, action in enumerate(path.actions[:3], start=1):
            st.markdown(f"{idx}. {action}")

    st.markdown("---")


def _render_path_comparison(paths: list[GrowthPath]) -> None:
    if len(paths) < 2:
        return

    st.markdown("**路径对比**")
    header = "| 路径 | 匹配度 | 起步薪资 | 3年薪资 | 你离下一级的距离 |"
    sep = "| --- | --- | --- | --- | --- |"
    rows = [header, sep]

    for path in paths:
        start_salary = _level_salary(path, path.current_level + 1 if path.current_level < 5 else path.current_level)
        if path.current_level == 1:
            start_salary = _level_salary(path, 2)
        year3_salary = _level_salary(path, 4)
        gap_count = len(path.skills_gap)
        gap_text = f"{gap_count}项能力待补" if gap_count else "已接近下一级"
        rows.append(
            f"| {path.path_name} | {_stars(path.match_stars)} | {start_salary} | {year3_salary} | {gap_text} |"
        )

    st.markdown("\n".join(rows))
    st.markdown(
        f'<div style="color:{MUTED}; font-size:12px; margin-top:8px;">'
        "💡 选哪条？匹配度最高≠一定要选。考虑你真正感兴趣的方向。"
        "</div>",
        unsafe_allow_html=True,
    )


def render_career_path(result: CareerPathResult) -> None:
    """渲染成长路径图。"""
    if not result.paths:
        st.info("成长路径暂时不可用，请稍后重试。")
        return

    if result.summary:
        safe_summary = html.escape(result.summary)
        st.markdown(
            f'<div style="color:{MUTED}; font-size:13px; margin-bottom:12px;">{safe_summary}</div>',
            unsafe_allow_html=True,
        )

    for path in result.paths:
        _render_single_path(path)

    _render_path_comparison(result.paths)

    st.markdown(
        f'<div style="color:{MUTED}; font-size:13px; margin:12px 0;">'
        "确定方向后，去金子工坊把简历优化成对应方向。"
        "</div>",
        unsafe_allow_html=True,
    )
    if st.button("🔨 去金子工坊优化简历", type="primary", key="gene_go_workshop"):
        from ui.sidebar import navigate_to_page

        resume = st.session_state.get("gene_user_input", "")
        if resume:
            st.session_state.workshop_resume_text = resume
            st.session_state.workshop_resume_input = resume
        navigate_to_page("workshop")
        st.rerun()
