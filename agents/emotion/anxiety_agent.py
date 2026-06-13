from pathlib import Path
from typing import Dict, Any, Optional

from pydantic import BaseModel, Field

from agents.base_agent import BaseAgent
from agents.emotion.empathy_chain import run_chain_of_empathy
from agents.emotion.parse_utils import extract_json_payload, extract_natural_response, as_str_list, as_text
from agents.emotion.prompt_utils import inject_few_shot_examples
from core.privacy_filter import sanitize_chat_for_api
from loguru import logger


class AnxietyResponse(BaseModel):
    """焦虑缓解响应"""

    empathy: str = Field(description="共情回应")
    confirmation: str = Field(description="情绪确认")
    relaxation: str = Field(description="放松引导")
    cognitive: str = Field(description="认知重构")
    actions: list[str] = Field(default_factory=list, description="行动建议")
    reasoning_chain: dict[str, str] = Field(default_factory=dict, description="Chain-of-Empathy 推理链")


_ANXIETY_DEEP_PROMPT = ""
_prompt_path = Path(__file__).resolve().parent.parent.parent / "prompts" / "emotion" / "anxiety_prompt.txt"
if _prompt_path.exists():
    _ANXIETY_DEEP_PROMPT = _prompt_path.read_text(encoding="utf-8")


class AnxietyAgent(BaseAgent):
    """焦虑缓解Agent"""

    AGENT_NAME = "anxiety_agent"

    def __init__(self):
        super().__init__(self.AGENT_NAME)

    def respond(
        self,
        user_input: str,
        emotion_state: Optional[Dict[str, Any]] = None,
        rag_context: str = "",
        system_prompt_override: str = "",
        rag_label: str = "相似案例",
        few_shot_examples: str = "",
    ) -> AnxietyResponse:
        """提供焦虑缓解响应"""
        logger.info("AnxietyAgent: Generating response for user")

        sanitized = sanitize_chat_for_api(user_input)
        emotion_desc = self._build_emotion_desc(sanitized, emotion_state)

        system_prompt = (
            _ANXIETY_DEEP_PROMPT
            if _ANXIETY_DEEP_PROMPT
            else "你是一位温暖、专业的职场心理咨询师。"
        )
        if system_prompt_override:
            system_prompt = f"{system_prompt}\n\n{system_prompt_override}"
        system_prompt = inject_few_shot_examples(system_prompt, few_shot_examples)

        reasoning, response = run_chain_of_empathy(
            user_input=sanitized,
            emotion_state=emotion_state,
            respond_style="阿杰",
            system_prompt=system_prompt,
            rag_context=rag_context,
            extra_task_hint=f"{emotion_desc}\n请用阿杰的口吻回复。先接住焦虑，再温和引导。短句为主，2-4段。",
            rag_label=rag_label,
        )

        result = self._parse_response(response)
        result.reasoning_chain = reasoning.model_dump()
        logger.info(f"AnxietyAgent: Response generated, {len(result.actions)} actions")
        return result

    def _build_emotion_desc(
        self,
        user_input: str,
        emotion_state: Optional[Dict[str, Any]]
    ) -> str:
        """构建情绪状态描述"""
        desc = f"用户描述：{user_input}\n\n"

        if emotion_state:
            desc += f"主要情绪：{emotion_state.get('primary_emotion', '焦虑')}\n"
            desc += f"情绪强度：{emotion_state.get('intensity', '中度')}\n"
            desc += f"关键表达：{', '.join(emotion_state.get('key_phrases', []))}\n"

        return desc

    def _parse_response(self, response: str) -> AnxietyResponse:
        """解析LLM响应"""
        text = extract_natural_response(response)
        json_data = extract_json_payload(text)
        if json_data:
            actions: list[str] = []
            actions.extend(as_str_list(json_data.get("anxiety_triggers")))
            for item in (
                json_data.get("actionable_tip"),
                json_data.get("coping_technique"),
                json_data.get("self_talk_reminder"),
            ):
                item_text = as_text(item)
                if item_text:
                    actions.append(item_text)

            return AnxietyResponse(
                empathy=as_text(json_data.get("empathic_response")),
                confirmation=as_text(json_data.get("anxiety_naming") or json_data.get("reassurance")),
                relaxation=as_text(json_data.get("coping_technique")),
                cognitive=as_text(json_data.get("cognitive_restructuring")),
                actions=actions[:5],
            )

        if text.strip():
            return AnxietyResponse(empathy=text.strip(), confirmation="", relaxation="", cognitive="", actions=[])

        return AnxietyResponse(empathy="", confirmation="", relaxation="", cognitive="", actions=[])


# 全局实例
anxiety_agent = AnxietyAgent()
