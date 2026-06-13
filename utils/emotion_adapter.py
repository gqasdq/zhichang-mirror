"""情绪联动适配器：AI 语气 + 界面主题呼吸。"""

from __future__ import annotations

import html
from typing import Sequence

try:
    import streamlit as st
except ImportError:  # pragma: no cover
    st = None  # type: ignore


class EmotionAdapter:
    """根据情绪状态调整 AI 优化语气与界面节奏。"""

    ANXIOUS = "焦虑"
    FRUSTRATED = "挫败"
    CONFUSED = "迷茫"
    CALM = "平稳"

    EMOTION_KEYS = {
        ANXIOUS: "anxious",
        FRUSTRATED: "frustrated",
        CONFUSED: "confused",
        CALM: "calm",
    }

    EMOTION_THEMES: dict[str, dict] = {
        "焦虑": {
            "primary_color": "#C4A882",
            "accent_color": "#8B7355",
            "card_bg": "rgba(196,168,130,0.18)",
            "bg_tint": "rgba(196,168,130,0.32)",
            "bg_mid": "#F3E8DC",
            "sidebar_tint": "#E8DDD0",
            "surface_bg": "rgba(255,250,245,0.94)",
            "layout": "single_column",
            "section_gap": "32px",
            "animation_speed": "0.8s",
            "show_encouragement": True,
            "encouragement_text": "一步一步来，每次只看一个就好",
            "progress_style": "minimal",
            "emoji_prefix": "🫂",
        },
        "挫败": {
            "primary_color": "#7EA88E",
            "accent_color": "#5DAE8B",
            "card_bg": "rgba(126,168,142,0.18)",
            "bg_tint": "rgba(126,168,142,0.28)",
            "bg_mid": "#EAF3EC",
            "sidebar_tint": "#DFEBE3",
            "surface_bg": "rgba(248,252,249,0.94)",
            "layout": "praise_first",
            "section_gap": "24px",
            "animation_speed": "0.6s",
            "show_encouragement": True,
            "encouragement_text": "你已经比很多人勇敢了，先看看你做得好的地方",
            "progress_style": "highlight_green",
            "emoji_prefix": "🌱",
        },
        "迷茫": {
            "primary_color": "#A8927E",
            "accent_color": "#8B7355",
            "card_bg": "rgba(168,146,126,0.16)",
            "bg_tint": "rgba(168,146,126,0.24)",
            "bg_mid": "#F0EAE4",
            "sidebar_tint": "#E5DDD5",
            "surface_bg": "rgba(255,252,249,0.94)",
            "layout": "guided",
            "section_gap": "20px",
            "animation_speed": "0.7s",
            "show_encouragement": True,
            "encouragement_text": "不知道从哪开始？我帮你一步步理清",
            "progress_style": "step_by_step",
            "emoji_prefix": "🧭",
        },
        "平稳": {
            "primary_color": "#B8908A",
            "accent_color": "#D4956A",
            "card_bg": "rgba(255,255,255,0.55)",
            "bg_tint": "transparent",
            "bg_mid": "",
            "sidebar_tint": "",
            "surface_bg": "",
            "layout": "normal",
            "section_gap": "16px",
            "animation_speed": "0.5s",
            "show_encouragement": False,
            "encouragement_text": "",
            "progress_style": "standard",
            "emoji_prefix": "✨",
        },
    }

    def __init__(self, emotion_state: str = "平稳"):
        self.emotion = normalize_emotion_state(emotion_state)

    @classmethod
    def from_session(cls) -> "EmotionAdapter":
        """从 session_state 读取情绪（标签 > 已保存状态 > 温度计分数）。"""
        if st is None:
            return cls()
        return cls(sync_emotion_to_session())

    def get_theme(self) -> dict:
        return self.EMOTION_THEMES.get(self.emotion, self.EMOTION_THEMES[self.CALM])

    def get_emotion_key(self) -> str:
        return self.EMOTION_KEYS.get(self.emotion, "calm")

    def get_layout_mode(self) -> str:
        return self.get_theme()["layout"]

    def get_section_gap(self) -> str:
        return self.get_theme()["section_gap"]

    def get_progress_style(self) -> str:
        return self.get_theme().get("progress_style", "standard")

    def get_theme_marker_html(self) -> str:
        key = self.get_emotion_key()
        return (
            f'<div id="emotion-root" data-emotion="{key}" '
            f'class="emotion-transition emotion-marker" aria-hidden="true"></div>'
        )

    def get_shell_class(self, base: str = "gold-report-shell") -> str:
        """报告容器 class，非平稳时附加呼吸动画。"""
        key = self.get_emotion_key()
        if key == "calm":
            return base
        return f"{base} emotion-surface emotion-surface--{key}"

    def get_full_theme_css(self) -> str:
        """情绪 CSS 已移至 ui/styles.py 全局注入，此处不再重复。"""
        return ""

    def get_bg_override_css(self) -> str:
        return self.get_full_theme_css()

    def inject_page_theme(self) -> None:
        """注入隐藏标记（CSS 由 sidebar 全局 styles 加载）。"""
        if st is None:
            return
        st.markdown(self.get_theme_marker_html(), unsafe_allow_html=True)

    def render_encouragement(self) -> None:
        if st is None:
            return
        theme = self.get_theme()
        if not theme.get("show_encouragement"):
            return
        text = html.escape(theme.get("encouragement_text", ""))
        emoji = theme.get("emoji_prefix", "")
        st.markdown(
            f"""
<div class="emotion-encourage" style="
    background: {theme['card_bg']};
    border-left: 3px solid {theme['accent_color']};
    padding: 14px 18px;
    border-radius: 0 12px 12px 0;
    margin-bottom: {theme['section_gap']};
    box-shadow: 0 2px 12px rgba(44,36,32,0.04);
">
    <span style="font-size:14px; color:#5C4B45; line-height:1.65; letter-spacing:0.01em;">
        {emoji} {text}
    </span>
</div>
""",
            unsafe_allow_html=True,
        )

    def render_guided_steps(self, steps: list[str], title: str = "跟着这三步走") -> None:
        if st is None or not steps:
            return
        theme = self.get_theme()
        items_html = ""
        for i, step in enumerate(steps[:3]):
            delay_class = f" step-guide-{i + 1}" if i else ""
            items_html += (
                f'<div class="step-guide{delay_class}" style="font-size:13px; color:#5C4B45; '
                f'margin-top:{"8" if i else "0"}px; line-height:1.6;">'
                f"{html.escape(step)}</div>"
            )
        st.markdown(
            f"""
<div style="background:{theme['card_bg']}; padding:14px 18px; border-radius:12px;
            margin-bottom:{theme['section_gap']}; border:1px solid rgba(61,56,51,0.06);">
    <div style="font-size:13px; color:#5C4B45; font-weight:600; margin-bottom:6px;">
        {theme.get('emoji_prefix', '🧭')} {html.escape(title)}
    </div>
    {items_html}
</div>
""",
            unsafe_allow_html=True,
        )

    def get_system_prompt_suffix(self) -> str:
        templates = {
            "焦虑": (
                "用户当前处于焦虑状态。语气要求：\n"
                "- 用温和鼓励的语气，不要用批评性措辞\n"
                "- 先肯定再建议，如'这段经历很有价值，只需要调整表达方式'\n"
                "- 避免说'缺少''不足''问题'，改为'可以补充''还能提升'\n"
                "- 每次优化建议不要超过3条，避免信息过载\n"
            ),
            "挫败": (
                "用户当前处于挫败状态。语气要求：\n"
                "- 先夸再改，每个优化建议前先肯定原文的价值\n"
                "- 如'这个经历本身很好，用STAR结构写出来会更出彩'\n"
                "- 优先展示优势和已做得好的地方\n"
                "- 把'缺点'重新定义为'提升空间'\n"
            ),
            "迷茫": (
                "用户当前处于迷茫状态。语气要求：\n"
                "- 用引导性语气，帮助用户找到方向\n"
                "- 如'根据你的经历，XX方向可能和你的匹配度更高'\n"
                "- 优化建议时说明'为什么要这样改'，不只是告诉改什么\n"
                "- 主动建议用户补充JD，这样优化更有针对性\n"
            ),
            "平稳": (
                "用户当前情绪平稳。语气要求：\n"
                "- 专业直接，不用刻意鼓励\n"
                "- 清晰指出问题和改进方向\n"
                "- 可以一次给出完整优化建议\n"
            ),
        }
        return templates.get(self.emotion, templates["平稳"])

    def get_section_order(
        self,
        sections: dict[str, str],
        default_order: Sequence[str] | None = None,
    ) -> list[str]:
        keys = list(default_order or sections.keys())
        if self.emotion == self.FRUSTRATED:
            return sorted(keys, key=lambda k: len(str(sections.get(k, ""))), reverse=True)
        if self.emotion == self.CONFUSED:
            priority = [
                "objective",
                "skills",
                "work_exp",
                "project_exp",
                "education",
                "self_eval",
                "basic_info",
            ]
            return [k for k in priority if k in keys] + [k for k in keys if k not in priority]
        return keys

    def get_pace_hint(self) -> str | None:
        if self.get_theme().get("show_encouragement"):
            return None
        hints = {
            "焦虑": "不急，我们一步一步来。选一个板块，慢慢优化就好。",
            "挫败": "你的经历比你想象的有价值。每优化一个板块，你会看到变化。",
            "迷茫": "建议先粘贴目标岗位JD，这样优化会更有方向感。",
        }
        return hints.get(self.emotion)

    def should_limit_optimization(self) -> bool:
        return self.emotion == self.ANXIOUS

    def get_jd_prompt(self) -> str | None:
        if self.emotion == self.CONFUSED:
            return (
                "💡 补充目标岗位JD后，AI优化会更有针对性。"
                "点击左侧「金子探测器」粘贴JD后再回来。"
            )
        return None


def _read_thermometer_score() -> int | None:
    """读取用户主动拖动过的温度计分数（忽略未触碰的默认值）。"""
    if st is None:
        return None
    if st.session_state.get("home_emotion_touched"):
        raw = st.session_state.get("home_emotion_score")
        if raw is None:
            raw = st.session_state.get("home_emotion_slider")
        if raw is not None:
            try:
                return int(raw)
            except (TypeError, ValueError):
                pass
    if st.session_state.get("emotion_start_touched"):
        raw = st.session_state.get("emotion_start_score")
        if raw is not None:
            try:
                return int(raw)
            except (TypeError, ValueError):
                pass
    return None


def emotion_from_score(score: int) -> str:
    """温度计 1=最低落、10=最好 → 映射界面情绪主题。"""
    if score <= 3:
        return EmotionAdapter.FRUSTRATED
    if score <= 6:
        return EmotionAdapter.ANXIOUS
    if score <= 7:
        return EmotionAdapter.CONFUSED
    return EmotionAdapter.CALM


def resolve_emotion_from_session() -> str:
    """综合标签、聊天状态、温度计推断当前情绪（不读 workshop，避免被「平稳」锁死）。"""
    if st is None:
        return EmotionAdapter.CALM

    tag = (st.session_state.get("emotion_selected_tag") or "").strip()
    if tag:
        return normalize_emotion_state(tag)

    raw = st.session_state.get("emotion_state")
    if raw and str(raw).strip():
        return normalize_emotion_state(str(raw))

    score = _read_thermometer_score()
    if score is not None:
        return emotion_from_score(score)

    return EmotionAdapter.CALM


def resolve_emotion_source() -> tuple[str, str, int | None]:
    """返回 (情绪, 来源, 分数)。来源: tag | chat | score | default"""
    if st is None:
        return EmotionAdapter.CALM, "default", None

    tag = (st.session_state.get("emotion_selected_tag") or "").strip()
    if tag:
        return normalize_emotion_state(tag), "tag", _read_thermometer_score()

    raw = st.session_state.get("emotion_state")
    if raw and str(raw).strip():
        return normalize_emotion_state(str(raw)), "chat", _read_thermometer_score()

    score = _read_thermometer_score()
    if score is not None:
        return emotion_from_score(score), "score", score

    return EmotionAdapter.CALM, "default", None


def sync_emotion_to_session() -> str:
    """把推断结果写入 workshop_emotion_state，供跨页面联动。"""
    emotion = resolve_emotion_from_session()
    if st is not None:
        st.session_state.workshop_emotion_state = emotion
    return emotion


def normalize_emotion_state(raw: str | None) -> str:
    if not raw:
        return EmotionAdapter.CALM

    text = str(raw).strip()
    if text in (
        EmotionAdapter.ANXIOUS,
        EmotionAdapter.FRUSTRATED,
        EmotionAdapter.CONFUSED,
        EmotionAdapter.CALM,
    ):
        return text

    lowered = text.lower()
    if any(k in text for k in ("焦虑", "低落", "偏焦虑")) or "anx" in lowered:
        return EmotionAdapter.ANXIOUS
    if any(k in text for k in ("挫败", "委屈", "放弃", "失败")):
        return EmotionAdapter.FRUSTRATED
    if "迷茫" in text or "方向" in text:
        return EmotionAdapter.CONFUSED
    if "平稳" in text:
        return EmotionAdapter.CALM

    return EmotionAdapter.CALM
