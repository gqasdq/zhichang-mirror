"""平行宇宙 - 分支故事交互组件。"""

from __future__ import annotations

import logging
from html import escape
from typing import Any, Callable, Dict, List, Optional

import streamlit as st

from core.analytics import track_module_enter
from core.parallel_engine import (
    BRANCH_STORY_FALLBACK_MSG,
    generate_branch_story_continue,
    generate_branch_story_start,
    is_branch_story_fallback,
    parse_choice_point,
)

ACCENT = "#B8908A"
TEXT = "#2C2420"
MUTED = "#8C8279"
BG_OUTLINE = "#F0EBE3"

logger = logging.getLogger(__name__)


def init_branch_story_state() -> None:
    defaults = {
        "parallel_choices": [],
        "parallel_story_parts": [],
        "parallel_current_node": 0,
        "parallel_story_pending": None,
        "parallel_story_complete": False,
        "parallel_story_loading": False,
        "parallel_story_card_id": "",
        "parallel_story_raw_start": "",
        "parallel_story_error": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value if not isinstance(value, list) else []


def reset_branch_story_state() -> None:
    st.session_state.parallel_choices = []
    st.session_state.parallel_story_parts = []
    st.session_state.parallel_current_node = 0
    st.session_state.parallel_story_pending = None
    st.session_state.parallel_story_complete = False
    st.session_state.parallel_story_loading = False
    st.session_state.parallel_story_card_id = ""
    st.session_state.parallel_story_raw_start = ""
    st.session_state.parallel_story_error = ""


def _inject_branch_styles() -> None:
    st.markdown(
        f"""
<style>
.parallel-story-block {{
    font-size: 14px;
    line-height: 1.75;
    color: {TEXT};
    margin: 8px 0 12px;
    white-space: pre-wrap;
}}
.parallel-choice-prompt {{
    text-align: center;
    font-size: 15px;
    font-weight: 700;
    color: {TEXT};
    margin: 14px 0 10px;
}}
.parallel-path-recap {{
    font-size: 12px;
    color: {MUTED};
    margin: 12px 0 8px;
    line-height: 1.6;
}}
.st-key-parallel_choice_a button,
.st-key-parallel_choice_b button {{
    background: {BG_OUTLINE} !important;
    color: {TEXT} !important;
    border: 1px solid rgba(184,144,138,0.45) !important;
    border-radius: 10px !important;
    font-size: 13px !important;
    line-height: 1.45 !important;
    min-height: 52px !important;
    white-space: normal !important;
}}
.st-key-parallel_choice_a button:hover,
.st-key-parallel_choice_b button:hover {{
    border-color: {ACCENT} !important;
    background: rgba(184,144,138,0.08) !important;
}}
.st-key-parallel_choice_a_selected button,
.st-key-parallel_choice_b_selected button {{
    background: {ACCENT} !important;
    color: #FFFFFF !important;
    border-color: {ACCENT} !important;
}}
.st-key-parallel_rewalk button {{
    background: {BG_OUTLINE} !important;
    color: {TEXT} !important;
    border: 1px solid rgba(184,144,138,0.35) !important;
}}
</style>
""",
        unsafe_allow_html=True,
    )


def _format_story_text(text: str) -> str:
    return escape(str(text or "").strip()).replace("\n", "<br>")


def _build_path_recap() -> str:
    choices: List[Dict[str, Any]] = st.session_state.get("parallel_choices", [])
    if not choices:
        return ""
    segments = [f"选择{idx + 1}: {item.get('label', '')}" for idx, item in enumerate(choices)]
    ending = " → 结局" if st.session_state.get("parallel_story_complete") else ""
    return "你选择的路径：" + " → ".join(segments) + ending


def _append_story_segment(raw_segment: str) -> bool:
    if is_branch_story_fallback(raw_segment):
        return False

    parsed = parse_choice_point(raw_segment)
    parts: List[str] = st.session_state.parallel_story_parts
    if parsed["has_choice"]:
        if parsed["story_before"]:
            parts.append(parsed["story_before"])
        st.session_state.parallel_story_pending = {
            "option_a": parsed["option_a"],
            "option_b": parsed["option_b"],
        }
        st.session_state.parallel_story_complete = False
    else:
        if raw_segment.strip():
            parts.append(raw_segment.strip())
        st.session_state.parallel_story_pending = None
        st.session_state.parallel_story_complete = True
    return True


def start_branch_story(
    card_id: str,
    context_builder: Callable[[], Dict[str, str]],
) -> None:
    """启动分支故事（牌4）。"""
    init_branch_story_state()
    reset_branch_story_state()
    st.session_state.parallel_story_card_id = card_id
    st.session_state.parallel_story_loading = True
    st.session_state.parallel_story_error = ""

    ctx = context_builder()
    try:
        raw = generate_branch_story_start(**ctx)
    except Exception:
        raw = BRANCH_STORY_FALLBACK_MSG

    st.session_state.parallel_story_raw_start = raw
    st.session_state.parallel_story_parts = []
    if not _append_story_segment(raw):
        st.session_state.parallel_story_error = "镜语者暂时没连上，请稍后重试。"
        st.session_state.parallel_story_raw_start = ""
    st.session_state.parallel_current_node = 0 if st.session_state.parallel_story_pending else 1
    st.session_state.parallel_story_loading = False


def _continue_after_choice(side: str, label: str, context_builder: Callable[[], Dict[str, str]]) -> None:
    pending = st.session_state.parallel_story_pending
    choices: List[Dict[str, Any]] = st.session_state.parallel_choices
    choices.append({"node": len(choices) + 1, "side": side, "label": label})
    st.session_state.parallel_choices = choices
    st.session_state.parallel_story_pending = None
    st.session_state.parallel_story_loading = True
    st.session_state.parallel_story_error = ""

    ctx = context_builder()
    try:
        raw = generate_branch_story_continue(
            story_parts=st.session_state.parallel_story_parts,
            choices=choices,
            chosen_side=side,
            chosen_label=label,
            **ctx,
        )
    except Exception as exc:
        logger.exception("branch story continue failed: %s", exc)
        raw = BRANCH_STORY_FALLBACK_MSG

    if not _append_story_segment(raw):
        choices.pop()
        st.session_state.parallel_choices = choices
        st.session_state.parallel_story_pending = pending
        st.session_state.parallel_story_error = "续写超时或失败，请重新点击上方选项重试。"
        st.session_state.parallel_story_loading = False
        return

    st.session_state.parallel_current_node = len(choices)
    st.session_state.parallel_story_loading = False


def _rewalk_from_first_choice() -> None:
    raw = st.session_state.get("parallel_story_raw_start", "")
    st.session_state.parallel_choices = []
    st.session_state.parallel_story_parts = []
    st.session_state.parallel_story_complete = False
    st.session_state.parallel_story_pending = None
    st.session_state.parallel_story_error = ""
    _append_story_segment(raw)
    st.session_state.parallel_current_node = 0


def get_branch_story_full_text() -> str:
    parts: List[str] = st.session_state.get("parallel_story_parts", [])
    recap = _build_path_recap()
    body = "\n\n".join(part for part in parts if part)
    if recap:
        return f"{body}\n\n{recap}"
    return body


def render_branch_story(
    card_title: str,
    card_color: str,
    context_builder: Callable[[], Dict[str, str]],
) -> None:
    """渲染带分支选择的故事区域。"""
    init_branch_story_state()
    _inject_branch_styles()

    st.markdown(
        f'<div class="flip-result" style="border-left-color:{escape(card_color)};">',
        unsafe_allow_html=True,
    )
    st.markdown(f"**{escape(card_title)}**")

    parts: List[str] = st.session_state.get("parallel_story_parts", [])
    if parts:
        combined = "\n\n".join(parts)
        st.markdown(
            f'<div class="parallel-story-block">{_format_story_text(combined)}</div>',
            unsafe_allow_html=True,
        )

    story_error = st.session_state.get("parallel_story_error", "")
    if story_error:
        st.error(story_error)

    pending = st.session_state.get("parallel_story_pending")
    if pending and isinstance(pending, dict):
        choice_round = len(st.session_state.get("parallel_choices", [])) + 1
        st.caption(
            f"完整5年路径分 3 段展开：第1段只看第1年，"
            f"选 2 次后看到完整结局（当前待第 {choice_round} 次选择）。"
        )
        st.markdown('<div class="parallel-choice-prompt">你会怎么选？</div>', unsafe_allow_html=True)
        col_a, col_b = st.columns(2)
        option_a = str(pending.get("option_a", "选项A")).strip()
        option_b = str(pending.get("option_b", "选项B")).strip()
        with col_a:
            if st.button(option_a, key="parallel_choice_a", use_container_width=True):
                with st.spinner("镜语者正在沿你的选择续写..."):
                    _continue_after_choice("A", option_a, context_builder)
                st.rerun()
        with col_b:
            if st.button(option_b, key="parallel_choice_b", use_container_width=True):
                with st.spinner("镜语者正在沿你的选择续写..."):
                    _continue_after_choice("B", option_b, context_builder)
                st.rerun()

    if st.session_state.get("parallel_story_complete"):
        recap = _build_path_recap()
        if recap:
            st.markdown(f'<div class="parallel-path-recap">{escape(recap)}</div>', unsafe_allow_html=True)
        if st.button("🔄 重走另一条路", key="parallel_rewalk", use_container_width=True):
            _rewalk_from_first_choice()
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)


def render():
    track_module_enter("平行宇宙")
    st.title("平行宇宙")
    st.write("请从侧边栏进入完整推演流程。")
