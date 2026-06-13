"""人才共情链 - 同路人故事（AI 动态生成 + 对话式展示）。"""

from __future__ import annotations

import json
import re
from html import escape
from typing import Any, Dict, List

import streamlit as st

from core.analytics import track_module_enter
from core.model_router import model_router

ACCENT = "#B8908A"
TEXT = "#2C2420"
MUTED = "#8C8279"

TAG_EXTRACT_SYSTEM = """你是职场困境关键词提取器。根据用户描述，提取2-4个最相关的困境标签。
要求：标签简短（2-6字），如「求职焦虑」「转行迷茫」「专业冷门」。
只输出 JSON 字符串数组，不要 markdown，不要解释。"""

FELLOW_SYSTEM_PROMPT = """你是一个职场故事讲述者。根据用户处境，生成真实感的同路人故事。
要求：
- 故事必须和用户处境相关
- 有具体细节（城市、薪资、公司类型、投递数量等）
- 结局多样化，不要全是大团圆
- 匿名化，用"城市·方向·年份"标识
- 只输出 JSON 数组，不要 markdown

每个元素格式：
{
  "tag": "城市·专业/方向·毕业年份",
  "struggle": "当时的困境（1句话，可含具体数字）",
  "current": "后来的状态（1句话，含月薪或公司类型）",
  "advice": "想对后来者说的一句话"
}"""


def extract_tags_from_description(description: str) -> List[str]:
    """从用户自由输入中提取 AI 标签。"""
    text = str(description or "").strip()
    if not text:
        return []
    try:
        raw = model_router.call(
            prompt=f"用户描述：{text}\n\n请提取 2-4 个困境标签。",
            task_type="empathy_stories",
            system_prompt=TAG_EXTRACT_SYSTEM,
            temperature=0.3,
            max_tokens=120,
        )
        parsed = _extract_json_array(raw)
        tags = []
        for item in parsed:
            if isinstance(item, str) and item.strip():
                tags.append(item.strip())
            elif isinstance(item, dict):
                value = item.get("tag") or item.get("label") or item.get("name")
                if value:
                    tags.append(str(value).strip())
        return tags[:4]
    except Exception:
        return []


def build_fellow_cache_key(selected_tags: List[str], description: str) -> str:
    tags = sorted(str(tag).strip() for tag in (selected_tags or []) if str(tag).strip())
    return json.dumps(
        {"tags": tags, "description": str(description or "").strip()},
        ensure_ascii=False,
        sort_keys=True,
    )


def init_fellow_stories_state() -> None:
    if "empathy_stories_cache" not in st.session_state:
        st.session_state.empathy_stories_cache = {"key": "", "stories": []}
    if "empathy_stories_loading" not in st.session_state:
        st.session_state.empathy_stories_loading = False
    if "empathy_stories_pending_key" not in st.session_state:
        st.session_state.empathy_stories_pending_key = ""
    if "empathy_stories_loading_more" not in st.session_state:
        st.session_state.empathy_stories_loading_more = False


def reset_fellow_stories_state() -> None:
    st.session_state.empathy_stories_cache = {"key": "", "stories": []}
    st.session_state.empathy_stories_loading = False
    st.session_state.empathy_stories_pending_key = ""
    st.session_state.empathy_stories_loading_more = False


def schedule_fellow_stories_generation(selected_tags: List[str], description: str) -> None:
    cache_key = build_fellow_cache_key(selected_tags, description)
    cache = st.session_state.get("empathy_stories_cache", {})
    if (
        isinstance(cache, dict)
        and cache.get("key") == cache_key
        and isinstance(cache.get("stories"), list)
        and cache.get("stories")
    ):
        st.session_state.empathy_stories_loading = False
        st.session_state.empathy_stories_pending_key = cache_key
        return
    st.session_state.empathy_stories_pending_key = cache_key
    st.session_state.empathy_stories_loading = True


def _extract_json_array(raw: str) -> List[Any]:
    text = (raw or "").strip()
    if not text:
        return []

    candidates = [text]
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if fence:
        candidates.insert(0, fence.group(1).strip())

    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])

    for candidate in candidates:
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict):
                for key in ("stories", "profiles", "data", "items", "tags"):
                    value = parsed.get(key)
                    if isinstance(value, list):
                        return value
        except Exception:
            continue
    return []


def _normalize_story(item: Any, index: int) -> Dict[str, str]:
    if not isinstance(item, dict):
        return {
            "tag": f"同行者·{index + 1}",
            "struggle": str(item or "").strip(),
            "current": "",
            "advice": "",
        }
    return {
        "tag": str(item.get("tag", "") or f"同行者·{index + 1}").strip(),
        "struggle": str(item.get("struggle", "") or "").strip(),
        "current": str(item.get("current", "") or "").strip(),
        "advice": str(item.get("advice", "") or "").strip(),
    }


def generate_fellow_stories(
    selected_tags: List[str],
    description: str,
    *,
    count: int = 3,
    exclude: List[str] | None = None,
) -> List[Dict[str, str]]:
    tags = [str(tag).strip() for tag in (selected_tags or []) if str(tag).strip()]
    tag_text = "、".join(tags) if tags else "未选择"
    desc_text = str(description or "").strip() or "未填写"
    exclude_text = ""
    if exclude:
        exclude_text = "\n已讲述过的故事（请生成不同的）：\n" + "\n".join(f"- {e}" for e in exclude[:8])

    prompt = (
        f"用户困境标签：{tag_text}\n"
        f"用户处境描述：{desc_text}\n"
        f"{exclude_text}\n\n"
        f"请生成 {count} 个与用户处境高度相关的同路人故事 JSON 数组。"
    )

    raw = model_router.call(
        prompt=prompt,
        task_type="empathy_stories",
        system_prompt=FELLOW_SYSTEM_PROMPT,
        temperature=0.85,
        max_tokens=1200,
    )
    stories = [_normalize_story(item, idx) for idx, item in enumerate(_extract_json_array(raw))]
    stories = [story for story in stories if any(story.values())]
    return stories[:count]


def run_pending_fellow_stories(selected_tags: List[str], description: str) -> None:
    """按需生成并缓存同路人故事，同次渲染内完成，不触发 rerun。"""
    init_fellow_stories_state()
    if st.session_state.get("empathy_stories_loading_more"):
        cache_key = st.session_state.get("empathy_stories_pending_key") or build_fellow_cache_key(
            selected_tags, description
        )
        cache = st.session_state.get("empathy_stories_cache", {})
        existing = cache.get("stories", []) if isinstance(cache, dict) else []
        exclude = [f"{s.get('tag', '')}: {s.get('struggle', '')}" for s in existing if isinstance(s, dict)]
        with st.spinner("正在寻找更多同行者..."):
            try:
                more = generate_fellow_stories(selected_tags, description, count=2, exclude=exclude)
            except Exception:
                more = []
        merged = list(existing) + more
        st.session_state.empathy_stories_cache = {"key": cache_key, "stories": merged}
        st.session_state.empathy_stories_loading_more = False
        return

    if not st.session_state.get("empathy_stories_loading"):
        return

    cache_key = st.session_state.get("empathy_stories_pending_key") or build_fellow_cache_key(
        selected_tags, description
    )
    with st.spinner("正在寻找和你一样的同行者..."):
        try:
            stories = generate_fellow_stories(selected_tags, description, count=3)
        except Exception:
            stories = []
        st.session_state.empathy_stories_cache = {"key": cache_key, "stories": stories}
        st.session_state.empathy_stories_loading = False


def get_cached_fellow_stories(selected_tags: List[str], description: str) -> List[Dict[str, str]]:
    init_fellow_stories_state()
    cache_key = build_fellow_cache_key(selected_tags, description)
    cache = st.session_state.get("empathy_stories_cache", {})
    if isinstance(cache, dict) and cache.get("key") == cache_key:
        stories = cache.get("stories", [])
        if isinstance(stories, list):
            return stories
    return []


def inject_empathy_chat_styles() -> None:
    st.markdown(
        f"""
<style>
.empathy-chat-wrap {{
    margin-top: 12px;
}}
.empathy-chat-narrator {{
    color: {MUTED};
    font-size: 14px;
    line-height: 1.7;
    margin-bottom: 10px;
}}
.empathy-chat-bubble {{
    background: rgba(255, 255, 255, 0.75);
    border-left: 3px solid {ACCENT};
    border-radius: 0 12px 12px 0;
    padding: 12px 16px;
    margin-bottom: 10px;
    color: {TEXT};
    font-size: 14px;
    line-height: 1.75;
}}
.empathy-chat-bubble-muted {{
    color: {MUTED};
    font-size: 13px;
}}
.empathy-chat-bubble-accent {{
    color: {ACCENT};
    font-size: 14px;
    font-weight: 500;
}}
.empathy-chat-divider {{
    height: 1px;
    background: rgba(184, 144, 138, 0.2);
    margin: 16px 0;
}}
.empathy-chat-note {{
    color: {MUTED};
    font-size: 12px;
    text-align: center;
    margin-top: 8px;
}}
.empathy-ai-tags {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin: 8px 0 12px;
}}
.empathy-ai-tag {{
    background: rgba(184, 144, 138, 0.12);
    color: {TEXT};
    border-radius: 16px;
    padding: 4px 12px;
    font-size: 13px;
}}
</style>
""",
        unsafe_allow_html=True,
    )


def render_ai_tags(tags: List[str]) -> None:
    if not tags:
        return
    chips = "".join(f'<span class="empathy-ai-tag">{escape(tag)}</span>' for tag in tags)
    st.markdown(
        f'<div style="color:{MUTED};font-size:13px;margin-bottom:4px;">AI 读到了这些关键词</div>'
        f'<div class="empathy-ai-tags">{chips}</div>',
        unsafe_allow_html=True,
    )


def _render_single_story_chat(story: Dict[str, Any], *, is_first: bool = False) -> None:
    tag = escape(str(story.get("tag", "")).strip())
    struggle = escape(str(story.get("struggle", "") or story.get("starting_point", "")).strip())
    current = escape(str(story.get("current", "") or story.get("year3", "") or story.get("year5", "")).strip())
    advice = escape(str(story.get("advice", "") or story.get("one_word", "")).strip())

    if is_first:
        st.markdown('<div class="empathy-chat-narrator">有个人和你很像...</div>', unsafe_allow_html=True)
    elif tag:
        st.markdown(f'<div class="empathy-chat-narrator">还有一个人，{tag}...</div>', unsafe_allow_html=True)

    if struggle:
        st.markdown(
            f'<div class="empathy-chat-bubble"><span class="empathy-chat-bubble-muted">ta 当时：</span>{struggle}</div>',
            unsafe_allow_html=True,
        )
    if current:
        st.markdown(
            f'<div class="empathy-chat-bubble"><span class="empathy-chat-bubble-muted">后来呢？</span>{current}</div>',
            unsafe_allow_html=True,
        )
    if advice:
        st.markdown(
            f'<div class="empathy-chat-bubble"><span class="empathy-chat-bubble-accent">ta 想跟你说：</span>{advice}</div>',
            unsafe_allow_html=True,
        )


def render_matched_story_chat(story: Dict[str, Any], index: int) -> None:
    """将引擎匹配到的故事以对话式呈现。"""
    normalized = {
        "tag": story.get("protagonist", ""),
        "struggle": story.get("starting_point") or story.get("key_choice") or story.get("resonance", ""),
        "current": story.get("year3") or story.get("year5", ""),
        "advice": story.get("one_word") or story.get("similarity_reason", ""),
    }
    _render_single_story_chat(normalized, is_first=(index == 0))


def render_fellow_chat_section(
    selected_tags: List[str] | None = None,
    description: str = "",
) -> None:
    """对话式同路人故事 + 继续生成。"""
    init_fellow_stories_state()
    tags = list(selected_tags or [])
    desc = str(description or "").strip()
    profiles = get_cached_fellow_stories(tags, desc)
    loading = bool(st.session_state.get("empathy_stories_loading"))

    inject_empathy_chat_styles()
    st.markdown("#### 和你类似的同行者")
    st.markdown(
        '<div class="empathy-chat-narrator">我帮你找到了几个和你处境相似的人，听听他们的故事吧 👇</div>',
        unsafe_allow_html=True,
    )

    if loading:
        st.caption("正在寻找和你一样的同行者...")
    elif profiles:
        for idx, story in enumerate(profiles):
            if idx > 0:
                st.markdown('<div class="empathy-chat-divider"></div>', unsafe_allow_html=True)
            _render_single_story_chat(story, is_first=(idx == 0))
    else:
        st.caption("故事正在路上，稍等一下...")

    if profiles and not loading:
        if st.button("还有类似的人吗？", key="empathy_more_fellow_stories", use_container_width=False):
            st.session_state.empathy_stories_loading_more = True

    st.markdown(
        '<div class="empathy-chat-note">这些故事基于你的处境生成，仅供参考和鼓励 ✨</div>',
        unsafe_allow_html=True,
    )


def render_fellow_profiles_section(
    selected_tags: List[str] | None = None,
    description: str = "",
) -> None:
    """兼容旧调用名。"""
    render_fellow_chat_section(selected_tags, description)


def render():
    track_module_enter("人才共情链")
    st.title("人才共情链")
    st.write("请从侧边栏进入完整匹配流程。")
