"""简历板块 AI 优化引擎。"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from core.model_router import model_router
from core.privacy_filter import sanitize_resume_for_api
from utils.emotion_adapter import EmotionAdapter, normalize_emotion_state

logger = logging.getLogger(__name__)


@dataclass
class OptimizationResult:
    optimized_content: str = ""
    changes: list[dict] = field(default_factory=list)
    optimize_types: list[str] = field(default_factory=list)
    success: bool = True
    error_message: str = ""


def _extract_json(text: str) -> dict:
    if not text:
        return {}

    cleaned = text.strip()
    if "```json" in cleaned:
        cleaned = cleaned.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in cleaned:
        cleaned = cleaned.split("```", 1)[1].split("```", 1)[0].strip()

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    return {}


class ResumeOptimizer:
    """接收板块原文 + JD + 情绪状态，返回优化结果。"""

    def optimize_section(
        self,
        section_name: str,
        original: str,
        jd: str = "",
        emotion_state: str = "平稳",
    ) -> OptimizationResult:
        original = (original or "").strip()
        if not original:
            return OptimizationResult(
                optimized_content="",
                changes=[],
                optimize_types=[],
                success=False,
                error_message="该板块暂无内容，请先填写或从其他板块补充。",
            )

        prompt = self._build_prompt(section_name, original, jd, emotion_state)
        emotion = normalize_emotion_state(emotion_state)
        adapter = EmotionAdapter(emotion)
        base_system = (
            "你是一位资深简历优化师，擅长用STAR法则改写经历描述、量化成果、嵌入关键词。"
            "只输出严格JSON，不要输出任何JSON以外的内容。"
        )
        system_prompt = f"{base_system}\n\n{adapter.get_system_prompt_suffix()}"
        try:
            response = model_router.call(
                prompt=prompt,
                task_type="complex_analysis",
                system_prompt=system_prompt,
                temperature=0.5,
                max_tokens=2500,
            )
            return self._parse_response(response, original)
        except Exception as exc:
            logger.warning("[ResumeOptimizer] optimize failed: %s", exc)
            return OptimizationResult(
                optimized_content=original,
                changes=[],
                optimize_types=[],
                success=False,
                error_message="优化暂时不可用，请稍后重试",
            )

    def _build_prompt(
        self,
        section_name: str,
        original_content: str,
        jd_content: str,
        emotion_state: str,
    ) -> str:
        sanitized_original = sanitize_resume_for_api(original_content)
        sanitized_jd = sanitize_resume_for_api(jd_content) if jd_content else "（无）"

        return f"""
你是一位资深简历优化师。请对以下简历板块进行优化。

## 当前板块：{section_name}
## 原始内容：
{sanitized_original}

## 目标岗位JD（如有）：
{sanitized_jd}

## 优化要求：
1. 如果经历描述不符合STAR法则（情境-任务-行动-结果），请按STAR结构改写，用【S】【T】【A】【R】标注每一部分
2. 所有成果描述必须包含量化数据（数字/百分比/规模），遵循下方「量化数据规则」
3. 如果有JD，自然地嵌入JD中的关键词
4. 替换口语化表述为专业术语（"参与了"→"负责"，"帮忙了"→"协助"）
5. 保持真实性，绝不编造虚假经历或凭空捏造不存在的项目

## 量化数据规则（非常重要）：
- 如果原文已有具体数字（如"50+组数据"），保留，不加⚠️
- 如果原文没有数字，你基于上下文估算了一个数字，必须在数字后面加⚠️
- ⚠️格式：数字后面紧跟⚠️符号，如"提升30%⚠️""降低22%⚠️"
- 用户会看到这些⚠️标记并确认，所以估算要合理，不要编离谱的数字
- 示例：原文"优化了用户体验" → 优化为"用户满意度提升30%⚠️"（30%是估算，需确认）

## 情绪状态：{normalize_emotion_state(emotion_state)}
- 请严格遵循 system 指令中的语气要求

## 输出格式（严格JSON，不要输出任何JSON以外的内容）：
{{
  "optimized_content": "优化后的完整文本（保持原有换行）",
  "changes": [
    {{
      "type": "STAR补全|量化改写|关键词嵌入|去口语化|逻辑重组",
      "original": "原文中被修改的片段",
      "optimized": "优化后的片段",
      "reason": "修改原因（一句话）"
    }}
  ],
  "optimize_types": ["STAR补全", "量化改写"]
}}
"""

    def _parse_response(self, raw: str, original: str) -> OptimizationResult:
        data = _extract_json(raw)
        if not data or not data.get("optimized_content"):
            logger.warning("[ResumeOptimizer] invalid JSON response")
            return OptimizationResult(
                optimized_content=original,
                changes=[],
                optimize_types=[],
                success=False,
                error_message="优化暂时不可用，请稍后重试",
            )

        changes = data.get("changes") or []
        if not isinstance(changes, list):
            changes = []

        optimize_types = data.get("optimize_types") or []
        if not isinstance(optimize_types, list):
            optimize_types = []

        normalized_changes: list[dict] = []
        for item in changes:
            if isinstance(item, dict):
                normalized_changes.append(item)

        normalized_types = [str(t) for t in optimize_types if t]

        return OptimizationResult(
            optimized_content=str(data.get("optimized_content", "")).strip(),
            changes=normalized_changes,
            optimize_types=normalized_types,
            success=True,
        )
