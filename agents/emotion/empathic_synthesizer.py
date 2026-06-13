from pathlib import Path
from typing import Dict, Any, Iterator

from pydantic import BaseModel, Field

from agents.base_agent import BaseAgent
from agents.emotion.parse_utils import extract_natural_response
from core.model_router import model_router
from core.privacy_filter import sanitize_chat_for_api
from loguru import logger


class SynthesizedResponse(BaseModel):
    """整合后的响应"""

    content: str = Field(description="最终响应内容")
    emotion_type: str = Field(description="情绪类型")
    key_suggestions: list[str] = Field(default_factory=list, description="核心建议")


_SYNTHESIZER_DEEP_PROMPT = ""
_prompt_path = Path(__file__).resolve().parent.parent.parent / "prompts" / "emotion" / "synthesizer_prompt.txt"
if _prompt_path.exists():
    _SYNTHESIZER_DEEP_PROMPT = _prompt_path.read_text(encoding="utf-8")


class EmpathicSynthesizer(BaseAgent):
    """共情整合Agent"""

    AGENT_NAME = "empathic_synthesizer"

    def __init__(self):
        super().__init__(self.AGENT_NAME)

    def _build_synthesis_prompt(
        self,
        user_input: str,
        emotion_detection: Dict[str, Any],
        agent_output: str,
        emotion_type: str,
        score_strategy_hint: str = "",
    ) -> tuple[str, str]:
        sanitized = sanitize_chat_for_api(user_input)
        intensity = emotion_detection.get("intensity", "中度")
        key_phrases = ", ".join(emotion_detection.get("key_phrases", [])[:5])

        system_prompt = (
            _SYNTHESIZER_DEEP_PROMPT
            if _SYNTHESIZER_DEEP_PROMPT
            else "你是一位温暖的朋友，用自然对话的方式回复。只输出纯文本。"
        )

        task_prompt = f"""用户说：{sanitized}

情绪类型：{emotion_type}
情绪强度：{intensity}
关键表达：{key_phrases or "无"}

专业回复参考（仅供理解，不要照搬结构和用词）：
{agent_output}

请用小明的口吻回复。先接住情绪，再温和回应。短句为主，2-4段。"""

        if score_strategy_hint:
            task_prompt += f"\n\n{score_strategy_hint}"

        return task_prompt, system_prompt

    def synthesize(
        self,
        user_input: str,
        emotion_detection: Dict[str, Any],
        agent_output: str,
        emotion_type: str,
        score_strategy_hint: str = "",
    ) -> SynthesizedResponse:
        """整合各Agent输出，生成最终自然语言响应。"""
        logger.info(f"Synthesizer: Synthesizing response for {emotion_type}")
        task_prompt, system_prompt = self._build_synthesis_prompt(
            user_input=user_input,
            emotion_detection=emotion_detection,
            agent_output=agent_output,
            emotion_type=emotion_type,
            score_strategy_hint=score_strategy_hint,
        )

        response = model_router.call(
            prompt=task_prompt,
            task_type="emotional_empathy",
            system_prompt=system_prompt,
            max_tokens=300,
        )

        content = extract_natural_response(response)
        suggestions = self._extract_suggestions(content)

        return SynthesizedResponse(
            content=content,
            emotion_type=emotion_type,
            key_suggestions=suggestions,
        )

    def synthesize_stream(
        self,
        user_input: str,
        emotion_detection: Dict[str, Any],
        agent_output: str,
        emotion_type: str,
        score_strategy_hint: str = "",
    ) -> Iterator[str]:
        """流式整合输出，供 UI write_stream 使用。"""
        task_prompt, system_prompt = self._build_synthesis_prompt(
            user_input=user_input,
            emotion_detection=emotion_detection,
            agent_output=agent_output,
            emotion_type=emotion_type,
            score_strategy_hint=score_strategy_hint,
        )
        yield from model_router.call_stream(
            prompt=task_prompt,
            task_type="emotional_empathy",
            system_prompt=system_prompt,
            max_tokens=300,
        )

    def _extract_suggestions(self, content: str) -> list[str]:
        """提取关键建议"""
        suggestions = []
        lines = content.split("\n")

        for line in lines:
            line = line.strip()
            if line.startswith(("1.", "2.", "3.", "4.", "5.")) or line.startswith("-"):
                suggestion = line.lstrip("0123456789.- ").strip()
                if suggestion:
                    suggestions.append(suggestion)

        return suggestions[:3]


# 全局实例
empathic_synthesizer = EmpathicSynthesizer()
