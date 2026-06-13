"""简历结构化解析器 — 将纯文本简历拆分为板块。"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from core.model_router import model_router
from core.privacy_filter import sanitize_resume_for_api

logger = logging.getLogger(__name__)

SECTION_KEYS = (
    "basic_info",
    "objective",
    "education",
    "work_exp",
    "project_exp",
    "skills",
    "self_eval",
)

HEADER_PATTERNS: dict[str, list[str]] = {
    "basic_info": [r"基本信息", r"个人信息", r"个人资料"],
    "objective": [r"求职意向", r"期望职位", r"求职目标"],
    "education": [r"教育背景", r"教育经历", r"学历", r"学习经历"],
    "work_exp": [r"工作经历", r"实习经历", r"工作经验", r"职业经历", r"实践经历"],
    "project_exp": [r"项目经历", r"项目经验", r"项目实践", r"科研项目"],
    "skills": [r"专业技能", r"技能特长", r"核心技能", r"掌握技能", r"技能证书"],
    "self_eval": [r"自我评价", r"个人评价", r"自我描述"],
}


@dataclass
class ParsedResume:
    sections: dict[str, str] = field(default_factory=dict)
    raw_text: str = ""


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


def _count_filled_sections(sections: dict[str, str]) -> int:
    return sum(1 for key in SECTION_KEYS if str(sections.get(key, "")).strip())


def sections_look_monolithic(sections: dict[str, str]) -> bool:
    """判断是否几乎所有内容都堆在一个板块（正则切分失败）。"""
    if _count_filled_sections(sections) >= 2:
        return False
    basic = str(sections.get("basic_info", "")).strip()
    return len(basic) > 120


def _regex_split_by_markers(text: str) -> dict[str, str] | None:
    """在连续文本中按板块标题切分（标题与正文可能在同一行）。"""
    markers: list[tuple[int, str, int]] = []
    for key, patterns in HEADER_PATTERNS.items():
        for pattern in patterns:
            for match in re.finditer(
                rf"(?:^|[\n\r]|\s)({pattern})\s*[:：]",
                text,
                re.MULTILINE | re.IGNORECASE,
            ):
                markers.append((match.start(1), key, match.end()))
            for match in re.finditer(
                rf"^[ \t]*({pattern})\s*[#*\s】]*\s*$",
                text,
                re.MULTILINE | re.IGNORECASE,
            ):
                markers.append((match.start(1), key, match.end()))

    if len(markers) < 2:
        return None

    markers.sort(key=lambda item: item[0])
    deduped: list[tuple[int, str, int]] = []
    seen_keys_at: dict[str, int] = {}
    for start, key, end in markers:
        if key in seen_keys_at and start - seen_keys_at[key] < 8:
            continue
        seen_keys_at[key] = start
        deduped.append((start, key, end))
    markers = deduped
    if len(markers) < 2:
        return None

    sections: dict[str, str] = {key: "" for key in SECTION_KEYS}
    pre = text[: markers[0][0]].strip()
    if pre:
        sections["basic_info"] = pre

    for i, (_start, key, header_end) in enumerate(markers):
        chunk_end = markers[i + 1][0] if i + 1 < len(markers) else len(text)
        chunk = text[header_end:chunk_end].strip()
        if not chunk:
            continue
        if sections[key]:
            sections[key] = f"{sections[key]}\n{chunk}"
        else:
            sections[key] = chunk

    return sections if _count_filled_sections(sections) >= 2 else None


def _regex_fallback(resume_text: str) -> dict[str, str]:
    """按常见标题关键词切分；失败时全文放入 basic_info。"""
    text = (resume_text or "").strip()
    if not text:
        return {key: "" for key in SECTION_KEYS}

    lines = text.splitlines()
    sections: dict[str, str] = {key: "" for key in SECTION_KEYS}
    current_key = "basic_info"
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer, current_key
        content = "\n".join(buffer).strip()
        if content:
            if sections[current_key]:
                sections[current_key] = f"{sections[current_key]}\n{content}"
            else:
                sections[current_key] = content
        buffer = []

    for line in lines:
        stripped = line.strip()
        matched_key = None
        for key, patterns in HEADER_PATTERNS.items():
            for pattern in patterns:
                if re.match(rf"^[#*\s【】]*{pattern}\s*[#*\s】]*[:：]?\s*$", stripped, re.I):
                    matched_key = key
                    break
                if re.match(rf"^[#*\s【】]*{pattern}\s*[#*\s】]*[:：]", stripped, re.I):
                    matched_key = key
                    remainder = re.sub(
                        rf"^[#*\s【】]*{pattern}\s*[#*\s】]*[:：]\s*",
                        "",
                        stripped,
                        flags=re.I,
                    )
                    flush()
                    current_key = key
                    buffer = [remainder] if remainder else []
                    break
            if matched_key:
                break

        if matched_key:
            continue

        buffer.append(line)

    flush()

    if _count_filled_sections(sections) < 2:
        marker_sections = _regex_split_by_markers(text)
        if marker_sections:
            return marker_sections

    if not any(sections.values()):
        sections["basic_info"] = text

    return sections


def _classify_paragraph(block: str) -> str:
    """按关键词将段落归类到板块（无标题简历兜底）。"""
    text = block.strip()
    if not text:
        return "basic_info"
    if re.search(r"求职意向|期望职位|求职目标|目标岗位", text):
        return "objective"
    if re.search(r"自我评价|个人评价|自我描述|个人综述", text):
        return "self_eval"
    if re.search(r"项目经历|项目经验|项目实践|挑战杯|项目名称|科研课题", text):
        return "project_exp"
    if re.search(r"专业技能|技能特长|核心技能|掌握技能|软件技能|技能证书", text):
        return "skills"
    if re.search(
        r"工作经历|实习经历|工作经验|职业经历|实践经历|"
        r"(?:有限)?公司|研究院|事务所|集团|实习|助理|工程师|"
        r"任职|岗位职责",
        text,
    ):
        return "work_exp"
    if re.search(
        r"教育背景|教育经历|学习经历|学历|毕业院校|"
        r"(?:大学|学院|学校|专科|本科|硕士|博士|学士|GPA|"
        r"地理信息|计算机|工商管理|人力资源管理)",
        text,
    ) and not re.search(r"项目经历|挑战杯", text):
        return "education"
    if re.search(r"熟悉|精通|掌握|熟练使用|具备.*能力", text) and re.search(
        r"SPSS|Python|SQL|Office|Excel|CAD|ArcGIS|Java|C\+\+|英语|四级|六级",
        text,
        re.I,
    ):
        return "skills"
    if re.search(r"1[3-9]\d{9}|@[\w.-]+\.\w+|电话|邮箱|性别|年龄|\d{1,2}岁", text):
        if len(text) <= 180 and not re.search(r"大学|学院|公司|项目|负责|参与", text):
            return "basic_info"
    return "basic_info"


def _append_section(sections: dict[str, str], key: str, chunk: str) -> None:
    chunk = chunk.strip()
    if not chunk:
        return
    if sections[key]:
        sections[key] = f"{sections[key]}\n{chunk}"
    else:
        sections[key] = chunk


def _heuristic_by_paragraphs(text: str) -> dict[str, str]:
    sections: dict[str, str] = {key: "" for key in SECTION_KEYS}
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    if len(blocks) <= 1:
        blocks = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for block in blocks:
        key = _classify_paragraph(block)
        _append_section(sections, key, block)
    return sections


def _heuristic_by_inline_anchors(text: str) -> dict[str, str]:
    """在连续正文中按强特征词切分。"""
    anchor_rules: list[tuple[str, str]] = [
        ("objective", r"求职意向|期望职位|求职目标"),
        ("education", r"教育背景|教育经历|学习经历|学历"),
        ("work_exp", r"工作经历|实习经历|工作经验|职业经历"),
        ("project_exp", r"项目经历|项目经验|项目实践|挑战杯"),
        ("skills", r"专业技能|技能特长|核心技能|掌握技能"),
        ("self_eval", r"自我评价|个人评价|自我描述"),
    ]
    markers: list[tuple[int, str, int]] = []
    for key, pattern in anchor_rules:
        for match in re.finditer(pattern, text, re.I):
            markers.append((match.start(), key, match.end()))

    # 无显式标题时，用学校/公司/项目等实体词作锚点
    implicit_rules: list[tuple[str, str]] = [
        ("education", r"[\u4e00-\u9fa5]{2,12}(?:大学|学院|学校|专科学校)"),
        ("work_exp", r"[\u4e00-\u9fa5]{2,20}(?:公司|集团|研究院|事务所|测绘|科技)(?:[\u4e00-\u9fa9]{0,8})?"),
        ("project_exp", r"(?:挑战杯|互联网\+|(?:智能|立体|停车|管理).{0,6}系统|项目(?:名称|背景)?[:：])"),
        ("skills", r"(?:熟悉|掌握|精通)(?:\s*[/、及和与])?\s*(?:SPSS|Python|SQL|Office|ArcGIS|CAD|Java)"),
        ("self_eval", r"(?:具备|拥有).{0,8}(?:沟通|协调|管理|学习|团队).{0,8}能力|性格(?:沉稳|开朗)"),
    ]
    for key, pattern in implicit_rules:
        for match in re.finditer(pattern, text, re.I):
            pos = match.start()
            if any(abs(pos - m[0]) < 6 for m in markers):
                continue
            markers.append((pos, key, match.start()))

    if len(markers) < 2:
        return {key: "" for key in SECTION_KEYS}

    markers.sort(key=lambda item: item[0])
    sections: dict[str, str] = {key: "" for key in SECTION_KEYS}
    first_start = markers[0][0]
    if first_start > 0:
        sections["basic_info"] = text[:first_start].strip()

    for i, (start, key, header_end) in enumerate(markers):
        end = markers[i + 1][0] if i + 1 < len(markers) else len(text)
        chunk = text[header_end:end].strip() or text[start:end].strip()
        _append_section(sections, key, chunk)

    return sections


def heuristic_split_resume(text: str) -> dict[str, str]:
    """
    无明确板块标题时的内容启发式拆分。
    依次尝试：标题锚点 → 段落分类 → 行内实体锚点。
    """
    raw = (text or "").strip()
    if not raw:
        return {key: "" for key in SECTION_KEYS}

    marker_sections = _regex_split_by_markers(raw)
    if marker_sections and _count_filled_sections(marker_sections) >= 2:
        return marker_sections

    line_sections = _regex_fallback(raw)
    if _count_filled_sections(line_sections) >= 2:
        return line_sections

    paragraph_sections = _heuristic_by_paragraphs(raw)
    if _count_filled_sections(paragraph_sections) >= 2 and not sections_look_monolithic(paragraph_sections):
        return paragraph_sections

    inline_sections = _heuristic_by_inline_anchors(raw)
    if _count_filled_sections(inline_sections) >= 2:
        return inline_sections

    if _count_filled_sections(paragraph_sections) >= 1:
        return paragraph_sections

    return line_sections if any(line_sections.values()) else {**{key: "" for key in SECTION_KEYS}, "basic_info": raw}


class ResumeParser:
    """用 AI 解析简历为结构化板块，失败时正则兜底。"""

    def parse_fast(self, resume_text: str) -> ParsedResume:
        """本地正则切分，不调用 LLM（跨模块跳转等需要即时展示的场景）。"""
        raw_text = (resume_text or "").strip()
        if not raw_text:
            return ParsedResume(sections={key: "" for key in SECTION_KEYS}, raw_text="")
        return ParsedResume(sections=_regex_fallback(raw_text), raw_text=raw_text)

    def parse(self, resume_text: str) -> ParsedResume:
        raw_text = (resume_text or "").strip()
        if not raw_text:
            return ParsedResume(sections={key: "" for key in SECTION_KEYS}, raw_text="")

        sanitized = sanitize_resume_for_api(raw_text)
        prompt = f"""
请将以下简历文本解析为结构化板块。输出严格JSON格式，不要输出任何JSON以外的内容。

简历文本：
{sanitized}

输出格式：
{{
  "basic_info": "基本信息内容（姓名、电话、邮箱等）",
  "objective": "求职意向内容（如果没有则为空字符串）",
  "education": "教育背景内容",
  "work_exp": "工作经历内容（如果没有实习/工作经历则为空字符串）",
  "project_exp": "项目经历内容（如果没有则为空字符串）",
  "skills": "专业技能内容",
  "self_eval": "自我评价内容（如果没有则为空字符串）"
}}

注意：
- 每个字段保留原文，不要改写
- 如果某个板块在简历中不存在，填空字符串
- 保持原有的换行和格式
"""

        try:
            response = model_router.call(
                prompt=prompt,
                task_type="quick_summary",
                system_prompt="你是一个简历解析器，只做结构化拆分，不改写内容。",
                temperature=0.2,
                max_tokens=3000,
            )
            return self._parse_response(raw_text, response)
        except Exception as exc:
            logger.warning("[ResumeParser] AI parse failed: %s", exc)
            return ParsedResume(sections=_regex_fallback(raw_text), raw_text=raw_text)

    def _parse_response(self, raw_text: str, response: str) -> ParsedResume:
        data = _extract_json(response)
        if not data:
            logger.warning("[ResumeParser] JSON extract failed, using regex fallback")
            return ParsedResume(sections=_regex_fallback(raw_text), raw_text=raw_text)

        sections: dict[str, str] = {}
        for key in SECTION_KEYS:
            value = data.get(key, "")
            sections[key] = str(value).strip() if value is not None else ""

        if not any(sections.values()):
            sections = _regex_fallback(raw_text)

        if sections_look_monolithic(sections):
            logger.info("[ResumeParser] monolithic result, applying heuristic split")
            sections = heuristic_split_resume(raw_text)

        return ParsedResume(sections=sections, raw_text=raw_text)
