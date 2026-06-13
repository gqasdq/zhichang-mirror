"""职业成长路径引擎 — 基于简历与基因数据推演发展路径。"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from core.model_router import model_router
from core.privacy_filter import sanitize_resume_for_api

logger = logging.getLogger(__name__)


@dataclass
class LevelInfo:
    level: int
    title: str
    salary_range: str


@dataclass
class GrowthPath:
    path_name: str
    is_primary: bool = False
    match_stars: int = 3
    current_level: int = 1
    levels: list[LevelInfo] = field(default_factory=list)
    skills_met: list[str] = field(default_factory=list)
    skills_gap: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    path_match_reason: str = ""


@dataclass
class CareerPathResult:
    paths: list[GrowthPath] = field(default_factory=list)
    summary: str = ""
    error: bool = False


_SYSTEM_PROMPT = (
    "你是一位资深职业规划师，熟悉2025-2026年中国应届生就业市场。"
    "你的任务是根据求职者的简历和职业基因，推演2-3条未来3-5年的职业发展路径。"
    "关注成长潜力而非当前可投递岗位，输出严格JSON，不要输出JSON以外的内容。"
)


_USER_TEMPLATE = """请根据以下简历和基因信息，生成2-3条职业发展成长路径，输出严格JSON：

```json
{{
  "summary": "一句话总结，如：你的空间思维与数据敏感基因组合，GIS开发和数据分析两条路径成长空间最大",
  "paths": [
    {{
      "path_name": "GIS开发方向",
      "is_primary": true,
      "match_stars": 4,
      "current_level": 2,
      "path_match_reason": "专业对口，空间思维基因突出",
      "levels": [
        {{"level": 1, "title": "实习生", "salary_range": "6-8K"}},
        {{"level": 2, "title": "初级", "salary_range": "8-12K"}},
        {{"level": 3, "title": "中级", "salary_range": "12-18K"}},
        {{"level": 4, "title": "高级", "salary_range": "18-25K"}},
        {{"level": 5, "title": "专家", "salary_range": "25K+"}}
      ],
      "skills_met": ["空间思维Lv.4（已达标）", "数据敏感Lv.3（已达标）"],
      "skills_gap": [
        "编程能力：需掌握Python+至少1个GIS开发框架",
        "项目经验：需1个以上完整GIS应用开发项目"
      ],
      "actions": [
        "学一个GIS开发框架（推荐Mapbox/Leaflet/GeoServer）",
        "做一个完整的GIS小项目放到GitHub（如疫情地图/房产热力图）",
        "刷3-5道LeetCode空间算法题"
      ]
    }}
  ]
}}
```

要求：
- 生成2-3条路径，按匹配度从高到低排序，第一条设 is_primary=true
- match_stars 为1-5整数
- current_level 为用户当前所在级别（1-5），基于简历经历客观判断
- levels 必须恰好5级，salary_range 参考一线城市应届生合理市场价（2025-2026）
- skills_gap 要具体可执行，不说"提升编程能力"这种空话
- actions 恰好3条，用户看完知道第一步做什么
- 这是成长路径推演，不是岗位投递推荐，不要输出招聘搜索关键词
{gene_section}
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


def _normalize_string_list(value: Any, limit: int = 6) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()][:limit]


def _normalize_level(item: Any) -> Optional[LevelInfo]:
    if not isinstance(item, dict):
        return None
    try:
        level = int(item.get("level", 0))
    except (TypeError, ValueError):
        return None
    title = str(item.get("title", "")).strip()
    if not title or level < 1:
        return None
    return LevelInfo(
        level=level,
        title=title,
        salary_range=str(item.get("salary_range", "")).strip() or "面议",
    )


def _build_gene_section(gene_data: Optional[dict]) -> str:
    if not gene_data:
        return ""

    lines = ["\n## 职业基因分析结果："]
    combo = gene_data.get("基因组合分析") or {}
    if isinstance(combo, dict) and combo.get("组合名称"):
        lines.append(f"- 基因组合：{combo.get('组合名称', '')} / {combo.get('核心基因型', '')}")
        if combo.get("组合优势"):
            lines.append(f"- 组合优势：{combo.get('组合优势', '')}")

    for gene in gene_data.get("显性基因") or []:
        if not isinstance(gene, dict):
            continue
        name = gene.get("基因名称", "")
        level = gene.get("等级", "")
        reason = str(gene.get("等级判定理由", "")).strip()[:80]
        lines.append(f"- {name} Lv.{level}：{reason}")

    hidden = gene_data.get("隐藏基因") or []
    for gene in hidden[:2]:
        if isinstance(gene, dict) and gene.get("基因名称"):
            lines.append(
                f"- 隐藏基因 {gene.get('基因名称')} Lv.{gene.get('推断等级', '')}"
            )

    return "\n".join(lines) + "\n" if len(lines) > 1 else ""


class CareerPathEngine:
    """根据简历 + 基因数据生成成长路径。"""

    def generate(
        self,
        resume_text: str,
        gene_data: Optional[dict] = None,
    ) -> CareerPathResult:
        prompt = self._build_prompt(resume_text, gene_data)
        try:
            response = model_router.call(
                prompt=prompt,
                task_type="complex_analysis",
                system_prompt=_SYSTEM_PROMPT,
                temperature=0.45,
                max_tokens=3500,
            )
            return self._parse_response(response)
        except Exception as exc:
            logger.warning("[career_path_engine] generate failed: %s", exc)
            return CareerPathResult(error=True)

    def _build_prompt(self, resume_text: str, gene_data: Optional[dict] = None) -> str:
        sanitized = sanitize_resume_for_api(resume_text)
        gene_section = _build_gene_section(gene_data)
        return _USER_TEMPLATE.format(resume_text=sanitized, gene_section=gene_section)

    def _parse_response(self, raw_content: str) -> CareerPathResult:
        data = _extract_json(raw_content)
        if not data:
            logger.warning("[career_path_engine] failed to parse JSON")
            return CareerPathResult(error=True)

        paths: list[GrowthPath] = []
        for item in data.get("paths") or []:
            if not isinstance(item, dict):
                continue
            path_name = str(item.get("path_name", "")).strip()
            if not path_name:
                continue

            levels: list[LevelInfo] = []
            for level_item in item.get("levels") or []:
                level_info = _normalize_level(level_item)
                if level_info:
                    levels.append(level_info)
            levels.sort(key=lambda x: x.level)
            if len(levels) < 5:
                continue

            try:
                match_stars = max(1, min(5, int(item.get("match_stars", 3))))
            except (TypeError, ValueError):
                match_stars = 3
            try:
                current_level = max(1, min(5, int(item.get("current_level", 1))))
            except (TypeError, ValueError):
                current_level = 1

            paths.append(
                GrowthPath(
                    path_name=path_name,
                    is_primary=bool(item.get("is_primary", False)),
                    match_stars=match_stars,
                    current_level=current_level,
                    levels=levels[:5],
                    skills_met=_normalize_string_list(item.get("skills_met")),
                    skills_gap=_normalize_string_list(item.get("skills_gap")),
                    actions=_normalize_string_list(item.get("actions"), limit=3),
                    path_match_reason=str(item.get("path_match_reason", "")).strip(),
                )
            )

        if not paths:
            return CareerPathResult(error=True)

        if not any(p.is_primary for p in paths):
            paths[0].is_primary = True

        paths = paths[:3]
        summary = str(data.get("summary", "")).strip()
        return CareerPathResult(paths=paths, summary=summary)
