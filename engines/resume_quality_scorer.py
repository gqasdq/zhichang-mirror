"""简历质量评分引擎（无 JD 模式）。"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from core.model_router import model_router
from core.privacy_filter import sanitize_resume_for_api


@dataclass
class ScoreExplanation:
    """单条可解释评分依据。"""

    dimension: str
    score: int
    original_text: str
    reason: str
    suggestion: str = ""

    def model_dump(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "score": self.score,
            "original_text": self.original_text,
            "reason": self.reason,
            "suggestion": self.suggestion,
        }


@dataclass
class ResumeQualityResult:
    star_score: int = 0
    star_details: list[dict[str, Any]] = field(default_factory=list)
    star_evidence: list[dict[str, Any]] = field(default_factory=list)
    quant_score: int = 0
    quant_details: list[dict[str, Any]] = field(default_factory=list)
    quant_evidence: list[dict[str, Any]] = field(default_factory=list)
    expression_score: int = 0
    expression_details: list[dict[str, Any]] = field(default_factory=list)
    expression_evidence: list[dict[str, Any]] = field(default_factory=list)
    explanations: list[dict[str, Any]] = field(default_factory=list)
    overall_score: float = 0.0
    quality_suggestion: str = ""
    raw_content: str = ""

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def compute_quality_score(
    star_score: int,
    quant_score: int,
    expression_score: int,
) -> float:
    """综合得分 = STAR×0.4 + 量化×0.3 + 表达规范×0.3"""
    return round(star_score * 0.4 + quant_score * 0.3 + expression_score * 0.3, 1)


def _clamp_score(value: Any, default: int = 50) -> int:
    try:
        score = int(float(value))
    except (TypeError, ValueError):
        return default
    return max(0, min(100, score))


def _extract_json(text: str) -> dict[str, Any]:
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


def _normalize_detail_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            entry = {
                "content": str(item.get("content", "")).strip(),
                "status": str(item.get("status", "")).strip(),
                "suggestion": item.get("suggestion"),
            }
            original_text = str(item.get("original_text", "")).strip()
            if original_text:
                entry["original_text"] = original_text
            result.append(entry)
    return result


def _normalize_evidence_list(value: Any) -> list[dict[str, Any]]:
    """解析 XAI 可解释性证据列表。"""
    if not isinstance(value, list):
        return []
    result: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        original_text = str(item.get("original_text", item.get("content", ""))).strip()
        if not original_text:
            continue
        result.append(
            {
                "original_text": original_text,
                "issue": str(item.get("issue", item.get("status", ""))).strip(),
                "suggestion": str(item.get("suggestion", "")).strip(),
            }
        )
    return result


def _build_explanations(
    star_score: int,
    quant_score: int,
    expression_score: int,
    star_evidence: list[dict[str, Any]],
    quant_evidence: list[dict[str, Any]],
    expression_evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """汇总为 ScoreExplanation 列表。"""
    items: list[dict[str, Any]] = []
    for ev in star_evidence:
        items.append(
            ScoreExplanation(
                dimension="STAR",
                score=star_score,
                original_text=str(ev.get("original_text", "")),
                reason=str(ev.get("issue", "")),
                suggestion=str(ev.get("suggestion", "")),
            ).model_dump()
        )
    for ev in quant_evidence:
        items.append(
            ScoreExplanation(
                dimension="量化",
                score=quant_score,
                original_text=str(ev.get("original_text", "")),
                reason=str(ev.get("issue", "")),
                suggestion=str(ev.get("suggestion", "")),
            ).model_dump()
        )
    for ev in expression_evidence:
        items.append(
            ScoreExplanation(
                dimension="表达",
                score=expression_score,
                original_text=str(ev.get("original_text", "")),
                reason=str(ev.get("issue", "")),
                suggestion=str(ev.get("suggestion", "")),
            ).model_dump()
        )
    return items


def _merge_evidence_into_details(
    details: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """将 evidence 中的 original_text 合并进 details，便于前端统一展示。"""
    if not evidence:
        return details
    merged = [dict(item) for item in details]
    used = set()
    for ev in evidence:
        original = ev.get("original_text", "")
        matched = False
        for item in merged:
            content = item.get("content", "")
            if original and (original in content or content in original):
                item.setdefault("original_text", original)
                if ev.get("issue"):
                    item.setdefault("issue", ev["issue"])
                matched = True
                used.add(original)
                break
        if not matched:
            merged.append(
                {
                    "content": original,
                    "original_text": original,
                    "status": ev.get("issue", ""),
                    "issue": ev.get("issue", ""),
                    "suggestion": ev.get("suggestion", ""),
                }
            )
    return merged


def _default_result(raw_content: str = "") -> ResumeQualityResult:
    return ResumeQualityResult(
        star_score=50,
        star_details=[],
        star_evidence=[],
        quant_score=50,
        quant_details=[],
        quant_evidence=[],
        expression_score=50,
        expression_details=[],
        expression_evidence=[],
        overall_score=50.0,
        quality_suggestion="评估暂不可用，请稍后重试。",
        raw_content=raw_content,
    )


_SYSTEM_PROMPT = (
    "你是一位资深简历优化师，请对以下简历进行质量评估，不参考任何岗位JD，仅评估简历本身的表达质量。"
    "请严格按 JSON 格式输出，不要添加任何解释性文字。"
    "关键要求（可解释 AI / XAI）："
    "1. 对每个评分维度，必须引用简历中的原文片段作为依据；"
    "2. star_evidence / quant_evidence / expression_evidence 各 1-4 条，"
    "每条含 original_text（简历原文）、issue（问题）、suggestion（改进建议）；"
    "3. 所有 suggestion 必须针对 original_text，不能泛泛而谈。"
    "评估三个维度："
    "1. STAR结构（40%权重）：检查每段经历描述是否包含情境(S)、任务(T)、行动(A)、结果(R)。"
    "常见问题：只写做了什么(A)，缺少为什么做(S/T)和结果(R)。"
    "2. 量化表达（30%权重）：检查成果描述是否包含具体数字/百分比/规模。"
    "3. 表达规范（30%权重）：检查用词是否专业，关注口语化、空话套话、逻辑结构。"
    "注意："
    "- 简历中已有数字（如'50+组数据''12城'）算已量化；"
    "- 只有动作数字没有结果数字，标记为 missing_R；"
    "- 表达规范不要苛求，只在明显口语化或明显空话时标记；"
    "- quality_suggestion 要具体、有可操作性；"
    "- overall_score 可省略，由系统计算。"
)


_USER_TEMPLATE = """请评估以下简历分析的质量，输出严格 JSON：

```json
{{
  "star_score": 65,
  "star_evidence": [
    {{"original_text": "负责项目管理", "issue": "缺少情境(S)和结果(R)", "suggestion": "补充：在XX项目中，通过XX方法，达成XX结果"}}
  ],
  "star_details": [
    {{"content": "经历描述", "status": "missing_R", "suggestion": "缺少量化结果(R)，建议补充具体成果", "original_text": "负责项目管理"}}
  ],
  "quant_score": 58,
  "quant_evidence": [
    {{"original_text": "优化了用户体验", "issue": "not_quantified", "suggestion": "建议补充：优化后XX指标提升XX%"}}
  ],
  "quant_details": [
    {{"content": "优化了用户体验", "status": "not_quantified", "suggestion": "建议补充：优化后XX指标提升XX%"}}
  ],
  "expression_score": 72,
  "expression_evidence": [
    {{"original_text": "熟练掌握Office", "issue": "hollow_claim", "suggestion": "空话套话，无佐证，建议删除或改为具体场景"}}
  ],
  "expression_details": [
    {{"content": "熟练掌握Office", "status": "hollow_claim", "suggestion": "空话套话，无佐证，建议删除或改为具体场景"}}
  ],
  "quality_suggestion": "针对最大提升空间给出50-120字可执行建议"
}}
```

要求：
- star_details / quant_details / expression_details 各 1-4 条，要具体
- star_evidence / quant_evidence / expression_evidence 必须引用简历原文
- expression status 如 colloquial / hollow_claim / structure_issue / complete
- quant status 为 quantified 或 not_quantified

【简历分析】
{resume_analysis}
"""


class ResumeQualityScorer:
    """简历质量评估引擎。"""

    def evaluate(self, resume_analysis: str) -> ResumeQualityResult:
        sanitized = sanitize_resume_for_api(resume_analysis)
        prompt = _USER_TEMPLATE.format(resume_analysis=sanitized)

        response = model_router.call(
            prompt=prompt,
            task_type="complex_analysis",
            system_prompt=_SYSTEM_PROMPT,
            temperature=0.3,
            max_tokens=2500,
        )

        return self._parse_response(response)

    def _parse_response(self, raw_content: str) -> ResumeQualityResult:
        data = _extract_json(raw_content)
        if not data:
            return _default_result(raw_content)

        star_score = _clamp_score(data.get("star_score"))
        quant_score = _clamp_score(data.get("quant_score"))
        expression_score = _clamp_score(data.get("expression_score"))
        overall_score = compute_quality_score(star_score, quant_score, expression_score)

        star_evidence = _normalize_evidence_list(data.get("star_evidence"))
        quant_evidence = _normalize_evidence_list(data.get("quant_evidence"))
        expression_evidence = _normalize_evidence_list(data.get("expression_evidence"))

        star_details = _merge_evidence_into_details(
            _normalize_detail_list(data.get("star_details")),
            star_evidence,
        )
        quant_details = _merge_evidence_into_details(
            _normalize_detail_list(data.get("quant_details")),
            quant_evidence,
        )
        expression_details = _merge_evidence_into_details(
            _normalize_detail_list(data.get("expression_details")),
            expression_evidence,
        )

        quality_suggestion = str(data.get("quality_suggestion", "")).strip()
        if not quality_suggestion:
            quality_suggestion = _default_result().quality_suggestion

        explanations = _build_explanations(
            star_score,
            quant_score,
            expression_score,
            star_evidence,
            quant_evidence,
            expression_evidence,
        )

        result = ResumeQualityResult(
            star_score=star_score,
            star_details=star_details,
            star_evidence=star_evidence,
            quant_score=quant_score,
            quant_details=quant_details,
            quant_evidence=quant_evidence,
            expression_score=expression_score,
            expression_details=expression_details,
            expression_evidence=expression_evidence,
            explanations=explanations,
            overall_score=overall_score,
            quality_suggestion=quality_suggestion,
            raw_content=raw_content,
        )

        result.raw_content = json.dumps(
            {
                "star_score": result.star_score,
                "star_details": result.star_details,
                "star_evidence": result.star_evidence,
                "quant_score": result.quant_score,
                "quant_details": result.quant_details,
                "quant_evidence": result.quant_evidence,
                "expression_score": result.expression_score,
                "expression_details": result.expression_details,
                "expression_evidence": result.expression_evidence,
                "explanations": result.explanations,
                "overall_score": result.overall_score,
                "quality_suggestion": result.quality_suggestion,
            },
            ensure_ascii=False,
        )
        return result
