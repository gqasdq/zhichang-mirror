from pathlib import Path
from typing import Dict, Any, Optional

from pydantic import BaseModel, Field

from agents.base_agent import BaseAgent
from agents.emotion.empathy_chain import run_chain_of_empathy
from agents.emotion.parse_utils import as_text, extract_json_payload, extract_natural_response
from agents.emotion.prompt_utils import inject_few_shot_examples
from core.privacy_filter import sanitize_chat_for_api
from loguru import logger


class GrievanceResponse(BaseModel):
    """委屈疏导响应"""

    empathy: str = Field(description="共情回应")
    confirmation: str = Field(description="情绪确认")
    relaxation: str = Field(description="放松引导")
    cognitive: str = Field(description="认知重构")
    actions: list[str] = Field(default_factory=list, description="行动建议")
    reasoning_chain: dict[str, str] = Field(default_factory=dict, description="Chain-of-Empathy 推理链")


_GRIEVANCE_DEEP_PROMPT = ""
_prompt_path = Path(__file__).resolve().parent.parent.parent / "prompts" / "emotion" / "grievance_prompt.txt"
if _prompt_path.exists():
    _GRIEVANCE_DEEP_PROMPT = _prompt_path.read_text(encoding="utf-8")


class GrievanceAgent(BaseAgent):
    """委屈疏导Agent"""

    AGENT_NAME = "grievance_agent"

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
    ) -> GrievanceResponse:
        """提供委屈疏导响应"""
        logger.info("GrievanceAgent: Generating response for user")

        sanitized = sanitize_chat_for_api(user_input)
        emotion_desc = self._build_emotion_desc(sanitized, emotion_state)

        system_prompt = (
            _GRIEVANCE_DEEP_PROMPT
            if _GRIEVANCE_DEEP_PROMPT
            else "你是一位温暖、专业的职场心理咨询师。"
        )
        if system_prompt_override:
            system_prompt = f"{system_prompt}\n\n{system_prompt_override}"
        system_prompt = inject_few_shot_examples(system_prompt, few_shot_examples)

        reasoning, response = run_chain_of_empathy(
            user_input=sanitized,
            emotion_state=emotion_state,
            respond_style="林姐",
            system_prompt=system_prompt,
            rag_context=rag_context,
            extra_task_hint=f"{emotion_desc}\n请用林姐的口吻回复。先接住委屈和愤怒，再温和引导。短句为主，2-4段。",
            rag_label=rag_label,
        )

        result = self._parse_response(response)
        result.reasoning_chain = reasoning.model_dump()
        logger.info(f"GrievanceAgent: Response generated, {len(result.actions)} actions")
        return result

    def _build_emotion_desc(
        self,
        user_input: str,
        emotion_state: Optional[Dict[str, Any]]
    ) -> str:
        """构建情绪状态描述"""
        desc = f"用户描述：{user_input}\n\n"

        if emotion_state:
            desc += f"主要情绪：{emotion_state.get('primary_emotion', '委屈')}\n"
            desc += f"情绪强度：{emotion_state.get('intensity', '中度')}\n"
            desc += f"关键表达：{', '.join(emotion_state.get('key_phrases', []))}\n"

        return desc

    def _parse_response(self, response: str) -> GrievanceResponse:
        """解析LLM响应"""
        text = extract_natural_response(response)
        json_data = extract_json_payload(text)
        if json_data:
            actions: list[str] = []
            for option_key in ("option_a", "option_b"):
                option = json_data.get(option_key)
                if isinstance(option, dict):
                    title = as_text(option.get("title"))
                    desc = as_text(option.get("description"))
                    if title and desc:
                        actions.append(f"{title}：{desc}")
                    elif title:
                        actions.append(title)

            for item in (
                json_data.get("recommended_action"),
                json_data.get("self_protection_tip"),
            ):
                item_text = as_text(item)
                if item_text:
                    actions.append(item_text)

            return GrievanceResponse(
                empathy=as_text(json_data.get("empathic_response")),
                confirmation=as_text(json_data.get("validity_assessment") or json_data.get("reassurance")),
                relaxation=as_text(json_data.get("self_protection_tip")),
                cognitive=as_text(json_data.get("rights_analysis") or json_data.get("situation_clarification")),
                actions=actions[:5],
            )

        if text.strip():
            return GrievanceResponse(empathy=text.strip(), confirmation="", relaxation="", cognitive="", actions=[])

        return GrievanceResponse(empathy="", confirmation="", relaxation="", cognitive="", actions=[])


# 全局实例
grievance_agent = GrievanceAgent()
