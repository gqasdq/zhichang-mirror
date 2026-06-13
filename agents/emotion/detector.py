from typing import Dict, Any, Literal, Optional
from pydantic import BaseModel, Field
from loguru import logger

from agents.base_agent import BaseAgent
from agents.emotion.parse_utils import extract_json_payload, as_float, as_str_list, as_text
from agents.emotion.score_utils import build_emotion_score_strategy_hint
from core.model_router import model_router
from core.privacy_filter import sanitize_chat_for_api
from core.prompt_manager import prompt_manager


class EmotionDetectionResult(BaseModel):
    """情绪检测结果"""

    primary_emotion: Literal["焦虑", "委屈", "挫败", "迷茫"] = Field(
        description="主要情绪类型"
    )
    confidence: float = Field(description="置信度 0.0-1.0", ge=0.0, le=1.0)
    secondary_emotions: list[str] = Field(default_factory=list, description="次要情绪")
    key_phrases: list[str] = Field(default_factory=list, description="关键短语")
    intensity: Literal["轻度", "中度", "重度"] = Field(description="情绪强度")


class EmotionDetectorAgent(BaseAgent):
    """情绪检测Agent"""

    AGENT_NAME = "emotion_detector"
    PROMPT_TEMPLATE = "emotion/detector_prompt.txt"

    def __init__(self):
        super().__init__(self.AGENT_NAME)

    def detect(
        self,
        user_input: str,
        emotion_start_score: Optional[int] = None,
    ) -> EmotionDetectionResult:
        """
        检测用户情绪

        Args:
            user_input: 用户输入文本
            emotion_start_score: 用户自评情绪温度计分数（1-10）

        Returns:
            EmotionDetectionResult: 情绪检测结果
        """
        logger.info(f"EmotionDetector: Detecting emotion for input length={len(user_input)}")

        sanitized = sanitize_chat_for_api(user_input)
        prompt = prompt_manager.render(
            self.PROMPT_TEMPLATE,
            user_input=sanitized,
            few_shot_examples="（暂无相似优质样例）",
        )
        prompt += f"\n\n## 用户输入\n{sanitized}\n"
        if emotion_start_score is not None:
            prompt += f"\n{build_emotion_score_strategy_hint(emotion_start_score)}\n"

        # 调用LLM
        response = model_router.call(
            prompt=prompt,
            task_type="simple_qa",
            system_prompt="你是一个专业的职场情绪分析师，严格按照JSON格式输出。",
        )

        # 解析结果
        result = self._parse_response(response)

        logger.info(f"EmotionDetector: Detected {result.primary_emotion} (confidence={result.confidence})")

        return result

    def _parse_response(self, response: str) -> EmotionDetectionResult:
        """解析LLM响应"""
        try:
            data = extract_json_payload(response)
            if not data:
                raise ValueError("No JSON payload found")

            raw_emotion = as_text(data.get("primary_emotion") or data.get("emotion_type"), "迷茫")
            if raw_emotion not in {"焦虑", "委屈", "挫败", "迷茫"}:
                raw_emotion = "迷茫"

            raw_intensity = as_text(data.get("intensity") or data.get("intensity_level"), "中度")
            if raw_intensity not in {"轻度", "中度", "重度"}:
                raw_intensity = "中度"

            confidence = as_float(data.get("confidence", data.get("emotion_type_confidence", 0.5)), 0.5)
            confidence = max(0.0, min(1.0, confidence))

            secondary = as_str_list(data.get("secondary_emotions"))
            if not secondary:
                secondary = as_str_list(data.get("detected_hints"))

            return EmotionDetectionResult(
                primary_emotion=raw_emotion,  # type: ignore[arg-type]
                confidence=confidence,
                secondary_emotions=secondary,
                key_phrases=as_str_list(data.get("key_phrases")),
                intensity=raw_intensity,  # type: ignore[arg-type]
            )
        except Exception as e:
            logger.error(f"Failed to parse emotion detection: {e}")
            return EmotionDetectionResult(
                primary_emotion="迷茫",
                confidence=0.0,
                secondary_emotions=[],
                key_phrases=[],
                intensity="中度",
            )


# 全局实例
emotion_detector = EmotionDetectorAgent()
