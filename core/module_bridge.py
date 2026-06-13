"""跨模块数据流转 — 情绪 / 探测器 / 平行宇宙 / 职业基因 / 共情链联动。

Session 键约定（写入时以「主键」为准，别名仅兼容旧页面读取）：
- emotion_state          主键：情绪标签（各模块统一）
- workshop_emotion_state 别名：工坊页读取，由 emotion_state 同步
- gene_text_input        主键：职业基因测序输入
- resume_text            别名：基因页历史兼容
- parallel_resume_text   主键：平行宇宙简历
- gold_resume_text       主键：金子探测器简历
- bridge_*               桥接元数据（摘要、优势、路径选择等）
"""

from __future__ import annotations

import json
from typing import Any, Optional

try:
    import streamlit as st
except ImportError:
    st = None  # type: ignore

# --- 主键常量 -----------------------------------------------------------------

KEY_EMOTION = "emotion_state"
KEY_GENE_INPUT = "gene_text_input"
KEY_PARALLEL_RESUME = "parallel_resume_text"
KEY_PARALLEL_WORRY = "parallel_worry"
KEY_GOLD_RESUME = "gold_resume_text"
KEY_GOLD_RESUME_INPUT = "gold_resume_input"

KEY_BRIDGE_EMOTION_SUMMARY = "bridge_emotion_summary"
KEY_BRIDGE_GOLD_STRENGTHS = "bridge_gold_strengths"
KEY_BRIDGE_PARALLEL_CHOICE = "bridge_parallel_choice"
KEY_BRIDGE_EMPATHY_CONTEXT = "bridge_empathy_context"
KEY_BRIDGE_GOLD_TO_PARALLEL = "bridge_gold_to_parallel_note"

# 兼容旧代码读取的别名（仅通过 _sync_aliases 写入）
_LEGACY_GENE_RESUME = "resume_text"
_LEGACY_WORKSHOP_EMOTION = "workshop_emotion_state"


def _set(key: str, value: Any) -> None:
    if st is not None:
        st.session_state[key] = value


def _sync_aliases(**pairs: Any) -> None:
    """把主键同步到仍依赖旧键名的页面。"""
    for key, value in pairs.items():
        _set(key, value)


def bridge_emotion_to_gold(emotion_state: str, summary: str = "") -> None:
    """情绪急救站 → 金子探测器。"""
    _set(KEY_EMOTION, emotion_state)
    _sync_aliases(**{_LEGACY_WORKSHOP_EMOTION: emotion_state})
    if summary:
        _set(KEY_BRIDGE_EMOTION_SUMMARY, summary)


def bridge_gold_to_gene(strengths: list[str], resume_snippet: str = "") -> None:
    """金子探测器 → 职业基因。"""
    _set(KEY_BRIDGE_GOLD_STRENGTHS, strengths[:5])
    if resume_snippet:
        snippet = resume_snippet.strip()
        _set(KEY_GENE_INPUT, snippet)
        _sync_aliases(**{_LEGACY_GENE_RESUME: snippet})


def bridge_gold_to_parallel(
    resume_snippet: str = "",
    *,
    worry: str = "",
    strengths: list[str] | None = None,
) -> None:
    """金子探测器 → 平行宇宙：带入简历与纠结，推演不同路径。"""
    if resume_snippet.strip():
        snippet = resume_snippet.strip()
        _set(KEY_PARALLEL_RESUME, snippet)
        _set(KEY_GOLD_RESUME, snippet)
        _sync_aliases(**{KEY_GOLD_RESUME_INPUT: snippet})
    if worry.strip():
        _set(KEY_PARALLEL_WORRY, worry.strip())
    if strengths:
        _set(KEY_BRIDGE_GOLD_STRENGTHS, strengths[:5])
    note_parts = []
    if strengths:
        note_parts.append("已识别优势：" + "、".join(strengths[:5]))
    if worry.strip():
        note_parts.append(f"当前纠结：{worry.strip()}")
    if note_parts:
        _set(KEY_BRIDGE_GOLD_TO_PARALLEL, "；".join(note_parts))


def bridge_parallel_to_gene(result: dict[str, Any]) -> None:
    """平行宇宙 → 职业基因：提取选中路径摘要作为测序输入。"""
    mirror_a = result.get("mirror_a") or {}
    title = str(mirror_a.get("title", ""))
    summary = str(mirror_a.get("summary", ""))
    y5 = mirror_a.get("year5") or {}
    position = str(y5.get("position", ""))
    parts = [
        f"我在平行宇宙推演中纠结的方向：{title}",
        summary,
        f"5年后可能的状态：{position}" if position else "",
    ]
    text = "\n".join(p for p in parts if p.strip())
    _set(KEY_GENE_INPUT, text)
    _sync_aliases(**{_LEGACY_GENE_RESUME: text})
    _set(KEY_BRIDGE_PARALLEL_CHOICE, title)


def bridge_empathy_to_emotion(tags: list[str], description: str = "") -> None:
    """人才共情链 → 情绪急救站：带入处境继续倾诉。"""
    ctx = {
        "tags": [str(t) for t in (tags or [])[:8]],
        "description": (description or "").strip()[:2000],
        "target": "emotion",
    }
    _set(KEY_BRIDGE_EMPATHY_CONTEXT, ctx)
    _set(KEY_BRIDGE_EMOTION_SUMMARY, (description or "").strip()[:500])


def bridge_empathy_to_gold(tags: list[str], description: str = "") -> None:
    """人才共情链 → 金子探测器：从故事共鸣转向简历优势挖掘。"""
    ctx = {
        "tags": [str(t) for t in (tags or [])[:8]],
        "description": (description or "").strip()[:2000],
        "target": "gold",
    }
    _set(KEY_BRIDGE_EMPATHY_CONTEXT, ctx)
    if description.strip():
        _set(KEY_BRIDGE_EMOTION_SUMMARY, description.strip()[:500])


def bridge_empathy_to_parallel(tags: list[str], description: str = "") -> None:
    """人才共情链 → 平行宇宙：用处境作为推演纠结输入。"""
    ctx = {
        "tags": [str(t) for t in (tags or [])[:8]],
        "description": (description or "").strip()[:2000],
        "target": "parallel",
    }
    _set(KEY_BRIDGE_EMPATHY_CONTEXT, ctx)
    worry = (description or "").strip()
    if worry:
        _set(KEY_PARALLEL_WORRY, worry[:800])


def bridge_gene_to_workshop(gene_result: dict[str, Any]) -> None:
    """职业基因 → 金子工坊：推荐岗位写入 JD 提示。"""
    jobs = gene_result.get("推荐岗位方向") or []
    if jobs and isinstance(jobs[0], dict):
        job = jobs[0]
        jd_hint = (
            f"岗位：{job.get('岗位名称', '')}\n"
            f"为什么适合：{job.get('为什么适合你', '')}\n"
            f"入门第一步：{job.get('入门第一步', '')}"
        )
        _set("workshop_jd_text", jd_hint)
        _set("workshop_jd_input", jd_hint)


def get_bridge_context() -> dict[str, Any]:
    """读取当前跨模块上下文。"""
    if st is None:
        return {}
    empathy_ctx = st.session_state.get(KEY_BRIDGE_EMPATHY_CONTEXT)
    return {
        "emotion_summary": st.session_state.get(KEY_BRIDGE_EMOTION_SUMMARY, ""),
        "gold_strengths": st.session_state.get(KEY_BRIDGE_GOLD_STRENGTHS, []),
        "parallel_choice": st.session_state.get(KEY_BRIDGE_PARALLEL_CHOICE, ""),
        "empathy_context": empathy_ctx if isinstance(empathy_ctx, dict) else {},
        "gold_to_parallel_note": st.session_state.get(KEY_BRIDGE_GOLD_TO_PARALLEL, ""),
    }


def render_bridge_hint() -> Optional[str]:
    """返回跨模块流转提示文案（供各页面展示）。"""
    ctx = get_bridge_context()
    if ctx.get("gold_to_parallel_note"):
        return f"已从金子探测器带入：{ctx['gold_to_parallel_note']}"
    empathy = ctx.get("empathy_context") or {}
    if empathy.get("target") == "parallel" and empathy.get("description"):
        return "已从人才共情链带入你的处境，可直接照一照推演路径"
    if empathy.get("target") == "gold":
        return "已从人才共情链带入共鸣处境，可上传简历挖掘优势"
    if empathy.get("target") == "emotion":
        return "已从人才共情链带入处境，情绪急救站会继续倾听"
    if ctx.get("parallel_choice"):
        return f"已从平行宇宙带入路径：{ctx['parallel_choice']}"
    if ctx.get("gold_strengths"):
        return f"已从金子探测器带入 {len(ctx['gold_strengths'])} 项优势"
    if ctx.get("emotion_summary"):
        return "已从情绪急救站带入你的倾诉摘要"
    return None
