"""
情绪急救站 - 支持单轮问答与连续对话两种模式

单轮模式：说一次 → 看回复 → 再来一次
连续模式：多轮对话，保留上下文记忆
"""

from datetime import datetime
from html import escape
import logging
from pathlib import Path

import streamlit as st

from agents.emotion.service import get_emotion_service
from agents.emotion.parse_utils import extract_natural_response
from core.privacy_filter import sanitize_chat_for_api
from core.session_manager import SessionManager
from core.analytics import track_emotion_score, track_module_enter
from ui.error_handler import handle_api_error
from ui.design_system import render_page_header, render_section_title
from ui.emotion_theme import apply_emotion_breath
from ui.sidebar import navigate_to_page
from components.emotion_diary import render_emotion_diary
from components.smart_navigation import get_emotion_nav_recommendations, render_smart_nav
from components.empathy_reasoning import render_empathy_reasoning_expander
from utils.emotion_adapter import EmotionAdapter, normalize_emotion_state, emotion_from_score, sync_emotion_to_session
from core.config import get_settings
from utils.emotion_instant import infer_emotion_from_text, pick_instant_reply, is_low_quality_ai_reply

logger = logging.getLogger(__name__)


# ===== 持久化 =====

def _history_file() -> Path:
    return SessionManager.user_file_path("emotion", "history.json")


def _load_history():
    try:
        history_path = _history_file()
        if history_path.exists():
            import json
            data = json.loads(history_path.read_text("utf-8"))
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


def _save_history(history):
    import json
    history_path = _history_file()
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(
        json.dumps(history[-50:], ensure_ascii=False, indent=2), "utf-8"
    )


# ===== 情绪服务 =====

def _get_emotion_service():
    if "emotion_session_id" not in st.session_state:
        st.session_state.emotion_session_id = f"emotion_{SessionManager.get_user_id()}"
    return get_emotion_service(st.session_state.emotion_session_id)


def _llm_available() -> bool:
    settings = get_settings()
    return bool(settings.deepseek_api_key or settings.zhipu_api_key)


def _append_chat_history(user_input: str, reply: str) -> None:
    now = datetime.now().strftime("%H:%M")
    st.session_state.emotion_chat_history.append(
        {"input": user_input, "reply": reply, "time": now}
    )
    _save_history(st.session_state.emotion_chat_history)


def _append_to_continuous_thread(user_text: str, reply: str) -> None:
    if st.session_state.get("emotion_chat_mode") != "continuous":
        return
    thread = list(st.session_state.get("emotion_continuous_thread") or [])
    thread.append({"role": "user", "content": user_text})
    thread.append({"role": "assistant", "content": reply})
    st.session_state.emotion_continuous_thread = thread[-12:]


def _run_emotion_response(user_text: str, emotion_start_score: int) -> None:
    """后台 AI 增强：即时回复已在上一帧展示，此处仅尝试替换为更贴切的 AI 文案。"""
    service = _get_emotion_service()
    emotion = infer_emotion_from_text(user_text)
    instant_fallback = st.session_state.emotion_current_reply or pick_instant_reply(
        emotion, emotion_start_score
    )
    final_reply = instant_fallback
    reasoning_chain: dict = {}

    history_for_api: list[dict[str, str]] = []
    if st.session_state.get("emotion_chat_mode") == "continuous":
        history_for_api = list(st.session_state.get("emotion_continuous_thread") or [])

    try:
        with st.spinner("小镜在想怎么回应你…"):
            result = service.fast_respond(
                user_text,
                emotion_hint=emotion,
                emotion_start_score=emotion_start_score,
                conversation_history=history_for_api or None,
            )
        ai_reply = extract_natural_response(result["response"]["content"])
        reasoning_chain = result.get("reasoning_chain") or {}
        if ai_reply.strip() and not is_low_quality_ai_reply(user_text, ai_reply):
            final_reply = ai_reply.strip()
        elif ai_reply.strip():
            logger.info("[emotion] AI reply too echo-like, keeping instant reply")
    except Exception as exc:
        logger.warning("[emotion] fast_respond failed, keeping instant reply: %s", exc)
    finally:
        st.session_state.emotion_current_reply = final_reply
        st.session_state.emotion_reasoning_chain = reasoning_chain
        st.session_state.emotion_ai_pending = False
        st.session_state.emotion_streaming = False
        _append_chat_history(user_text, final_reply)
        _append_to_continuous_thread(user_text, final_reply)


# ===== 样式 =====

def _inject_styles():
    st.markdown(
        """
<style>
/* 情绪急救站 · 页面专属样式 */
[data-testid="stMainBlockContainer"] {
    padding-top: 8px !important;
    padding-bottom: 8px !important;
}

/* 情绪标签按钮 */
[class^="st-key-emotion_tag_"] button {
    background: rgba(184,144,138,0.1) !important;
    color: #6B5B52 !important;
    border: 1px solid rgba(184,144,138,0.25) !important;
    border-radius: 20px !important;
}
[class^="st-key-emotion_tag_"] button:hover {
    background: rgba(184,144,138,0.2) !important;
    font-weight: 700 !important;
}

/* 说出来按钮（深色强调） */
.st-key-emotion_submit button[kind="secondary"] {
    background-color: #B8908A !important;
    color: #FFF !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
}
.st-key-emotion_submit button[kind="secondary"]:hover {
    background-color: #A07A74 !important;
}

/* 再来一次按钮（浅色版） */
.st-key-emotion_again button {
    background: rgba(184,144,138,0.12) !important;
    color: #6B5B52 !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
}
.st-key-emotion_again button:hover {
    background: rgba(184,144,138,0.2) !important;
}

/* 点赞反馈 & 智能跳转按钮 */
[class*="st-key-smart_nav_"] button,
.st-key-emotion_feedback_up button {
    background: rgba(184,144,138,0.14) !important;
    color: #5C4F47 !important;
    border: 1px solid rgba(184,144,138,0.28) !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
}
[class*="st-key-smart_nav_"] button:hover,
.st-key-emotion_feedback_up button:hover {
    background: rgba(184,144,138,0.22) !important;
    color: #2C2420 !important;
    border-color: rgba(184,144,138,0.4) !important;
}

/* 输入框 */
div[data-testid="stTextArea"] textarea {
    border-color: rgba(184,144,138,0.3) !important;
}
div[data-testid="stTextArea"] textarea:focus {
    border-color: #B8908A !important;
    box-shadow: 0 0 0 1px rgba(184,144,138,0.2) !important;
}

/* 倾诉记录 expander */
[data-testid="stExpander"] summary,
[data-testid="stExpander"] summary p {
    color: #8C8279 !important;
}
[data-testid="stExpander"] summary svg {
    fill: #8C8279 !important;
    color: #8C8279 !important;
}

/* 回复卡片 */
.emotion-reply {
    border-left: 3px solid #B8908A;
    padding: 20px 24px;
    color: #2C2420;
    line-height: 2;
    font-size: 15px;
    background: rgba(184,144,138,0.04);
    border-radius: 0 12px 12px 0;
}

/* 用户说的话 */
.emotion-user-words {
    background: rgba(184,144,138,0.12);
    border-radius: 14px;
    padding: 14px 18px;
    color: #2C2420;
    line-height: 1.75;
    font-size: 14px;
    margin-bottom: 16px;
    margin-left: auto;
}

/* 历史条目 */
.history-item {
    padding: 10px 14px;
    border-left: 2px solid rgba(184,144,138,0.3);
    margin-bottom: 8px;
    color: #8C8279;
    font-size: 13px;
    line-height: 1.6;
}
.history-time {
    color: #9E8E83;
    font-size: 11px;
}

/* 情绪温度计 slider */
.stSlider [data-baseweb="slider"] > div > div {
    background: linear-gradient(to right, #E8D5CF, #B8908A) !important;
}
.stSlider [data-baseweb="thumb"] {
    background-color: #B8908A !important;
    border-color: #B8908A !important;
}
.stSlider [data-baseweb="slider"] [role="slider"] {
    background-color: #B8908A !important;
}
</style>
""",
        unsafe_allow_html=True,
    )


# ===== 情绪标签 =====

EMOTION_TAGS = [
    ("焦虑", "我最近总是很焦虑，睡不着觉..."),
    ("委屈", "我觉得自己被不公平对待了..."),
    ("挫败", "试了好多次还是失败了，想放弃了..."),
    ("迷茫", "不知道自己该做什么，感觉很迷茫..."),
    ("说不清", "我说不上来什么感觉，就是很难受..."),
]


def _emotion_hint(score: int) -> str:
    if score <= 3:
        return "🫂 有点低落，想聊聊吗？"
    if score <= 5:
        return "还行，有点焦虑？说说看"
    if score <= 7:
        return "还不错，有想聊的随时说"
    return "状态不错！🎉 但我随时在"


def _delta_feedback(start: int, end: int) -> str:
    delta = end - start
    if delta >= 2:
        return f"你的状态好了不少，从{start}度到{end}度，每一度都算数 🌱"
    if delta == 1:
        return "稍微好了一点点，这也是进步 💪"
    if delta == 0:
        return "没关系，有时候能维持住就已经很棒了 🫂"
    return "如果还是很不好，可以明天再来，我一直在这里 🤍"


def _format_delta_arrow(delta: int) -> str:
    if delta > 0:
        return f"↑{delta}"
    if delta < 0:
        return f"↓{abs(delta)}"
    return "→0"


def _maybe_record_emotion_delta() -> None:
    start = st.session_state.get("emotion_start_score")
    end = st.session_state.get("emotion_end_score")
    if start is None or end is None:
        return

    delta = end - start
    history = st.session_state.emotion_history
    if history:
        last = history[-1]
        if last.get("start_score") == start and last.get("end_score") == end:
            return

    history.append(
        {
            "start_score": start,
            "end_score": end,
            "delta": delta,
            "timestamp": datetime.now().isoformat(),
        }
    )
    track_emotion_score(int(start), int(end))


def _on_emotion_start_change() -> None:
    st.session_state.emotion_start_touched = True
    st.session_state.emotion_start_score = st.session_state.emotion_start_slider
    sync_emotion_to_session()


def _render_emotion_thermometer(label: str, state_key: str, widget_key: str) -> int:
    if state_key == "emotion_start_score" and "emotion_start_touched" not in st.session_state:
        st.session_state.emotion_start_touched = False

    raw = st.session_state.get(state_key)
    on_change = _on_emotion_start_change if state_key == "emotion_start_score" else None
    score = st.slider(
        label,
        min_value=1,
        max_value=10,
        value=int(raw if raw is not None else 5),
        key=widget_key,
        on_change=on_change,
    )
    st.session_state[state_key] = score
    st.markdown(
        f'<div style="color:#8C8279;font-size:13px;margin-top:-8px;margin-bottom:12px;">{_emotion_hint(score)}</div>',
        unsafe_allow_html=True,
    )
    return score


def _format_history_line(entry: dict) -> str:
    ts_raw = entry.get("timestamp", "")
    try:
        ts = datetime.fromisoformat(ts_raw)
        time_label = f"{ts.month}月{ts.day}日 {ts.strftime('%H:%M')}"
    except (TypeError, ValueError):
        time_label = ts_raw or "—"
    start = entry.get("start_score", "?")
    end = entry.get("end_score", "?")
    arrow = _format_delta_arrow(entry.get("delta", 0))
    return f"{time_label} | {start}度→{end}度 {arrow}"


def _reset_emotion_turn() -> None:
    """结束当前轮，恢复输入区（连续模式下保留对话线程）。"""
    st.session_state.emotion_show_result = False
    st.session_state.emotion_current_reply = ""
    st.session_state.emotion_current_input = ""
    st.session_state.emotion_selected_tag = ""
    st.session_state.emotion_selected_idx = -1
    st.session_state.emotion_streaming = False
    st.session_state.emotion_ai_pending = False
    st.session_state.emotion_reasoning_chain = {}
    for key in ("emotion_text_area",):
        st.session_state.pop(key, None)


def _reset_emotion_conversation() -> None:
    """完全重置对话，清空历史与温度计。"""
    _reset_emotion_turn()
    st.session_state.chat_started = False
    st.session_state.emotion_start_score = None
    st.session_state.emotion_end_score = None
    st.session_state.emotion_start_touched = False
    st.session_state.emotion_chat_history = []
    st.session_state.emotion_continuous_thread = []
    _save_history([])
    for key in ("emotion_start_slider", "emotion_end_slider"):
        st.session_state.pop(key, None)


def _infer_emotion_state() -> str:
    """从标签、输入或温度计推断情绪状态。"""
    tag = (st.session_state.get("emotion_selected_tag") or "").strip()
    if tag:
        return normalize_emotion_state(tag)

    text = (st.session_state.get("emotion_current_input") or "").strip()
    if text:
        normalized = normalize_emotion_state(text)
        if normalized != EmotionAdapter.CALM or any(
            k in text for k in ("焦虑", "挫败", "委屈", "迷茫")
        ):
            return normalized

    score = st.session_state.get("emotion_start_score")
    if score is not None and st.session_state.get("emotion_start_touched"):
        try:
            return emotion_from_score(int(score))
        except (TypeError, ValueError):
            pass

    return EmotionAdapter.CALM


def _render_action_guidance() -> None:
    reasoning = st.session_state.get("emotion_reasoning_chain") or {}
    render_empathy_reasoning_expander(reasoning)

    col_up, col_spacer = st.columns([1, 3])
    with col_up:
        if st.button("👍 这个回应有帮助", key="emotion_feedback_up", use_container_width=True):
            service = _get_emotion_service()
            ok = service.record_positive_feedback(
                user_input=st.session_state.get("emotion_current_input", ""),
                assistant_output=st.session_state.get("emotion_current_reply", ""),
                emotion_type=_infer_emotion_state(),
            )
            if ok:
                st.toast("已记录，小镜会从这次对话中学习 ✨", icon="💙")
            else:
                st.toast("感谢反馈！", icon="💙")

    emotion = _infer_emotion_state()
    render_smart_nav(
        get_emotion_nav_recommendations(emotion),
        context={
            "emotion_state": emotion,
            "summary": (st.session_state.get("emotion_current_input") or "")[:200],
        },
    )


def _render_restart_button() -> None:
    continuous = st.session_state.get("emotion_chat_mode") == "continuous"
    if continuous:
        col_continue, col_end = st.columns(2)
        with col_continue:
            if st.button("💬 继续说说", key="emotion_continue", use_container_width=True, type="primary"):
                _reset_emotion_turn()
                st.rerun()
        with col_end:
            if st.button("🔄 结束本次对话", key="emotion_again", use_container_width=True):
                _reset_emotion_conversation()
                st.rerun()
    else:
        if st.button("🔄 再来一次", key="emotion_again", use_container_width=True):
            _reset_emotion_conversation()
            st.rerun()


def _render_continuous_thread() -> None:
    """连续模式下展示已有对话线程。"""
    thread = st.session_state.get("emotion_continuous_thread") or []
    if len(thread) < 2:
        return
    st.markdown(
        '<div style="color:#8C8279;font-size:13px;font-weight:600;margin:12px 0 8px;">本次对话</div>',
        unsafe_allow_html=True,
    )
    for turn in thread[:-2]:
        role = turn.get("role", "")
        content = escape(turn.get("content", "")).replace("\n", "<br>")
        if role == "user":
            st.markdown(f'<div class="emotion-user-words">{content}</div>', unsafe_allow_html=True)
        elif role == "assistant":
            st.markdown(f'<div class="emotion-reply">{content}</div>', unsafe_allow_html=True)


def _render_chat_mode_toggle() -> None:
    if "emotion_chat_mode" not in st.session_state:
        st.session_state.emotion_chat_mode = "single"

    col_label, col_mode = st.columns([2, 3])
    with col_label:
        st.markdown(
            '<div style="color:#8C8279;font-size:13px;padding-top:8px;">对话模式</div>',
            unsafe_allow_html=True,
        )
    with col_mode:
        st.radio(
            "对话模式",
            options=["single", "continuous"],
            format_func=lambda x: "单轮倾诉" if x == "single" else "连续对话",
            horizontal=True,
            label_visibility="collapsed",
            key="emotion_chat_mode",
        )

    if st.session_state.emotion_chat_mode == "continuous":
        st.caption("连续对话会记住本次聊天上下文，适合慢慢把心里话说完")


def _render_diary_promo() -> None:
    """情绪日记醒目入口。"""
    show_diary = st.session_state.pop("emotion_show_diary", False) or st.session_state.pop(
        "emotion_scroll_diary", False
    )
    st.markdown(
        """
<style>
.emotion-diary-promo {
  margin: 0 0 16px; padding: 14px 16px;
  background: linear-gradient(135deg, rgba(184,144,138,0.14), rgba(240,235,227,0.9));
  border: 1px solid rgba(184,144,138,0.22); border-radius: 12px;
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
}
.emotion-diary-promo-text { flex: 1; }
.emotion-diary-promo-title { font-size: 14px; font-weight: 650; color: #2C2420; }
.emotion-diary-promo-sub { font-size: 12px; color: #8C8279; margin-top: 2px; }
</style>
""",
        unsafe_allow_html=True,
    )
    st.markdown(
        """
<div class="emotion-diary-promo mirror-reveal">
  <div class="emotion-diary-promo-text">
    <div class="emotion-diary-promo-title">📔 情绪日记 · 每天签个到</div>
    <div class="emotion-diary-promo-sub">记录求职心情，看看是在好转还是更需要被接住</div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
    if st.button("打开情绪日记 ↓", key="emotion_open_diary", use_container_width=True):
        st.session_state.emotion_show_diary = True
        st.rerun()

    if show_diary:
        render_emotion_diary()
    else:
        with st.expander("📔 情绪日记（点击展开签到）", expanded=False):
            render_emotion_diary()


@st.fragment
def _render_tag_picker() -> None:
    """标签选择独立片段，避免每次点击触发整页重绘。"""
    st.markdown(
        '<div style="color:#8C8279; font-size:14px; margin-bottom:12px;">你也可以先选一个感觉</div>',
        unsafe_allow_html=True,
    )
    tag_cols = st.columns(len(EMOTION_TAGS))
    selected_idx = int(st.session_state.get("emotion_selected_idx", -1))
    for i, (label, text) in enumerate(EMOTION_TAGS):
        with tag_cols[i]:
            if st.button(label, key=f"emotion_tag_{i}", use_container_width=True):
                if selected_idx == i:
                    st.session_state.emotion_selected_idx = -1
                    st.session_state.emotion_selected_tag = ""
                else:
                    st.session_state.emotion_selected_tag = text
                    st.session_state.emotion_selected_idx = i
                    st.session_state.emotion_state = normalize_emotion_state(label)
                    st.session_state.emotion_start_touched = True
                    sync_emotion_to_session()
                selected_idx = int(st.session_state.get("emotion_selected_idx", -1))

    if selected_idx >= 0:
        st.markdown(
            f"""
<style>
.st-key-emotion_tag_{selected_idx} button {{
    background: rgba(184,144,138,0.2) !important;
    font-weight: 700 !important;
    color: #6B5B52 !important;
    border: 1px solid rgba(184,144,138,0.25) !important;
}}
</style>
""",
            unsafe_allow_html=True,
        )


@st.fragment
def _render_history_expander() -> None:
    if not st.session_state.emotion_chat_history:
        return
    st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)
    with st.expander("倾诉记录", expanded=False):
        if st.button("清空记录", key="emotion_clear_history"):
            st.session_state.emotion_chat_history = []
            _save_history([])
        for item in reversed(st.session_state.emotion_chat_history[-20:]):
            user_text = escape(item.get("input", ""))[:50]
            time_str = item.get("time", "")
            st.markdown(
                f'<div class="history-item">{user_text}<span class="history-time"> {time_str}</span></div>',
                unsafe_allow_html=True,
            )


def _render_emotion_history_records() -> None:
    history = st.session_state.get("emotion_history", [])

    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
    st.markdown(
        '<div style="color:#8C8279;font-size:13px;font-weight:600;margin-bottom:6px;">历史记录</div>',
        unsafe_allow_html=True,
    )

    if not history:
        st.caption("还没有记录，聊一次就有了")
    else:
        lines = [_format_history_line(entry) for entry in reversed(history[-5:])]
        st.text("\n".join(lines))

    st.caption("数据只存浏览器，关掉就没了")


# ===== 主入口 =====

def _consume_emotion_query() -> None:
    if hasattr(st, "query_params"):
        mode = st.query_params.get("mode")
    else:
        mode = st.experimental_get_query_params().get("mode")
    if isinstance(mode, list):
        mode = mode[0] if mode else None
    if mode == "continuous":
        st.session_state.emotion_chat_mode = "continuous"


def render():
    track_module_enter("情绪急救站")
    _consume_emotion_query()
    _inject_styles()

    # 初始化
    if "emotion_show_result" not in st.session_state:
        st.session_state.emotion_show_result = False
    if "emotion_current_reply" not in st.session_state:
        st.session_state.emotion_current_reply = ""
    if "emotion_current_input" not in st.session_state:
        st.session_state.emotion_current_input = ""
    if "emotion_chat_history" not in st.session_state:
        st.session_state.emotion_chat_history = _load_history()
    if "emotion_history" not in st.session_state:
        st.session_state.emotion_history = []
    if "emotion_selected_tag" not in st.session_state:
        st.session_state.emotion_selected_tag = ""
    if "emotion_selected_idx" not in st.session_state:
        st.session_state.emotion_selected_idx = -1
    if "chat_started" not in st.session_state:
        st.session_state.chat_started = False
    if "emotion_start_score" not in st.session_state:
        st.session_state.emotion_start_score = None
    if "emotion_end_score" not in st.session_state:
        st.session_state.emotion_end_score = None
    if "emotion_streaming" not in st.session_state:
        st.session_state.emotion_streaming = False
    if "emotion_ai_pending" not in st.session_state:
        st.session_state.emotion_ai_pending = False
    if "emotion_reasoning_chain" not in st.session_state:
        st.session_state.emotion_reasoning_chain = {}
    if "emotion_state" not in st.session_state:
        st.session_state.emotion_state = ""
    if "emotion_chat_mode" not in st.session_state:
        st.session_state.emotion_chat_mode = "single"
    if "emotion_continuous_thread" not in st.session_state:
        st.session_state.emotion_continuous_thread = []

    # 标题
    render_page_header("情绪急救站", "说了想说的话，心里会舒服一点")

    _render_chat_mode_toggle()
    _render_diary_promo()

    if st.session_state.get("emotion_state") or st.session_state.get("workshop_emotion_state"):
        apply_emotion_breath(show_encouragement=False)

    # 改动1：情绪温度计（对话开始前显示）
    if not st.session_state.get("chat_started", False):
        _render_emotion_thermometer(
            "你现在的求职状态几度？",
            "emotion_start_score",
            "emotion_start_slider",
        )

    # ========================================
    # 两种状态：输入状态 / 结果状态
    # ========================================

    if st.session_state.emotion_show_result:
        if st.session_state.get("emotion_chat_mode") == "continuous":
            _render_continuous_thread()

        st.markdown(
            f'<div class="emotion-user-words">{escape(st.session_state.emotion_current_input)}</div>',
            unsafe_allow_html=True,
        )

        if st.session_state.get("emotion_streaming"):
            score = int(st.session_state.get("emotion_start_score") or 5)
            user_text = st.session_state.emotion_current_input
            emotion = infer_emotion_from_text(user_text)
            instant = pick_instant_reply(emotion, score)
            st.session_state.emotion_current_reply = instant
            st.session_state.emotion_streaming = False

            skip_ai = (score <= 3) or not _llm_available()
            if skip_ai:
                st.session_state.emotion_ai_pending = False
                _append_chat_history(user_text, instant)
                _append_to_continuous_thread(user_text, instant)
            else:
                st.session_state.emotion_ai_pending = True
            st.rerun()

        if st.session_state.emotion_current_reply:
            st.markdown(
                f'<div class="emotion-reply">{escape(st.session_state.emotion_current_reply).replace(chr(10), "<br>")}</div>',
                unsafe_allow_html=True,
            )
            if st.session_state.get("emotion_ai_pending"):
                st.caption("💙 小镜先陪你说一句 — 如果想听更贴你情况的话，稍等几秒…")
                try:
                    score = int(st.session_state.get("emotion_start_score") or 5)
                    _run_emotion_response(user_text=st.session_state.emotion_current_input, emotion_start_score=score)
                except Exception as e:
                    st.session_state.emotion_ai_pending = False
                    handle_api_error(e, context="emotion")
                st.rerun()
            else:
                _render_action_guidance()
        elif st.session_state.get("emotion_ai_pending"):
            st.caption("💙 小镜正在准备回应…")

        st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)
        _render_restart_button()

    else:
        st.markdown(
            '<div style="color:#8C8279; font-size:14px; margin-bottom:12px;">你现在是什么感觉？随便说，或先选一个标签</div>',
            unsafe_allow_html=True,
        )
        _render_tag_picker()

        selected_tag = st.session_state.get("emotion_selected_tag", "")
        if selected_tag:
            st.markdown(
                '<div style="color:#6B5B52;font-size:13px;font-weight:700;margin-bottom:6px;">已选择情绪标签</div>',
                unsafe_allow_html=True,
            )

        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

        user_input = st.text_area(
            "或者自己写",
            placeholder="把现在最堵的那句话写下来...",
            label_visibility="collapsed",
            key="emotion_text_area",
            height=100,
        )

        st.markdown("<div style='height:4px;'></div>", unsafe_allow_html=True)

        if st.button("说出来", key="emotion_submit", use_container_width=True, type="secondary"):
            final_input = selected_tag or (user_input.strip() if user_input and user_input.strip() else None)
            if final_input:
                st.session_state.emotion_current_input = final_input
                st.session_state.emotion_start_touched = True
                st.session_state.emotion_state = normalize_emotion_state(selected_tag or final_input)
                st.session_state.workshop_emotion_state = st.session_state.emotion_state
                st.session_state.emotion_current_reply = ""
                st.session_state.emotion_show_result = True
                st.session_state.emotion_streaming = True
                st.session_state.emotion_ai_pending = False
                st.session_state.chat_started = True
                st.session_state.emotion_selected_tag = ""
                st.session_state.emotion_selected_idx = -1
                st.rerun()
            else:
                st.warning("选一个标签，或者写点什么吧")

    # 情绪追踪：聊后复测 + 历史记录（对话轮次 >= 3 时显示）
    if len(st.session_state.emotion_chat_history) >= 3:
        with st.expander("📊 情绪追踪", expanded=False):
            _render_emotion_thermometer(
                "聊完之后，你现在几度？",
                "emotion_end_score",
                "emotion_end_slider",
            )
            start = st.session_state.get("emotion_start_score")
            end = st.session_state.get("emotion_end_score")
            if start is not None and end is not None:
                _maybe_record_emotion_delta()
                st.success(_delta_feedback(start, end))
            _render_emotion_history_records()

    st.caption("🔒 对话保存在本地会话目录，可在侧边栏「历史记录」回看")
    _render_history_expander()

    st.markdown("---")

    render_section_title("什么时候需要来这里")
    cols = st.columns(3)
    items = [
        ("收到拒信的时候", "明明准备了好久，结果还是没过"),
        ("刷到别人offer的时候", "朋友圈又有人晒offer，自己什么都没有"),
        ("投了一百份简历没回音", "不是不努力，是真的没有回应"),
    ]
    for i, (title, desc) in enumerate(items):
        with cols[i]:
            st.markdown(f"""
        <div style="background-color:#FAF7F4; border-radius:8px; padding:16px; border-left:3px solid #B8908A;">
            <div style="color:#2C2420; font-size:14px; font-weight:600;">{title}</div>
            <div style="color:#8C8279; font-size:12px; margin-top:4px;">{desc}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    st.markdown("""
<div style="background-color:#F0EBE3; border-radius:8px; padding:12px 16px;">
    <span style="color:#8C8279; font-size:13px;">这里没有评判，没有建议，只有一个人听你说。</span>
</div>
""", unsafe_allow_html=True)
