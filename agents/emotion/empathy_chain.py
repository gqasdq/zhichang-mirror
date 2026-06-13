"""Chain-of-Empathy 共情推理链 — 反思 → 策略 → 生成 → 自检。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from agents.emotion.parse_utils import extract_json_payload
from core.model_router import model_router
from loguru import logger


@dataclass
class EmpathyReasoning:
    """情绪推理中间结果（四步共情链）。"""

    emotion_analysis: str = ""
    reflection: str = ""
    support_type: str = ""
    strategy: str = ""
    self_check: str = ""

    def model_dump(self) -> dict[str, str]:
        return {
            "emotion_analysis": self.emotion_analysis,
            "reflection": self.reflection,
            "support_type": self.support_type,
            "strategy": self.strategy,
            "self_check": self.self_check,
        }

    @property
    def is_valid(self) -> bool:
        return bool(
            self.emotion_analysis
            or self.reflection
            or self.support_type
            or self.strategy
        )


def parse_reasoning(raw_content: str) -> EmpathyReasoning:
    """解析推理链 JSON。"""
    data = extract_json_payload(raw_content) or {}
    return EmpathyReasoning(
        emotion_analysis=str(data.get("emotion_analysis", "")).strip(),
        reflection=str(data.get("reflection", "")).strip(),
        support_type=str(data.get("support_type", "")).strip(),
        strategy=str(data.get("strategy", "")).strip(),
        self_check=str(data.get("self_check", "")).strip(),
    )


def _build_reasoning_prompt(user_input: str, emotion_state: Optional[dict[str, Any]]) -> str:
    emotion_hint = ""
    if emotion_state:
        emotion_hint = (
            f"\n已检测情绪：{emotion_state.get('primary_emotion', '未知')}，"
            f"强度：{emotion_state.get('intensity', '中度')}"
        )

    return f"""请分析用户的情绪状态，完成 Chain-of-Empathy 四步推理：

用户说：{user_input}{emotion_hint}

步骤1 · 情绪识别：用户的核心情绪是什么？为什么？
步骤2 · 反思：我为什么这样判断？用户的真实需求是什么？
步骤3 · 策略选择：这个人需要被认可 / 具体建议 / 被理解 / 情绪宣泄？
步骤4 · 自检：我应该怎么回应？这条回复会不会让用户更焦虑？

只需输出 JSON：
{{
  "emotion_analysis": "...",
  "reflection": "...",
  "support_type": "...",
  "strategy": "...",
  "self_check": "..."
}}"""


def run_chain_of_empathy(
    user_input: str,
    emotion_state: Optional[dict[str, Any]],
    respond_style: str,
    system_prompt: str,
    rag_context: str = "",
    extra_task_hint: str = "",
    rag_label: str = "相似案例",
) -> tuple[EmpathyReasoning, str]:
    """
    两阶段共情推理：
    1. complex_analysis — 四步推理链
    2. emotional_empathy — 基于推理生成最终回复
    """
    reasoning_prompt = _build_reasoning_prompt(user_input, emotion_state)

    reasoning_response = model_router.call(
        prompt=reasoning_prompt,
        task_type="complex_analysis",
        system_prompt="你是情绪分析专家，先分析再行动。输出严格 JSON。",
        temperature=0.3,
        max_tokens=650,
    )
    reasoning = parse_reasoning(reasoning_response)
    logger.info(
        "Chain-of-Empathy: support=%s self_check=%s",
        reasoning.support_type or "unknown",
        "yes" if reasoning.self_check else "no",
    )

    enhanced_prompt = f"""基于以下 Chain-of-Empathy 分析，生成回复：

用户说：{user_input}

【思考过程】
① 情绪识别：{reasoning.emotion_analysis or '（待补充）'}
② 反思：{reasoning.reflection or '（待补充）'}
③ 支持类型：{reasoning.support_type or '被理解'}
④ 策略：{reasoning.strategy or '温和陪伴'}
⑤ 自检：{reasoning.self_check or '确保语气温和、不施压'}"""

    if extra_task_hint:
        enhanced_prompt += f"\n\n{extra_task_hint}"
    else:
        enhanced_prompt += f"\n\n请用{respond_style}的口吻回复。先接住情绪，再温和引导。短句为主，2-4段。"

    if rag_context:
        enhanced_prompt += (
            f"\n\n---\n以下是{rag_label}供参考（仅参考风格，不要照搬，严禁编造）：\n{rag_context}"
        )

    response = model_router.call(
        prompt=enhanced_prompt,
        task_type="emotional_empathy",
        system_prompt=system_prompt,
        max_tokens=300,
    )
    return reasoning, response
