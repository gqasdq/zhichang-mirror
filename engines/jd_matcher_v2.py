"""JD 三维匹配评分引擎 v2。"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from core.model_router import model_router
from core.privacy_filter import sanitize_resume_for_api
from core.few_shot_retriever import retrieve_few_shot_text


@dataclass
class JDMatchResult:
    """三维 JD 匹配结果。"""

    keyword_score: int = 0
    keyword_matched: list[str] = field(default_factory=list)
    keyword_missing: list[str] = field(default_factory=list)
    star_score: int = 0
    star_details: list[dict[str, Any]] = field(default_factory=list)
    quant_score: int = 0
    quant_details: list[dict[str, Any]] = field(default_factory=list)
    overall_score: float = 0.0
    smart_suggestion: str = ""
    raw_content: str = ""

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def compute_overall_score(keyword_score: int, star_score: int, quant_score: int) -> float:
    """综合得分 = 关键词×0.4 + STAR×0.3 + 量化×0.3"""
    return round(keyword_score * 0.4 + star_score * 0.3 + quant_score * 0.3, 1)


def _clamp_score(value: Any, default: int = 50) -> int:
    try:
        score = int(float(value))
    except (TypeError, ValueError):
        return default
    return max(0, min(100, score))


def _extract_json(text: str) -> dict[str, Any]:
    """从 LLM 响应中提取 JSON，失败时返回空 dict。"""
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


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = str(item).strip()
        if text and text not in result:
            result.append(text)
    return result


def _normalize_detail_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    result: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            result.append(
                {
                    "content": str(item.get("content", "")).strip(),
                    "status": str(item.get("status", "")).strip(),
                    "suggestion": item.get("suggestion"),
                }
            )
    return result


def _default_result(raw_content: str = "") -> JDMatchResult:
    return JDMatchResult(
        keyword_score=50,
        keyword_matched=[],
        keyword_missing=[],
        star_score=50,
        star_details=[],
        quant_score=50,
        quant_details=[],
        overall_score=50.0,
        smart_suggestion="暂无法生成详细建议，请稍后重试或补充更完整的 JD 与简历内容。",
        raw_content=raw_content,
    )


_MATCH_SYSTEM_PROMPT = (
    "你是一位岗位匹配分析师。请严格按 JSON 格式输出，不要添加任何解释性文字。"
    "评分维度说明："
    "1) keyword_score：JD 硬技能与软技能关键词在简历中的覆盖率（0-100）；"
    "2) star_score：经历描述符合 STAR 法则的比例（0-100）；"
    "3) quant_score：成果描述包含量化数据的比例（0-100）。"
    "你只负责提取与判断，overall_score 可省略，由系统计算。"
)


_MATCH_USER_TEMPLATE = """请分析以下简历分析与岗位 JD 的匹配情况，输出严格 JSON：

```json
{{
  "keyword_score": 82,
  "keyword_matched": ["关键词1", "关键词2"],
  "keyword_missing": ["缺失关键词1"],
  "star_score": 65,
  "star_details": [
    {{"content": "经历描述", "status": "missing_S_R", "suggestion": "缺少情境(S)和结果(R)"}}
  ],
  "quant_score": 58,
  "quant_details": [
    {{"content": "成果描述", "status": "not_quantified", "suggestion": "建议补充量化数据"}}
  ],
  "smart_suggestion": "针对差距给出可执行建议，50-120字"
}}
```

要求：
- keyword_matched / keyword_missing 各 2-6 条，要具体
- star_details 列出 1-4 段需改写的经历，status 如 complete / missing_S / missing_R / missing_S_R
- quant_details 列出 1-4 条，status 为 quantified 或 not_quantified
- smart_suggestion 要有实质内容，指出最大差距与改进方向

【简历分析】
{resume_analysis}

【岗位 JD】
{job_description}
"""


class JDMatcherV2:
    """三维 JD 匹配引擎（仅在有 JD 时调用）。"""

    def match(self, resume_analysis: str, job_description: str) -> JDMatchResult:
        sanitized_analysis = sanitize_resume_for_api(resume_analysis)
        sanitized_jd = sanitize_resume_for_api(job_description)

        few_shot_examples = retrieve_few_shot_text(
            f"{sanitized_jd}\n{sanitized_analysis}",
            module="matcher",
            top_k=3,
            header="以下是相似岗位的过往优质匹配分析样例，请参考其分析思路，针对当前简历与 JD 输出 JSON：",
        )

        prompt = _MATCH_USER_TEMPLATE.format(
            resume_analysis=sanitized_analysis,
            job_description=sanitized_jd,
        )
        if few_shot_examples and few_shot_examples != "（暂无相似优质样例）":
            prompt = f"## 动态优质匹配样例\n{few_shot_examples}\n\n{prompt}"

        response = model_router.call(
            prompt=prompt,
            task_type="complex_analysis",
            system_prompt=_MATCH_SYSTEM_PROMPT,
            temperature=0.3,
            max_tokens=2500,
        )

        return self._parse_response(response)

    def _parse_response(self, raw_content: str) -> JDMatchResult:
        data = _extract_json(raw_content)
        if not data:
            return _default_result(raw_content)

        keyword_score = _clamp_score(data.get("keyword_score"))
        star_score = _clamp_score(data.get("star_score"))
        quant_score = _clamp_score(data.get("quant_score"))
        overall_score = compute_overall_score(keyword_score, star_score, quant_score)

        smart_suggestion = str(data.get("smart_suggestion", "")).strip()
        if not smart_suggestion:
            smart_suggestion = _default_result().smart_suggestion

        result = JDMatchResult(
            keyword_score=keyword_score,
            keyword_matched=_normalize_string_list(data.get("keyword_matched")),
            keyword_missing=_normalize_string_list(data.get("keyword_missing")),
            star_score=star_score,
            star_details=_normalize_detail_list(data.get("star_details")),
            quant_score=quant_score,
            quant_details=_normalize_detail_list(data.get("quant_details")),
            overall_score=overall_score,
            smart_suggestion=smart_suggestion,
            raw_content=raw_content,
        )

        result.raw_content = json.dumps(
            {
                "match_score": int(round(overall_score)),
                "keyword_score": result.keyword_score,
                "keyword_matched": result.keyword_matched,
                "keyword_missing": result.keyword_missing,
                "star_score": result.star_score,
                "star_details": result.star_details,
                "quant_score": result.quant_score,
                "quant_details": result.quant_details,
                "overall_score": result.overall_score,
                "smart_suggestion": result.smart_suggestion,
            },
            ensure_ascii=False,
        )
        return result
