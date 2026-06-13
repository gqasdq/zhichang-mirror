"""
平行宇宙（镜语者）核心引擎。
"""

from __future__ import annotations

import functools
import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.config import get_settings
from core.constants import API_PARALLEL_TIMEOUT
from core.model_router import model_router
from core.privacy_filter import sanitize_chat_for_api


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
logger = logging.getLogger(__name__)


def _router_chat(
    *,
    prompt: str,
    task_type: str,
    system_prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    timeout: float | None = None,
) -> str:
    """经 model_router（网关限流 + 健康检查 + failover）调用 LLM。"""
    return model_router.call(
        prompt=prompt,
        task_type=task_type,
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
    )


def _extract_json_object(text: str) -> str:
    """从文本中尽量提取最外层JSON对象。"""
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]

    match = re.search(r"\{[\s\S]*\}", text)
    return match.group(0) if match else ""


def _safe_json_loads(raw: str) -> Optional[Dict[str, Any]]:
    payload = (raw or "").strip()
    if not payload:
        return None

    try:
        result = json.loads(payload)
        return result if isinstance(result, dict) else None
    except Exception:
        pass

    fence_json = re.search(r"```json\s*([\s\S]*?)\s*```", payload, re.IGNORECASE)
    if fence_json:
        try:
            result = json.loads(fence_json.group(1).strip())
            return result if isinstance(result, dict) else None
        except Exception:
            pass

    fence_any = re.search(r"```\s*([\s\S]*?)\s*```", payload)
    if fence_any:
        try:
            result = json.loads(fence_any.group(1).strip())
            return result if isinstance(result, dict) else None
        except Exception:
            pass

    extracted = _extract_json_object(payload)
    if extracted:
        try:
            result = json.loads(extracted)
            return result if isinstance(result, dict) else None
        except Exception:
            return None
    return None


@functools.lru_cache(maxsize=4)
def _read_prompt_file(filename: str) -> str:
    prompt_path = _PROJECT_ROOT / "prompts" / filename
    if not prompt_path.exists():
        return ""
    return prompt_path.read_text("utf-8")


def _normalize_parallel_result(data: Dict[str, Any]) -> Dict[str, Any]:
    def norm_mirror(name: str) -> Dict[str, Any]:
        source = data.get(name, {})
        if not isinstance(source, dict):
            source = {}
        year5 = source.get("year5", {})
        if not isinstance(year5, dict):
            year5 = {}
        year10 = source.get("year10", {})
        if not isinstance(year10, dict):
            year10 = {}
        turning_points = source.get("turning_points", [])
        if not isinstance(turning_points, list):
            turning_points = []
        risks = source.get("risks", [])
        if not isinstance(risks, list):
            risks = []
        return {
            "title": str(source.get("title", "")),
            "summary": str(source.get("summary", "")),
            "year5": {
                "position": str(year5.get("position", "")),
                "salary": str(year5.get("salary", "")),
                "location": str(year5.get("location", "")),
                "description": str(year5.get("description", "")),
            },
            "year10": {
                "position": str(year10.get("position", "")),
                "salary": str(year10.get("salary", "")),
                "description": str(year10.get("description", "")),
            },
            "turning_points": [
                {"year": str(tp.get("year", "")), "event": str(tp.get("event", ""))}
                for tp in turning_points
                if isinstance(tp, dict)
            ],
            "risks": [str(x) for x in risks],
            "data_source": str(source.get("data_source", "")),
        }

    return {
        "mirror_a": norm_mirror("mirror_a"),
        "mirror_b": norm_mirror("mirror_b"),
        "mirror_c": norm_mirror("mirror_c"),
        "insight": str(data.get("insight", "")),
    }


def call_deepseek(user_info: str) -> Dict[str, Any]:
    """
    调用DeepSeek完成镜语者主推演。
    """
    main_prompt = _read_prompt_file("mirror_master_main.txt")
    if not main_prompt:
        return {"error": "缺少主Prompt文件：prompts/mirror_master_main.txt"}

    settings = get_settings()
    if not settings.deepseek_api_key and not settings.zhipu_api_key:
        return {"error": "未配置 LLM API Key，请检查 .env"}

    sanitized = sanitize_chat_for_api(user_info)
    try:
        content = _router_chat(
            prompt=sanitized,
            task_type="future_projection",
            system_prompt=main_prompt,
            temperature=0.7,
            max_tokens=3000,
            timeout=API_PARALLEL_TIMEOUT,
        )
    except Exception as exc:
        logger.exception("call_deepseek api failed: %s", str(exc))
        return {"error": f"推演调用失败：{exc}"}

    parsed = _safe_json_loads(content)
    if not parsed:
        logger.error("call_deepseek parse failed, raw content: %s", content[:1200])
        return {"error": "推演结果解析失败，请重试"}
    return _normalize_parallel_result(parsed)


def call_zhipu_followup(
    card_info: Dict[str, Any],
    user_worry: str,
    user_revealed: str,
    user_answer: str = "",
    user_resume_raw: str = "",
    mirror_titles: str = "未知",
) -> str:
    """
    调用智谱完成翻牌追问。
    """
    try:
        followup_prompt = _read_prompt_file("mirror_master_followup.txt")
        if not followup_prompt:
            return "我一时没回上来，能再说一遍吗？"
        followup_prompt = followup_prompt.replace("{mirror_titles}", mirror_titles or "未知")

        settings = get_settings()
        if not settings.deepseek_api_key and not settings.zhipu_api_key:
            return "我一时没回上来，能再说一遍吗？"

        prompt_type = str(card_info.get("prompt_type", "")).strip()
        title = str(card_info.get("title", "")).strip()
        prompt_type = "expand" if prompt_type == "expand_a" else prompt_type

        short_questions = {
            "regret": "你在说现在纠结的时候，我想知道——你有没有想过，当初如果选了那条路，现在会怎样？",
            "fear": "你说你在纠结，其实我想知道——你最怕的事情是什么？",
            "dream": "你说你在两个选择之间纠结，但我好奇——如果你内心真的想做一件事，那件事是什么？",
        }
        if prompt_type in short_questions and not user_answer.strip():
            return short_questions[prompt_type]

        if not user_resume_raw.strip():
            try:
                import streamlit as st  # 延迟导入，避免核心模块强依赖UI

                user_resume_raw = str(st.session_state.get("parallel_resume_text", "")).strip()
            except Exception:
                user_resume_raw = ""

        sanitized_worry = sanitize_chat_for_api(user_worry or "")
        sanitized_revealed = sanitize_chat_for_api(user_revealed or "")
        sanitized_answer = sanitize_chat_for_api(user_answer or "")
        sanitized_resume = sanitize_chat_for_api(user_resume_raw or "")

        user_parts = [
            f"当前牌类型：{prompt_type}",
            f"当前牌标题：{title}",
            f"用户纠结：{sanitized_worry or '未提供'}",
            f"已透露信息：{sanitized_revealed or '暂无'}",
        ]
        if sanitized_resume.strip():
            user_parts.append(f"用户简历原文：\n{sanitized_resume.strip()}")
        if sanitized_answer.strip():
            user_parts.append(f"用户回答：{sanitized_answer.strip()}")
            user_parts.append("请先理解回答，再给200字以内洞察。")
        elif prompt_type in {"expand", "fourth"}:
            user_parts.append("这是直出牌，请直接给出结果，不要先提问。")

        user_parts.append(
            "严格遵循系统Prompt中对应牌面规则输出，保持镜语者风格，正文输出，不要额外解释。"
        )

        content = _router_chat(
            prompt="\n".join(user_parts),
            task_type="parallel_followup",
            system_prompt=followup_prompt,
            temperature=0.8,
            max_tokens=500,
            timeout=15.0,
        )
        return content or "我一时没回上来，能再说一遍吗？"
    except Exception as exc:
        logger.exception(
            "call_zhipu_followup failed: prompt_type=%s, card_title=%s, worry_len=%s, revealed_len=%s, answer_len=%s, resume_len=%s, err=%s",
            str(card_info.get("prompt_type", "")),
            str(card_info.get("title", "")),
            len(user_worry or ""),
            len(user_revealed or ""),
            len(user_answer or ""),
            len(user_resume_raw or ""),
            str(exc),
        )
        return "我一时没回上来，能再说一遍吗？"


def call_deepseek_followup(
    card_type: str,
    user_worry: str = "",
    mirror_a_title: str = "",
    mirror_a_summary: str = "",
    user_resume_raw: str = "",
    mirror_titles: str = "",
    user_revealed_info: str = "",
) -> str:
    """
    用DeepSeek处理牌4/牌5追问（深度推演）。
    """
    followup_prompt = _read_prompt_file("mirror_master_followup.txt")
    if not followup_prompt:
        return BRANCH_STORY_FALLBACK_MSG

    settings = get_settings()
    if not settings.deepseek_api_key and not settings.zhipu_api_key:
        return BRANCH_STORY_FALLBACK_MSG

    try:
        sanitized_worry = sanitize_chat_for_api(user_worry or "")
        sanitized_resume = sanitize_chat_for_api(user_resume_raw or "")
        sanitized_revealed = sanitize_chat_for_api(user_revealed_info or "")

        system_prompt = (
            followup_prompt.replace("{mirror_titles}", mirror_titles or "未知")
            .replace("{mirror_a_title}", mirror_a_title or "")
            .replace("{mirror_a_summary}", mirror_a_summary or "")
            .replace("{user_worry}", sanitized_worry or "未提供")
            .replace("{user_revealed_info}", sanitized_revealed or "暂无")
        )
        system_prompt += (
            f"\n\n重要：用户本次只翻牌{card_type}，只输出该牌面对应的内容，不要输出其他牌面。"
        )

        base_user_context = "\n\n".join(
            [
                f"用户纠结：{sanitized_worry or '未提供'}",
                f"用户简历原文：{sanitized_resume or '用户未提供简历原文'}",
            ]
        )
        if card_type == "expand":
            user_message = f"【本次执行：牌4——展开镜面A的完整5年路径】\n\n{base_user_context}"
        elif card_type == "fourth":
            user_message = f"【本次执行：牌5——有没有第四种可能】\n\n{base_user_context}"
        else:
            user_message = f"【本次执行：{card_type}】\n\n{base_user_context}"

        content = _router_chat(
            prompt=user_message,
            task_type="future_projection",
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=3000,
            timeout=15.0,
        )
        return content or "我一时没回上来，能再说一遍吗？"
    except Exception as exc:
        logger.exception(
            "call_deepseek_followup failed: card_type=%s, mirror_titles=%s, err=%s",
            card_type,
            mirror_titles,
            str(exc),
        )
        return "我一时没回上来，能再说一遍吗？"


@dataclass
class ParallelConfig:
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    zhipu_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    zhipu_model: str = "glm-4-flash"
    prompts_dir: Path = Path("prompts")
    main_prompt_file: str = "mirror_master_main.txt"
    followup_prompt_file: str = "mirror_master_followup.txt"
    history_file: Path = Path("data/parallel/history.json")
    max_history: int = 50
    deepseek_api_key: str = ""
    zhipu_api_key: str = ""

    def __post_init__(self) -> None:
        self.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        self.zhipu_api_key = os.getenv("ZHIPU_API_KEY", "").strip()


@dataclass
class UserProfile:
    worry: str = ""
    resume_text: str = ""
    education: str = ""
    major: str = ""
    skills: List[str] = field(default_factory=list)

    def to_text(self) -> str:
        sections = [f"【用户纠结的核心】\n{self.worry.strip()}"]
        if self.resume_text.strip():
            sections.append("【用户现状】")
            if self.education:
                sections.append(f"学历：{self.education}")
            if self.major:
                sections.append(f"专业：{self.major}")
            if self.skills:
                sections.append(f"技能：{', '.join(self.skills[:8])}")
            sections.append(self.resume_text.strip())
        return "\n".join(sections)


@dataclass
class MirrorPath:
    title: str = ""
    summary: str = ""
    year5: Dict[str, str] = field(default_factory=dict)
    year10: Dict[str, str] = field(default_factory=dict)
    turning_points: List[Dict[str, str]] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    data_source: str = ""


@dataclass
class ParallelResult:
    mirror_a: MirrorPath = field(default_factory=MirrorPath)
    mirror_b: MirrorPath = field(default_factory=MirrorPath)
    mirror_c: MirrorPath = field(default_factory=MirrorPath)
    insight: str = ""
    raw_json: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mirror_a": {
                "title": self.mirror_a.title,
                "summary": self.mirror_a.summary,
                "year5": self.mirror_a.year5,
                "year10": self.mirror_a.year10,
                "turning_points": self.mirror_a.turning_points,
                "risks": self.mirror_a.risks,
                "data_source": self.mirror_a.data_source,
            },
            "mirror_b": {
                "title": self.mirror_b.title,
                "summary": self.mirror_b.summary,
                "year5": self.mirror_b.year5,
                "year10": self.mirror_b.year10,
                "turning_points": self.mirror_b.turning_points,
                "risks": self.mirror_b.risks,
                "data_source": self.mirror_b.data_source,
            },
            "mirror_c": {
                "title": self.mirror_c.title,
                "summary": self.mirror_c.summary,
                "year5": self.mirror_c.year5,
                "year10": self.mirror_c.year10,
                "turning_points": self.mirror_c.turning_points,
                "risks": self.mirror_c.risks,
                "data_source": self.mirror_c.data_source,
            },
            "insight": self.insight,
        }


class ResumeParser:
    EDUCATION_KEYWORDS = ["博士", "硕士", "本科", "大专", "专科"]
    MAJOR_KEYWORDS = ["计算机", "软件", "电子", "机械", "土木", "建筑", "金融", "市场", "自动化", "数学", "统计"]
    SKILL_KEYWORDS = [
        "Python",
        "Java",
        "SQL",
        "AI",
        "机器学习",
        "深度学习",
        "运营",
        "直播",
        "ArcGIS",
        "BIM",
        "产品",
    ]

    def parse(self, text: str) -> Dict[str, Any]:
        return _parse_resume_text(text)


class HistoryManager:
    def __init__(self, config: Optional[ParallelConfig] = None) -> None:
        from core.session_manager import SessionManager

        self.config = config or ParallelConfig()
        self.history_file = SessionManager.user_file_path("parallel", "history.json")
        if not self.history_file.exists():
            self.history_file.write_text("[]", "utf-8")

    def load(self) -> List[Dict[str, Any]]:
        try:
            content = self.history_file.read_text("utf-8").strip()
            if not content:
                return []
            data = json.loads(content)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def save(self, history: List[Dict[str, Any]]) -> None:
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        self.history_file.write_text(
            json.dumps(history[-self.config.max_history :], ensure_ascii=False, indent=2),
            "utf-8",
        )


class ParallelEngine:
    FOLLOWUP_QUESTIONS = {
        "regret": "你在说现在纠结的时候，我想知道——你有没有想过，当初如果选了那条路，现在会怎样？",
        "fear": "你说你在纠结，其实我想知道——你最怕的事情是什么？",
        "dream": "你说你在两个选择之间纠结，但我好奇——如果你内心真的想做一件事，那件事是什么？",
    }

    def __init__(self, config: Optional[ParallelConfig] = None) -> None:
        self.config = config or ParallelConfig()
        self._main_prompt = _read_prompt_file(self.config.main_prompt_file)
        self._followup_prompt = _read_prompt_file(self.config.followup_prompt_file)

    def _load_prompt(self, filename: str) -> str:
        prompt_path = self.config.prompts_dir / filename
        if prompt_path.exists():
            return prompt_path.read_text("utf-8")
        return ""

    def generate(self, user_profile: UserProfile) -> ParallelResult:
        data = call_deepseek(user_profile.to_text())
        if "error" in data:
            raise ValueError(str(data.get("error", "推演失败")))
        return ParallelResult(
            mirror_a=self._to_mirror(data.get("mirror_a", {})),
            mirror_b=self._to_mirror(data.get("mirror_b", {})),
            mirror_c=self._to_mirror(data.get("mirror_c", {})),
            insight=str(data.get("insight", "")),
            raw_json=json.dumps(data, ensure_ascii=False),
        )

    def get_followup_question(self, prompt_type: str) -> str:
        return self.FOLLOWUP_QUESTIONS.get(prompt_type, "")

    def flip_card(
        self,
        prompt_type: str,
        card_title: str,
        user_worry: str,
        user_revealed_info: str,
        user_answer: str = "",
        mirror_a_text: str = "",
        user_resume_raw: str = "",
        mirror_titles: str = "未知",
        mirror_a_title: str = "",
        mirror_a_summary: str = "",
    ) -> str:
        try:
            revealed = user_revealed_info or ""
            if mirror_a_text:
                revealed = f"{revealed}\n镜面A摘要：{mirror_a_text}".strip()
            normalized_type = "expand" if prompt_type == "expand_a" else prompt_type
            if normalized_type in {"regret", "fear", "dream"}:
                return call_zhipu_followup(
                    card_info={"prompt_type": normalized_type, "title": card_title},
                    user_worry=user_worry,
                    user_revealed=revealed,
                    user_answer=user_answer,
                    user_resume_raw=user_resume_raw,
                    mirror_titles=mirror_titles,
                )

            return call_deepseek_followup(
                card_type=normalized_type,
                user_worry=user_worry,
                mirror_titles=mirror_titles,
                mirror_a_title=mirror_a_title,
                mirror_a_summary=mirror_a_summary or mirror_a_text,
                user_resume_raw=user_resume_raw,
                user_revealed_info=revealed,
            )
        except Exception as exc:
            logger.exception(
                "flip_card failed: prompt_type=%s, card_title=%s, err=%s",
                prompt_type,
                card_title,
                str(exc),
            )
            return "我一时没回上来，能再说一遍吗？"

    def _parse_main_result(self, content: str) -> ParallelResult:
        data = _safe_json_loads(content)
        if data is None:
            raise ValueError("无法解析镜语者返回JSON，请重试。")
        data = _normalize_parallel_result(data)

        return ParallelResult(
            mirror_a=self._to_mirror(data.get("mirror_a", {})),
            mirror_b=self._to_mirror(data.get("mirror_b", {})),
            mirror_c=self._to_mirror(data.get("mirror_c", {})),
            insight=str(data.get("insight", "")).strip(),
        )

    @staticmethod
    def _to_mirror(data: Dict[str, Any]) -> MirrorPath:
        if not isinstance(data, dict):
            return MirrorPath()
        return MirrorPath(
            title=str(data.get("title", "")),
            summary=str(data.get("summary", "")),
            year5=data.get("year5", {}) if isinstance(data.get("year5", {}), dict) else {},
            year10=data.get("year10", {}) if isinstance(data.get("year10", {}), dict) else {},
            turning_points=data.get("turning_points", []) if isinstance(data.get("turning_points", []), list) else [],
            risks=data.get("risks", []) if isinstance(data.get("risks", []), list) else [],
            data_source=str(data.get("data_source", "")),
        )


_engine: Optional[ParallelEngine] = None
_resume_parser: Optional[ResumeParser] = None


def _parse_resume_text(text: str) -> Dict[str, Any]:
    source = (text or "").strip()
    parsed: Dict[str, Any] = {"raw_text": source, "education": "", "major": "", "skills": []}
    if not source:
        return parsed

    for kw in ResumeParser.EDUCATION_KEYWORDS:
        if kw in source:
            parsed["education"] = kw
            break

    for kw in ResumeParser.MAJOR_KEYWORDS:
        if kw in source:
            parsed["major"] = kw
            break

    for kw in ResumeParser.SKILL_KEYWORDS:
        if kw in source and kw not in parsed["skills"]:
            parsed["skills"].append(kw)
    return parsed


def get_engine() -> ParallelEngine:
    global _engine
    if _engine is None:
        _engine = ParallelEngine()
    return _engine


def get_resume_parser() -> ResumeParser:
    global _resume_parser
    if _resume_parser is None:
        _resume_parser = ResumeParser()
    return _resume_parser


def parse_resume(text: str) -> Dict[str, Any]:
    return get_resume_parser().parse(text)


STORY_CHOICE_SYSTEM_APPEND = """
在故事的大约1/3和2/3处，各设置一个选择节点。每个节点给出2个选项。
输出格式：在需要选择的节点处，用以下格式标记：
[CHOICE_POINT]
选项A: [描述]
选项B: [描述]
[/CHOICE_POINT]
选择节点之前的故事正常输出，选择节点之后的故事等用户选择后再生成。
"""

BRANCH_STORY_FALLBACK_MSG = "我一时没回上来，能再说一遍吗？"
_BRANCH_STORY_CONTINUE_MAX_HISTORY = 8000
_BRANCH_STORY_RESUME_MAX = 2500
_YEAR2_START_PATTERN = re.compile(
    r"(?:【第2年】|##\s*第2年|#+\s*第2年)",
    re.IGNORECASE,
)


def is_branch_story_fallback(text: str) -> bool:
    return (text or "").strip() == BRANCH_STORY_FALLBACK_MSG


def _truncate_for_branch_story(text: str, limit: int) -> str:
    cleaned = (text or "").strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit] + "\n...(后文省略)..."


def _build_branch_story_system_prompt(
    *,
    mirror_a_title: str,
    mirror_a_summary: str,
    user_worry: str,
    phase_hint: str = "",
) -> str:
    template = _read_prompt_file("mirror_branch_story.txt")
    if not template:
        template = (
            "你是镜语者，为用户展开镜面A「{mirror_a_title}」的5年分支故事。"
            "用户纠结：{user_worry}。摘要：{mirror_a_summary}。"
            + STORY_CHOICE_SYSTEM_APPEND
        )
    prompt = (
        template.replace("{mirror_a_title}", mirror_a_title or "未知路径")
        .replace("{mirror_a_summary}", mirror_a_summary or "暂无摘要")
        .replace("{user_worry}", user_worry or "未提供")
    )
    if phase_hint:
        prompt += f"\n\n【本次续写要求】\n{phase_hint}"
    return prompt


def normalize_branch_story_start(raw: str) -> str:
    """首段若误写了第2年及之后，截断到第1年后再保留选择节点。"""
    parsed = parse_choice_point(raw)
    if not parsed["has_choice"]:
        return raw

    story_before = parsed["story_before"]
    extra_year = _YEAR2_START_PATTERN.search(story_before)
    if extra_year:
        story_before = story_before[: extra_year.start()].strip()

    return (
        f"{story_before}\n\n[CHOICE_POINT]\n"
        f"选项A: {parsed['option_a']}\n"
        f"选项B: {parsed['option_b']}\n"
        f"[/CHOICE_POINT]"
    )


def _call_branch_story_llm(
    *,
    system_prompt: str,
    user_message: str,
    max_tokens: int = 2200,
) -> str:
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            content = _router_chat(
                prompt=user_message,
                task_type="parallel_story",
                system_prompt=system_prompt,
                temperature=0.7,
                max_tokens=max_tokens,
                timeout=API_PARALLEL_TIMEOUT,
            )
            if content and not is_branch_story_fallback(content):
                return content
        except Exception as exc:
            last_error = exc
            logger.warning(
                "branch story LLM attempt %s failed: %s",
                attempt + 1,
                str(exc),
            )
    if last_error:
        logger.exception("branch story LLM failed after retries: %s", str(last_error))
    return BRANCH_STORY_FALLBACK_MSG


def parse_choice_point(text: str) -> Dict[str, Any]:
    content = text or ""
    patterns = (
        re.compile(
            r"\[CHOICE_POINT\]\s*选项A\s*[:：]\s*(.*?)\s*选项B\s*[:：]\s*(.*?)\s*\[/CHOICE_POINT\]",
            re.DOTALL | re.IGNORECASE,
        ),
        re.compile(
            r"\[CHOICE_POINT\]\s*选项A\s*[:：]\s*(.*?)\s*选项B\s*[:：]\s*(.*?)\s*$",
            re.DOTALL | re.IGNORECASE,
        ),
        re.compile(
            r"\[CHOICE_POINT\]\s*A\s*[:：]\s*(.*?)\s*B\s*[:：]\s*(.*?)\s*(?:\[/CHOICE_POINT\]|$)",
            re.DOTALL | re.IGNORECASE,
        ),
    )
    for pattern in patterns:
        match = pattern.search(content)
        if match:
            return {
                "has_choice": True,
                "story_before": content[: match.start()].strip(),
                "option_a": match.group(1).strip(),
                "option_b": match.group(2).strip(),
            }
    return {
        "has_choice": False,
        "story_before": content.strip(),
        "option_a": "",
        "option_b": "",
    }


def generate_branch_story_start(
    user_worry: str = "",
    mirror_a_title: str = "",
    mirror_a_summary: str = "",
    user_resume_raw: str = "",
    mirror_titles: str = "",
    user_revealed_info: str = "",
) -> str:
    """生成故事首段，在第一个选择节点前停止。"""
    if not get_settings().deepseek_api_key:
        return BRANCH_STORY_FALLBACK_MSG

    sanitized_worry = sanitize_chat_for_api(user_worry or "")
    sanitized_resume = _truncate_for_branch_story(
        sanitize_chat_for_api(user_resume_raw or ""),
        _BRANCH_STORY_RESUME_MAX,
    )

    system_prompt = _build_branch_story_system_prompt(
        mirror_a_title=mirror_a_title,
        mirror_a_summary=mirror_a_summary,
        user_worry=sanitized_worry,
        phase_hint=(
            "这是分支故事第1段。只输出【第1年】正文，然后在第一个 [CHOICE_POINT] 标记处结束。"
            "禁止输出第2年及之后的内容。"
        ),
    )
    user_message = "\n\n".join(
        [
            "【牌4 · 分支故事第1段】",
            f"用户纠结：{sanitized_worry or '未提供'}",
            f"用户简历（节选）：{sanitized_resume or '用户未提供简历原文'}",
            "请开始写第1年故事，并在第一个选择节点处停止。",
        ]
    )

    raw = _call_branch_story_llm(system_prompt=system_prompt, user_message=user_message, max_tokens=1800)
    if is_branch_story_fallback(raw):
        return raw
    return normalize_branch_story_start(raw)


def generate_branch_story_continue(
    story_parts: List[str],
    choices: List[Dict[str, Any]],
    chosen_side: str,
    chosen_label: str,
    user_worry: str = "",
    mirror_a_title: str = "",
    mirror_a_summary: str = "",
    user_resume_raw: str = "",
    mirror_titles: str = "",
    user_revealed_info: str = "",
) -> str:
    """用户做出选择后续写故事。"""
    _ = user_revealed_info, user_resume_raw, mirror_titles  # 续写依赖已写故事，不重复传简历
    if not get_settings().deepseek_api_key:
        return BRANCH_STORY_FALLBACK_MSG

    choice_count = len(choices)
    if choice_count >= 2:
        phase_hint = (
            "这是最后一次续写。请写【第4-5年】并给出【镜语者说】作为结局，"
            "不要再添加 [CHOICE_POINT]。"
        )
    else:
        phase_hint = (
            "这是第2段续写。请写【第2年】【第3年】，"
            "在第二个 [CHOICE_POINT] 标记（含标记）后停止，不要写标记之后的内容。"
        )

    sanitized_worry = sanitize_chat_for_api(user_worry or "")
    history = "\n\n".join(story_parts).strip()
    if len(history) > _BRANCH_STORY_CONTINUE_MAX_HISTORY:
        history = "...(前文省略)...\n" + history[-_BRANCH_STORY_CONTINUE_MAX_HISTORY :]
    choice_history = "\n".join(
        f"选择{idx + 1}: {item.get('label', '')}" for idx, item in enumerate(choices)
    )

    system_prompt = _build_branch_story_system_prompt(
        mirror_a_title=mirror_a_title,
        mirror_a_summary=mirror_a_summary,
        user_worry=sanitized_worry,
        phase_hint=phase_hint,
    )
    user_message = "\n\n".join(
        [
            "【分支故事续写】",
            f"镜面A：{mirror_a_title or '未知'}",
            f"路径摘要：{mirror_a_summary or '暂无'}",
            f"已写故事：\n{history}",
            f"已做选择：\n{choice_history}",
            f"本次选择：{chosen_side} — {chosen_label}",
            "请沿该选择继续发展故事，保持镜语者叙事风格。",
        ]
    )

    return _call_branch_story_llm(system_prompt=system_prompt, user_message=user_message, max_tokens=2400)
