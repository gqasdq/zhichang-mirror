"""智能模块跳转推荐 — 形成产品闭环动线。"""

from __future__ import annotations

import html
from typing import Any, Optional

import streamlit as st

from ui.sidebar import navigate_to_page
from utils.emotion_adapter import EmotionAdapter, normalize_emotion_state

# 页面 route 映射（与 sidebar.PAGE_ROUTE_MAP 一致）
PAGE_ROUTES = {
    "gold_detector": "gold",
    "gold": "gold",
    "workshop": "workshop",
    "parallel": "parallel",
    "parallel_universe": "parallel",
    "career_gene": "gene",
    "gene": "gene",
    "emotion": "emotion",
}


def _inject_nav_styles() -> None:
    if st.session_state.get("_smart_nav_styles"):
        return
    st.session_state["_smart_nav_styles"] = True
    st.markdown(
        """
<style>
.smart-nav-shell {
  margin: 28px 0 8px;
  padding: 20px 22px;
  background: linear-gradient(135deg, rgba(255,252,249,0.92), rgba(240,235,227,0.75));
  border: 1px solid rgba(184, 144, 138, 0.14);
  border-radius: 14px;
}
.smart-nav-title {
  font-size: 15px;
  font-weight: 650;
  color: #2C2420;
  margin-bottom: 14px;
}
.smart-nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  margin-bottom: 8px;
  background: rgba(255, 255, 255, 0.65);
  border: 1px solid rgba(61, 56, 51, 0.06);
  border-radius: 10px;
  transition: box-shadow 0.2s ease;
}
.smart-nav-item:last-child { margin-bottom: 0; }
.smart-nav-item:hover {
  box-shadow: 0 2px 12px rgba(44, 36, 32, 0.06);
}
.smart-nav-icon { font-size: 20px; flex-shrink: 0; }
.smart-nav-body { flex: 1; min-width: 0; }
.smart-nav-item-title {
  font-size: 14px;
  font-weight: 600;
  color: #2C2420;
}
.smart-nav-reason {
  font-size: 12px;
  color: #8C8279;
  margin-top: 2px;
  line-height: 1.45;
}
</style>
""",
        unsafe_allow_html=True,
    )


def render_smart_nav(
    recommendations: list[dict[str, str]],
    context: dict | None = None,
) -> None:
    """渲染下一步推荐区域。context 可选，用于跨模块数据流转。"""
    if not recommendations:
        return
    recs = recommendations[:2]
    ctx = context or {}
    _inject_nav_styles()

    items_html: list[str] = []
    for idx, rec in enumerate(recs):
        icon = html.escape(rec.get("icon", "→"))
        title = html.escape(rec.get("title", ""))
        reason = html.escape(rec.get("reason", ""))
        items_html.append(
            f"""
<div class="smart-nav-item mirror-reveal mirror-stagger-{min(idx + 1, 4)}">
  <div class="smart-nav-icon">{icon}</div>
  <div class="smart-nav-body">
    <div class="smart-nav-item-title">{title}</div>
    <div class="smart-nav-reason">{reason}</div>
  </div>
</div>"""
        )

    st.markdown(
        f"""
<div class="smart-nav-shell">
  <div class="smart-nav-title">🧭 下一步，你可以试试</div>
  {"".join(items_html)}
</div>
""",
        unsafe_allow_html=True,
    )

    cols = st.columns(len(recs))
    for idx, rec in enumerate(recs):
        page = rec.get("page", "")
        route = PAGE_ROUTES.get(page, page)
        with cols[idx]:
            if st.button(f"前往 {rec.get('title', '')} →", key=f"smart_nav_{route}_{idx}", use_container_width=True):
                _apply_bridge(route, ctx)
                navigate_to_page(route)
                st.rerun()


def _apply_bridge(route: str, ctx: dict) -> None:
    """跳转前写入跨模块上下文。"""
    from core.module_bridge import (
        bridge_emotion_to_gold,
        bridge_empathy_to_emotion,
        bridge_empathy_to_gold,
        bridge_empathy_to_parallel,
        bridge_gold_to_gene,
        bridge_gold_to_parallel,
    )

    if route == "gene" and ctx.get("strengths"):
        bridge_gold_to_gene(
            ctx["strengths"],
            resume_snippet=str(ctx.get("resume_snippet", "") or ""),
        )
    if route == "gold" and ctx.get("emotion_state"):
        bridge_emotion_to_gold(ctx["emotion_state"], ctx.get("summary", ""))
    if route == "parallel":
        if ctx.get("strengths") or ctx.get("resume_snippet"):
            bridge_gold_to_parallel(
                str(ctx.get("resume_snippet", "") or ""),
                worry=str(ctx.get("worry", "") or ""),
                strengths=ctx.get("strengths"),
            )
        empathy = ctx.get("empathy") or {}
        if empathy.get("tags") is not None or empathy.get("description"):
            bridge_empathy_to_parallel(
                empathy.get("tags") or [],
                empathy.get("description") or "",
            )
    if route == "emotion" and ctx.get("empathy"):
        em = ctx["empathy"]
        bridge_empathy_to_emotion(em.get("tags") or [], em.get("description") or "")
    if route == "gold" and ctx.get("empathy"):
        em = ctx["empathy"]
        bridge_empathy_to_gold(em.get("tags") or [], em.get("description") or "")


def get_emotion_nav_recommendations(emotion_state: str) -> list[dict[str, str]]:
    emotion = normalize_emotion_state(emotion_state)
    if emotion == EmotionAdapter.ANXIOUS:
        return [{
            "icon": "🔍",
            "title": "金子探测器",
            "reason": "焦虑时最容易忽略自己的优势",
            "page": "gold_detector",
        }]
    if emotion == EmotionAdapter.FRUSTRATED:
        return [
            {
                "icon": "🌌",
                "title": "平行宇宙",
                "reason": "也许是方向不对，不是你不行",
                "page": "parallel",
            },
            {
                "icon": "🔍",
                "title": "金子探测器",
                "reason": "换个角度，重新看见简历里的金子",
                "page": "gold_detector",
            },
        ]
    if emotion == EmotionAdapter.CONFUSED:
        return [
            {
                "icon": "🧬",
                "title": "职业基因",
                "reason": "不知道去哪？先弄清楚你是什么料",
                "page": "career_gene",
            },
            {
                "icon": "🌌",
                "title": "平行宇宙",
                "reason": "推演不同选择，帮你看清方向",
                "page": "parallel",
            },
        ]
    return [{
        "icon": "🔨",
        "title": "金子工坊",
        "reason": "状态不错，正好优化简历",
        "page": "workshop",
    }]


def get_gold_detector_nav_recommendations(
    match_result: Optional[dict[str, Any]],
    has_jd: bool,
) -> list[dict[str, str]]:
    if not has_jd or not match_result:
        return [
            {
                "icon": "📋",
                "title": "金子探测器",
                "reason": "粘贴目标 JD，解锁关键词匹配分析",
                "page": "gold_detector",
            },
            {
                "icon": "🧬",
                "title": "职业基因",
                "reason": "还不确定方向？先看看你适合什么",
                "page": "career_gene",
            },
        ]

    overall = float(match_result.get("overall_score", 0))
    if overall >= 70:
        return [{
            "icon": "🔨",
            "title": "金子工坊",
            "reason": "基础不错，去打磨到最好",
            "page": "workshop",
        }]
    if overall >= 50:
        return [
            {
                "icon": "🔨",
                "title": "金子工坊",
                "reason": "还有提升空间，逐条优化简历",
                "page": "workshop",
            },
            {
                "icon": "🧭",
                "title": "金子探测器",
                "reason": "对比多个岗位，找到更匹配的方向",
                "page": "gold_detector",
            },
        ]
    return [
        {
            "icon": "🧬",
            "title": "职业基因",
            "reason": "可能方向需要调整，先看看基因图谱",
            "page": "career_gene",
        },
        {
            "icon": "🌌",
            "title": "平行宇宙",
            "reason": "推演不同路径，找到更适合的选择",
            "page": "parallel",
        },
    ]


def get_empathy_nav_recommendations(
    tags: list[str] | None = None,
    description: str = "",
) -> list[dict[str, str]]:
    """人才共情链故事看完后的行动引导。"""
    _ = tags
    desc = (description or "").strip()
    return [
        {
            "icon": "🌌",
            "title": "平行宇宙",
            "reason": "用推演看看，还有没有别的路径",
            "page": "parallel",
        },
        {
            "icon": "🔍",
            "title": "金子探测器",
            "reason": "把共鸣变成行动，从简历优势开始",
            "page": "gold_detector",
        },
    ]


def get_parallel_universe_nav_recommendations() -> list[dict[str, str]]:
    return [
        {
            "icon": "🧬",
            "title": "职业基因",
            "reason": "看清方向后，测测你的职业基因",
            "page": "career_gene",
        },
        {
            "icon": "🔨",
            "title": "金子工坊",
            "reason": "选定了方向，把简历打磨到位",
            "page": "workshop",
        },
    ]


def get_career_gene_nav_recommendations(gene_result: Optional[dict[str, Any]]) -> list[dict[str, str]]:
    hidden = (gene_result or {}).get("隐藏基因") or []
    has_hidden = isinstance(hidden, list) and len(hidden) > 0
    if has_hidden:
        return [
            {
                "icon": "🔍",
                "title": "金子探测器",
                "reason": "隐藏基因需要证据支撑，去简历里找",
                "page": "gold_detector",
            },
            {
                "icon": "🔨",
                "title": "金子工坊",
                "reason": "把潜力写进简历，让 HR 也看见",
                "page": "workshop",
            },
        ]
    return [{
        "icon": "🔨",
        "title": "金子工坊",
        "reason": "基因图谱清晰了，下一步优化简历",
        "page": "workshop",
    }]
