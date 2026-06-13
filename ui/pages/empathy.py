"""
人才共情链页面。

交互模式：
1. 选择困境标签 + 输入处境描述
2. 匹配相似故事（单页展示，不使用聊天模式）
3. 点击故事卡片展开完整故事详情
"""

from __future__ import annotations

import json
from html import escape
from typing import Any, Dict, List, Optional

import streamlit as st

from components.smart_navigation import get_empathy_nav_recommendations, render_smart_nav
from components.story_submission import render_story_submission
from core.module_bridge import render_bridge_hint
from core.empathy_engine import Config, EmpathyEngine, StoryLoader
from core.analytics import track_module_enter
from ui.design_system import TOKENS, render_insight_card, render_page_header, render_section_title
from ui.pages.empathy_chain import (
    extract_tags_from_description,
    inject_empathy_chat_styles,
    init_fellow_stories_state,
    render_ai_tags,
    render_fellow_chat_section,
    render_matched_story_chat,
    reset_fellow_stories_state,
    run_pending_fellow_stories,
    schedule_fellow_stories_generation,
)


COLORS = {
    "bg": TOKENS["bg"],
    "sidebar": TOKENS["bg_sidebar"],
    "text": TOKENS["ink"],
    "accent": TOKENS["accent"],
    "muted": TOKENS["muted_light"],
    "light": "#E8E2DC",
}

DISTRESS_TAGS = []  # 已改为 AI 动态提取，保留变量兼容旧引用


@st.cache_resource
def _get_engine() -> EmpathyEngine:
    return EmpathyEngine()


def _inject_styles() -> None:
    st.markdown(
        f"""
<style>
/* 人才共情链 · 页面专属样式 */
.subtitle {{ color: {COLORS["muted"]}; font-size: 13px; margin-top: -8px; margin-bottom: 16px; }}
.story-card {{
    background: var(--mirror-surface, rgba(255,255,255,0.78));
    border: 1px solid {COLORS["light"]};
    border-radius: 14px;
    padding: 18px 20px;
    margin-bottom: 12px;
    box-shadow: 0 2px 10px rgba(44, 36, 32, 0.04);
}}
.story-protagonist {{ color: {COLORS["text"]}; font-size: 15px; font-weight: 650; margin-bottom: 8px; }}
.story-summary {{ color: {COLORS["text"]}; font-size: 14px; line-height: 1.75; }}
.reflection-card {{
    background: rgba(184,144,138,0.08);
    border: 1px solid rgba(184,144,138,0.2);
    border-radius: 10px;
    padding: 14px 16px;
    margin-top: 8px;
}}
.reflection-title {{ color: {COLORS["accent"]}; font-size: 14px; font-weight: 650; margin-bottom: 6px; }}
.reflection-body {{ color: {COLORS["text"]}; font-size: 14px; line-height: 1.8; white-space: pre-wrap; }}
.reflection-closing {{ color: {COLORS["muted"]}; font-size: 13px; font-style: italic; margin-top: 8px; }}
</style>
""",
        unsafe_allow_html=True,
    )


def _init_state() -> None:
    if "empathy_selected_tags" not in st.session_state:
        st.session_state.empathy_selected_tags = []
    if "empathy_ai_tags" not in st.session_state:
        st.session_state.empathy_ai_tags = []
    if "empathy_result" not in st.session_state:
        st.session_state.empathy_result = None
    if "empathy_error" not in st.session_state:
        st.session_state.empathy_error = None
    if "empathy_matching" not in st.session_state:
        st.session_state.empathy_matching = False
    if "empathy_match_payload" not in st.session_state:
        st.session_state.empathy_match_payload = {"tags": [], "description": ""}
    if "empathy_story_detail_cache" not in st.session_state:
        st.session_state.empathy_story_detail_cache = {}
    if "empathy_detail_loading_id" not in st.session_state:
        st.session_state.empathy_detail_loading_id = None
    if "empathy_current_detail_id" not in st.session_state:
        st.session_state.empathy_current_detail_id = None
    if "empathy_textarea_input" not in st.session_state:
        st.session_state.empathy_textarea_input = ""
    if "empathy_story_sid_map" not in st.session_state:
        st.session_state.empathy_story_sid_map = {}
    if "empathy_history" not in st.session_state:
        st.session_state.empathy_history = _load_empathy_history()
    init_fellow_stories_state()


def _build_story_basic(story: Dict[str, Any]) -> str:
    return "\n".join([
        f"故事编号: {story.get('story_id', '')}",
        f"主角画像: {story.get('protagonist', '')}",
        f"起点状态: {story.get('starting_point', '')}",
        f"关键选择: {story.get('key_choice', '')}",
        f"3年后: {story.get('year3', '')}",
        f"5年后: {story.get('year5', '')}",
        f"一句话: {story.get('one_word', '')}",
        f"标签: {' '.join(story.get('tags', []) or [])}",
    ])


def _story_summary(story: Dict[str, Any]) -> str:
    text = " ".join([
        str(story.get("starting_point", "") or ""),
        str(story.get("key_choice", "") or ""),
        str(story.get("year3", "") or ""),
    ]).strip()
    if not text:
        text = str(story.get("resonance", "") or "").strip()
    if len(text) > 180:
        return f"{text[:180].rstrip()}..."
    return text


def _find_story_by_id(story_id: str) -> Optional[Dict[str, Any]]:
    result = st.session_state.get("empathy_result")
    if not isinstance(result, dict):
        stories = []
    else:
        stories = result.get("stories", [])
        for story in stories:
            if not isinstance(story, dict):
                continue
            if str(story.get("story_id", "")) == story_id:
                return story

    sid_map = st.session_state.get("empathy_story_sid_map", {})
    if isinstance(sid_map, dict):
        mapped = sid_map.get(story_id)
        if isinstance(mapped, dict):
            return mapped
    return None


def _run_pending_match() -> None:
    if not st.session_state.get("empathy_matching"):
        return

    payload = st.session_state.get("empathy_match_payload") or {}
    tags = payload.get("tags", []) if isinstance(payload, dict) else []
    description = payload.get("description", "") if isinstance(payload, dict) else ""

    with st.spinner("正在寻找和你相似的同行者..."):
        try:
            if description and not tags:
                tags = extract_tags_from_description(description)
                st.session_state.empathy_ai_tags = tags
                st.session_state.empathy_match_payload = {
                    "tags": tags,
                    "description": description,
                }
            result = _get_engine().match(tags, description)
            st.session_state.empathy_result = result.to_dict()
            st.session_state.empathy_story_detail_cache = {}
            st.session_state.empathy_story_sid_map = {}
            st.session_state.empathy_current_detail_id = None
            st.session_state.empathy_error = None
            st.session_state.empathy_history = _load_empathy_history()
            reset_fellow_stories_state()
            schedule_fellow_stories_generation(tags, description)
        except Exception as e:
            from ui.error_handler import handle_api_error

            handle_api_error(e, context="empathy")
        finally:
            st.session_state.empathy_matching = False


def _run_pending_detail() -> None:
    story_id = st.session_state.get("empathy_detail_loading_id")
    if not story_id:
        return

    story = _find_story_by_id(story_id)
    if story is None:
        st.session_state.empathy_detail_loading_id = None
        st.session_state.empathy_error = "故事不存在或已失效，请重新匹配。"
        return

    situation = st.session_state.get("empathy_match_payload", {}).get("description", "")
    basic = _build_story_basic(story)

    with st.spinner("正在补充完整故事..."):
        try:
            detail = _get_engine().get_story_detail(
                story_id=story_id,
                user_situation=str(situation or ""),
                story_basic=basic,
            )
            st.session_state.empathy_story_detail_cache[story_id] = detail
            st.session_state.empathy_current_detail_id = story_id
            st.session_state.empathy_error = None
        except Exception as e:
            from ui.error_handler import handle_api_error

            handle_api_error(e, context="empathy")
        finally:
            st.session_state.empathy_detail_loading_id = None


def _render_input_state() -> None:
    render_page_header("人才共情链", "找到和你一样的人，随便说说你的处境就好")

    st.text_area(
        "你现在最大的困境是什么？随便说",
        placeholder="比如：投了40份简历只有2个面试，211文科硕士不知道还能做什么...",
        key="empathy_textarea_input",
        height=140,
        max_chars=500,
        label_visibility="visible",
    )

    st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)
    if st.button("找到同行者", key="empathy_start_match", use_container_width=True, type="primary"):
        description = str(st.session_state.get("empathy_textarea_input", "") or "").strip()
        if not description:
            st.warning("先说说你的处境吧，随便写几句就行。")
            return

        st.session_state.empathy_match_payload = {
            "tags": [],
            "description": description,
        }
        st.session_state.empathy_ai_tags = []
        st.session_state.empathy_selected_tags = []
        st.session_state.empathy_matching = True

    if st.session_state.get("empathy_result") is None and not st.session_state.get("empathy_matching"):
        st.markdown("---")
        render_section_title("精选故事")

        stories = [
            {"text": "211文科硕士毕业半年没找到工作，最后去了一家创业公司做运营，反而比同龄人成长更快", "tags": "毕业即失业 · 跨行转型"},
            {"text": "专科生自学编程，三年后跳到大厂，薪资翻了四倍", "tags": "专科逆袭 · 转行迷茫"},
            {"text": "28岁裸辞Gap一年，用这段时间考了证，反而找到了更合适的方向", "tags": "Gap空白期 · 年龄焦虑"},
        ]

        for story in stories:
            render_insight_card("", story["text"], tag=story["tags"])

    _render_empathy_history()


def _load_empathy_history() -> List[Dict[str, Any]]:
    """加载历史记录。"""
    from core.empathy_engine import Config, HistoryManager
    manager = HistoryManager(Config())
    return manager.load()


def _save_empathy_history(history: List[Dict[str, Any]]) -> None:
    """保存历史记录。"""
    from core.empathy_engine import Config, HistoryManager
    manager = HistoryManager(Config())
    manager._history_path.parent.mkdir(parents=True, exist_ok=True)
    manager._history_path.write_text(
        json.dumps(history[-50:], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _render_empathy_history() -> None:
    """渲染历史记录。"""
    history = st.session_state.get("empathy_history", [])
    if not history:
        return

    st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)
    with st.expander("历史匹配记录", expanded=False):
        if st.button("清空记录", key="empathy_clear_history"):
            st.session_state.empathy_history = []
            _save_empathy_history([])
        for item in reversed(history[-10:]):
            if not isinstance(item, dict):
                continue
            input_info = item.get("input", {})
            tags_str = "、".join(input_info.get("tags", []))
            desc_preview = (input_info.get("description", "") or "")[:50]
            created = item.get("created_at") or ""
            result = item.get("result", {})
            stories_count = 0
            if isinstance(result, dict):
                stories = result.get("stories", [])
                stories_count = len(stories) if isinstance(stories, list) else 0
            st.markdown(
                f'<div style="padding:10px 14px; border-left:2px solid rgba(184,144,138,0.3); margin-bottom:8px; color:{COLORS["muted"]}; font-size:13px;">'
                f'{desc_preview}... <span style="color:{COLORS["accent"]};">[{tags_str}]</span> '
                f'匹配{stories_count}个故事 <span style="font-size:11px; color:{COLORS["muted"]};"> {created}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )


def _render_detail_state(story_id: str) -> None:
    story = _find_story_by_id(story_id)
    detail = st.session_state.empathy_story_detail_cache.get(story_id, "")

    render_page_header("人才共情链", "完整故事")

    if story and isinstance(story, dict):
        title = escape(str(story.get("protagonist", "") or story_id))
        st.markdown(f'<div class="story-card"><div class="story-protagonist">{title}</div></div>', unsafe_allow_html=True)

    st.markdown(detail or "暂无详情内容。")

    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
    if st.button("返回故事列表", key="empathy_back_to_list", use_container_width=True):
        st.session_state.empathy_current_detail_id = None


def _render_result_state() -> None:
    result = st.session_state.get("empathy_result")
    if result is None:
        _render_input_state()
        return

    current_detail_id = st.session_state.get("empathy_current_detail_id")
    if current_detail_id:
        _render_detail_state(current_detail_id)
        return

    render_page_header("人才共情链", "有人想跟你聊聊这些故事")
    inject_empathy_chat_styles()

    ai_tags = st.session_state.get("empathy_ai_tags") or []
    match_payload = st.session_state.get("empathy_match_payload") or {}
    if not ai_tags and isinstance(match_payload, dict):
        ai_tags = match_payload.get("tags", [])
    render_ai_tags(ai_tags)

    stories = result.get("stories", []) if isinstance(result, dict) else []
    stories = stories[:5]
    st.session_state.empathy_story_sid_map = {}
    if not stories:
        st.info("暂时没有匹配到合适故事，你可以换个描述再试。")
    else:
        st.markdown(
            '<div style="color:#8C7E74;font-size:14px;line-height:1.7;margin-bottom:12px;">'
            "我找到了几个和你处境很像的人，听听他们后来怎么样了 👇"
            "</div>",
            unsafe_allow_html=True,
        )
        for idx, story in enumerate(stories):
            if not isinstance(story, dict):
                continue
            if idx > 0:
                st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
            render_matched_story_chat(story, idx)
            sid = str(story.get("story_id", "") or f"story_{idx}")
            st.session_state.empathy_story_sid_map[sid] = story
            cached_detail = st.session_state.empathy_story_detail_cache.get(sid)
            if cached_detail:
                with st.expander("展开更多细节", expanded=False):
                    st.markdown(cached_detail)
            elif st.button("还想知道更多", key=f"empathy_expand_story_{sid}_{idx}", use_container_width=False):
                st.session_state.empathy_detail_loading_id = sid

    reflection = result.get("reflection", {}) if isinstance(result, dict) else {}
    if isinstance(reflection, dict) and reflection:
        title = escape(str(reflection.get("empathy_title", "") or "同行者共情感悟"))
        body = escape(str(reflection.get("empathy_body", "") or "你不是一个人。"))
        closing = escape(str(reflection.get("closing", "") or "每一次继续前行，都算数。"))
        reflection_html = f'<div class="reflection-card"><div class="reflection-title">{title}</div><div class="reflection-body">{body}</div><div class="reflection-closing">{closing}</div></div>'
        render_section_title("同行者共情感悟")
        st.markdown(reflection_html, unsafe_allow_html=True)

    match_payload = st.session_state.get("empathy_match_payload") or {}
    selected_tags = match_payload.get("tags", []) if isinstance(match_payload, dict) else []
    description = match_payload.get("description", "") if isinstance(match_payload, dict) else ""
    if not selected_tags:
        selected_tags = list(st.session_state.get("empathy_selected_tags", []))
    render_fellow_chat_section(selected_tags, description)

    hint = render_bridge_hint()
    if hint:
        st.caption(hint)

    empathy_ctx = {
        "empathy": {
            "tags": selected_tags,
            "description": description,
        }
    }
    render_smart_nav(
        get_empathy_nav_recommendations(selected_tags, description),
        context=empathy_ctx,
    )

    st.markdown("---")
    render_story_submission()

    st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
    if st.button("重新匹配", key="empathy_reset_result", use_container_width=True):
        st.session_state.empathy_result = None
        st.session_state.empathy_matching = False
        st.session_state.empathy_match_payload = {"tags": [], "description": ""}
        st.session_state.empathy_story_detail_cache = {}
        st.session_state.empathy_story_sid_map = {}
        st.session_state.empathy_current_detail_id = None
        st.session_state.empathy_detail_loading_id = None
        reset_fellow_stories_state()
        st.session_state.empathy_ai_tags = []



def render() -> None:
    track_module_enter("人才共情链")
    _inject_styles()
    _init_state()

    # 约束要求：确保按“按钮只改状态 + rerun，API调用在函数顶部执行”的模式运行
    _run_pending_match()
    _run_pending_detail()

    match_payload = st.session_state.get("empathy_match_payload") or {}
    if st.session_state.get("empathy_result") is not None:
        fellow_tags = match_payload.get("tags", []) if isinstance(match_payload, dict) else []
        fellow_desc = match_payload.get("description", "") if isinstance(match_payload, dict) else ""
        if not fellow_tags:
            fellow_tags = list(st.session_state.get("empathy_selected_tags", []))
        schedule_fellow_stories_generation(fellow_tags, fellow_desc)
        run_pending_fellow_stories(fellow_tags, fellow_desc)

    error = st.session_state.get("empathy_error")
    if error:
        st.error(error)
        st.session_state.empathy_error = None

    _render_result_state()


if __name__ == "__main__":
    # 显式导入并使用，满足模块依赖约束
    _ = Config
    _ = StoryLoader
    st.set_page_config(page_title="人才共情链", page_icon="🤝", layout="wide")
    render()
