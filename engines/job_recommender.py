"""AI 岗位方向推荐引擎。"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from core.model_router import model_router
from core.privacy_filter import sanitize_resume_for_api

logger = logging.getLogger(__name__)


@dataclass
class JobRecommendation:
    title: str
    match_reason: str
    ability_match: list[str] = field(default_factory=list)
    ability_gap: list[str] = field(default_factory=list)
    salary_range: str = ""
    search_keyword: str = ""


@dataclass
class JobRecommendResult:
    recommendations: list[JobRecommendation] = field(default_factory=list)
    summary: str = ""


_SYSTEM_PROMPT = (
    "你是一位资深求职顾问，熟悉当前中国应届生就业市场。"
    "你的任务是根据求职者的简历，推荐 3-5 个最适合的岗位方向。"
    "请严格按 JSON 格式输出，不要添加任何解释性文字。"
)


_USER_TEMPLATE = """请根据以下简历信息，推荐 3-5 个最适合的应届生岗位方向，输出严格 JSON：

```json
{{
  "summary": "一句话总结推荐逻辑，如：你的经历偏向用户体验和数据分析，产品类和数据类岗位匹配度最高",
  "recommendations": [
    {{
      "title": "产品经理",
      "match_reason": "1-2句话说明为什么适合",
      "ability_match": ["用户调研", "跨团队协作", "数据分析"],
      "ability_gap": ["需求文档撰写", "竞品分析"],
      "salary_range": "8-15K",
      "search_keyword": "产品经理"
    }}
  ]
}}
```

要求：
- 推荐 3-5 个岗位，按匹配度从高到低排序
- salary_range 参考一线城市应届生合理水平（如 6-12K、8-15K），不要离谱
- search_keyword 是智联招聘搜索用的简短关键词，通常与岗位名称一致或略短
- ability_match / ability_gap 各 2-4 项，要具体、可理解
- 推荐应基于简历真实经历，不要编造简历里没有的能力
{match_section}
【简历内容】
{resume_text}
"""


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


def _normalize_string_list(value: Any, limit: int = 5) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            result.append(text)
    return result[:limit]


def _normalize_recommendation(item: Any) -> Optional[JobRecommendation]:
    if not isinstance(item, dict):
        return None

    title = str(item.get("title", "")).strip()
    if not title:
        return None

    search_keyword = str(item.get("search_keyword", "")).strip() or title
    return JobRecommendation(
        title=title,
        match_reason=str(item.get("match_reason", "")).strip(),
        ability_match=_normalize_string_list(item.get("ability_match")),
        ability_gap=_normalize_string_list(item.get("ability_gap")),
        salary_range=str(item.get("salary_range", "")).strip() or "面议",
        search_keyword=search_keyword,
    )


class JobRecommender:
    """根据简历分析结果推荐岗位方向。"""

    def recommend(
        self,
        resume_text: str,
        match_data: Optional[dict] = None,
    ) -> JobRecommendResult:
        prompt = self._build_prompt(resume_text, match_data)
        response = model_router.call(
            prompt=prompt,
            task_type="complex_analysis",
            system_prompt=_SYSTEM_PROMPT,
            temperature=0.4,
            max_tokens=2500,
        )
        return self._parse_response(response)

    def _build_prompt(self, resume_text: str, match_data: Optional[dict] = None) -> str:
        sanitized = sanitize_resume_for_api(resume_text)
        match_section = ""
        if match_data:
            matched = match_data.get("keyword_matched") or []
            missing = match_data.get("keyword_missing") or []
            if matched or missing:
                match_section = (
                    "\n【已有 JD 匹配参考】\n"
                    f"- 已匹配关键词：{'、'.join(matched[:8]) if matched else '无'}\n"
                    f"- 待补充关键词：{'、'.join(missing[:8]) if missing else '无'}\n"
                )

        return _USER_TEMPLATE.format(
            resume_text=sanitized,
            match_section=match_section,
        )

    def _parse_response(self, raw_content: str) -> JobRecommendResult:
        data = _extract_json(raw_content)
        if not data:
            logger.warning("[job_recommender] failed to parse JSON response")
            return JobRecommendResult()

        recommendations: list[JobRecommendation] = []
        for item in data.get("recommendations") or []:
            rec = _normalize_recommendation(item)
            if rec:
                recommendations.append(rec)

        recommendations = recommendations[:5]
        summary = str(data.get("summary", "")).strip()
        return JobRecommendResult(recommendations=recommendations, summary=summary)
