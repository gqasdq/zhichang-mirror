"""
人才共情链核心引擎。

负责：
- 从 data/empathy 目录加载故事并按标签/关键词筛选
- 经 model_router 完成主匹配与故事详情追问（限流、重试、 failover）
- 兼容多种 JSON 返回格式并做异常兜底
- 读写 data/empathy/history.json 历史记录
"""

from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.model_router import model_router
from core.privacy_filter import sanitize_chat_for_api


_PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Config:
    """人才共情链引擎配置（路径与超时；API 经 model_router / api_gateway）。"""

    MAIN_PROMPT_PATH: Path = Path("prompts/empathy_master_main.txt")
    DETAIL_PROMPT_PATH: Path = Path("prompts/empathy_master_detail.txt")
    STORY_DIR: Path = Path("data/empathy")
    HISTORY_PATH: Path = Path("data/empathy/history.json")
    HARD_TIMEOUT_SECONDS: int = 120

    def resolve(self, path: Path) -> Path:
        return (_PROJECT_ROOT / path).resolve()


@dataclass
class Story:
    """单个故事。"""

    story_id: str = ""
    protagonist: str = ""
    starting_point: str = ""
    key_choice: str = ""
    year3: str = ""
    year5: str = ""
    one_word: str = ""
    tags: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    # 以下字段通常由模型主匹配流程补全
    title: str = ""
    similarity_reason: str = ""
    resonance: str = ""


@dataclass
class EmpathyReflection:
    """共情感悟。"""

    empathy_title: str = ""
    empathy_body: str = ""
    closing: str = ""


@dataclass
class EmpathyResult:
    """共情匹配结果。"""

    stories: List[Story] = field(default_factory=list)
    reflection: EmpathyReflection = field(default_factory=EmpathyReflection)
    raw_json: str = ""
    parse_error: str = ""
    matched_tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class HistoryManager:
    """历史记录读写。"""

    def __init__(self, config: Config) -> None:
        from core.session_manager import SessionManager

        self._history_path = SessionManager.user_file_path("empathy", "history.json")
        if not self._history_path.exists():
            self._history_path.write_text("[]", encoding="utf-8")

    def load(self) -> List[Dict[str, Any]]:
        try:
            data = json.loads(self._history_path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def append(self, item: Dict[str, Any], max_items: int = 50) -> None:
        records = self.load()
        records.append(item)
        self._history_path.write_text(
            json.dumps(records[-max_items:], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


class StoryLoader:
    """故事加载与筛选。"""

    def __init__(self, config: Config) -> None:
        self.config = config
        self._stories: List[Story] = []
        self._story_map: Dict[str, Story] = {}
        self.reload()

    def reload(self) -> None:
        story_dir = self.config.resolve(self.config.STORY_DIR)
        stories: List[Story] = []
        if story_dir.exists():
            for path in sorted(story_dir.glob("*.md")):
                stories.extend(self._parse_file(path))
        self._stories = stories
        self._story_map = {story.story_id: story for story in stories if story.story_id}

    def all_stories(self) -> List[Story]:
        return list(self._stories)

    def get_story(self, story_id: str) -> Optional[Story]:
        key = str(story_id or "").strip()
        return self._story_map.get(key)

    def select_related_stories(
        self, user_tags: List[str], user_description: str, min_count: int = 8, max_count: int = 12
    ) -> List[Story]:
        candidates = self._stories
        if not candidates:
            return []

        tag_set = set(self._normalize_tokens(" ".join(user_tags)))
        desc_terms = set(self._extract_keywords(user_description))
        query_terms = tag_set | desc_terms

        scored: List[tuple[int, Story]] = []
        for story in candidates:
            score = 0
            story_terms = set(self._story_terms(story))

            # 标签强匹配优先
            if tag_set:
                score += 3 * len(tag_set & set(self._normalize_tokens(" ".join(story.tags))))
            # 关键词匹配
            score += len(desc_terms & story_terms)
            # 文本包含（弱信号）
            haystack = " ".join(
                [
                    story.protagonist,
                    story.starting_point,
                    story.key_choice,
                    story.year3,
                    story.year5,
                    story.one_word,
                    " ".join(story.tags),
                    " ".join(story.keywords),
                ]
            ).lower()
            for term in query_terms:
                if len(term) >= 2 and term.lower() in haystack:
                    score += 1

            scored.append((score, story))

        scored.sort(key=lambda item: (item[0], item[1].story_id), reverse=True)
        ranked = [item[1] for item in scored]

        # 至少给到 min_count 条，最多 max_count 条
        picked = ranked[:max_count]
        if len(picked) < min_count:
            pool_ids = {s.story_id for s in picked}
            for story in ranked[max_count:]:
                if story.story_id in pool_ids:
                    continue
                picked.append(story)
                pool_ids.add(story.story_id)
                if len(picked) >= min_count:
                    break
        return picked[:max_count]

    def format_story_samples(self, stories: List[Story]) -> str:
        parts: List[str] = []
        for story in stories:
            lines = [
                f"【故事编号】{story.story_id}",
                f"【主角画像】{story.protagonist}",
                f"【起点状态】{story.starting_point}",
                f"【关键选择】{story.key_choice}",
                f"【3年后】{story.year3}",
                f"【5年后】{story.year5}",
                f"【一句话】{story.one_word}",
                f"【标签】{' '.join(story.tags)}",
                f"【关键词】{' '.join(story.keywords)}",
            ]
            parts.append("\n".join(lines))
        return "\n\n---\n\n".join(parts)

    def _parse_file(self, path: Path) -> List[Story]:
        content = path.read_text(encoding="utf-8", errors="ignore")
        stories: List[Story] = []
        current: Dict[str, str] = {}
        current_field: Optional[str] = None
        index = 0

        def flush() -> None:
            nonlocal current, index
            if not current:
                return
            index += 1
            story = self._to_story(current, path, index)
            if story:
                stories.append(story)
            current = {}

        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            kv = self._match_field(line)
            if kv:
                field_name, value = kv
                if field_name == "story_id":
                    flush()
                current[field_name] = value
                current_field = field_name
                continue

            if current_field and current:
                current[current_field] = f"{current.get(current_field, '')} {line}".strip()

        flush()
        return stories

    def _match_field(self, line: str) -> Optional[tuple[str, str]]:
        patterns = {
            "story_id": [
                r"^【?故事编号】?\s*[:：]?\s*(.+)$",
                r"^Story\s*ID\s*[:：]\s*(.+)$",
                r"^(S-\d+)\s*$",
            ],
            "protagonist": [r"^【?主角画像】?\s*[:：]?\s*(.+)$", r"^主角\s*[:：]\s*(.+)$"],
            "starting_point": [r"^【?起点状态】?\s*[:：]?\s*(.+)$", r"^起点\s*[:：]\s*(.+)$"],
            "key_choice": [r"^【?关键选择】?\s*[:：]?\s*(.+)$", r"^选择\s*[:：]\s*(.+)$"],
            "year3": [r"^【?3年后】?\s*[:：]?\s*(.+)$", r"^三年后\s*[:：]\s*(.+)$"],
            "year5": [r"^【?5年后】?\s*[:：]?\s*(.+)$", r"^五年后\s*[:：]\s*(.+)$"],
            "one_word": [r"^【?一句话(?:建议)?】?\s*[:：]?\s*(.+)$", r"^一句话\s*[:：]\s*(.+)$"],
            "tags": [r"^【?标签】?\s*[:：]?\s*(.+)$"],
            "keywords": [r"^【?关键词】?\s*[:：]?\s*(.+)$"],
            "title": [r"^【?标题】?\s*[:：]?\s*(.+)$"],
        }
        for field_name, regs in patterns.items():
            for reg in regs:
                match = re.match(reg, line, flags=re.IGNORECASE)
                if match:
                    return field_name, match.group(1).strip()
        return None

    def _to_story(self, raw: Dict[str, str], source_path: Path, index: int) -> Optional[Story]:
        if not raw:
            return None
        story_id = raw.get("story_id", "").strip() or f"{source_path.stem.upper()}-{index:03d}"
        tags = self._normalize_tokens(raw.get("tags", ""))
        keywords = self._normalize_tokens(raw.get("keywords", ""))
        if not keywords:
            keywords = self._extract_keywords(
                " ".join(
                    [
                        raw.get("protagonist", ""),
                        raw.get("starting_point", ""),
                        raw.get("key_choice", ""),
                        raw.get("one_word", ""),
                    ]
                )
            )
        return Story(
            story_id=story_id,
            protagonist=raw.get("protagonist", "").strip(),
            starting_point=raw.get("starting_point", "").strip(),
            key_choice=raw.get("key_choice", "").strip(),
            year3=raw.get("year3", "").strip(),
            year5=raw.get("year5", "").strip(),
            one_word=raw.get("one_word", "").strip(),
            tags=tags,
            keywords=keywords,
            title=raw.get("title", "").strip(),
        )

    def _story_terms(self, story: Story) -> List[str]:
        return self._extract_keywords(
            " ".join(
                [
                    story.protagonist,
                    story.starting_point,
                    story.key_choice,
                    story.year3,
                    story.year5,
                    story.one_word,
                    " ".join(story.tags),
                    " ".join(story.keywords),
                ]
            )
        )

    def _normalize_tokens(self, text: str) -> List[str]:
        if not text:
            return []
        text = text.replace("#", " ")
        parts = re.split(r"[\s,，、;/|]+", text)
        clean = []
        for part in parts:
            token = part.strip()
            if token and token not in clean:
                clean.append(token)
        return clean

    def _extract_keywords(self, text: str, limit: int = 20) -> List[str]:
        if not text:
            return []
        stopwords = {
            "的",
            "了",
            "和",
            "是",
            "我",
            "你",
            "他",
            "她",
            "也",
            "在",
            "有",
            "都",
            "就",
            "很",
            "一个",
            "我们",
            "他们",
            "以及",
            "因为",
            "所以",
        }
        words = re.findall(r"[\u4e00-\u9fffA-Za-z0-9_]+", text)
        result: List[str] = []
        for word in words:
            token = word.strip().lower()
            if len(token) < 2 or token in stopwords:
                continue
            if token not in result:
                result.append(token)
            if len(result) >= limit:
                break
        return result


def _extract_json_object(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return ""


def _safe_json_loads(content: str) -> Optional[Dict[str, Any]]:
    payload = (content or "").strip()
    if not payload:
        return None

    candidates = [payload]

    fence_json = re.search(r"```json\s*([\s\S]*?)\s*```", payload, re.IGNORECASE)
    if fence_json:
        candidates.append(fence_json.group(1).strip())

    fence_any = re.search(r"```\s*([\s\S]*?)\s*```", payload)
    if fence_any:
        candidates.append(fence_any.group(1).strip())

    extracted = _extract_json_object(payload)
    if extracted:
        candidates.append(extracted)

    for candidate in candidates:
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            continue
    return None


class EmpathyEngine:
    """人才共情链核心引擎。"""

    def __init__(self, config: Optional[Config] = None) -> None:
        self.config = config or Config()
        self.story_loader = StoryLoader(self.config)
        self.history = HistoryManager(self.config)
        self._main_prompt = self._read_prompt(self.config.MAIN_PROMPT_PATH)
        self._detail_prompt = self._read_prompt(self.config.DETAIL_PROMPT_PATH)

    def _read_prompt(self, relative_path: Path) -> str:
        path = self.config.resolve(relative_path)
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def _run_with_hard_timeout(self, func: Callable[[], Any], timeout_seconds: int = 120) -> Any:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(func)
            try:
                return future.result(timeout=timeout_seconds)
            except FuturesTimeoutError as exc:
                future.cancel()
                raise TimeoutError(f"API调用超过{timeout_seconds}秒，已中断") from exc

    def _build_main_prompt(self, user_tags: List[str], user_description: str, story_samples: str) -> str:
        template = self._main_prompt or (
            "你是同行者，请根据用户标签和处境匹配3-5个故事，输出JSON。\n"
            "标签：{user_tags}\n"
            "处境：{user_description}\n"
            "候选故事：\n{story_samples}"
        )
        tags_text = "、".join([str(tag).strip() for tag in user_tags if str(tag).strip()]) or "未选择标签"
        desc_text = str(user_description or "").strip() or "用户未提供详细描述"

        prompt = template
        prompt = prompt.replace("{story_samples}", story_samples)
        prompt = prompt.replace("{user_tags}", tags_text)
        prompt = prompt.replace("{user_description}", desc_text)
        # 兼容其他命名占位符
        prompt = prompt.replace("{story_pool}", story_samples)
        prompt = prompt.replace("{user_situation}", f"标签：{tags_text}\n处境：{desc_text}")
        prompt = prompt.replace("{user_input}", f"标签：{tags_text}\n处境：{desc_text}")
        return prompt

    def _build_detail_prompt(self, story_id: str, user_situation: str, story_basic: str) -> str:
        template = self._detail_prompt or (
            "你是同行者，请基于用户处境和故事信息讲述完整故事。\n"
            "故事ID：{story_id}\n"
            "用户处境：{user_situation}\n"
            "故事信息：\n{story_basic}\n"
            "时间：{timestamp}"
        )
        prompt = template
        prompt = prompt.replace("{story_id}", story_id)
        prompt = prompt.replace("{user_situation}", user_situation)
        prompt = prompt.replace("{story_basic}", story_basic)
        prompt = prompt.replace("{timestamp}", time.strftime("%Y-%m-%d %H:%M:%S"))
        return prompt

    def _fallback_payload(self, raw: str, error_text: str) -> Dict[str, Any]:
        return {
            "stories": [],
            "reflection": {
                "empathy_title": "同行者想说",
                "empathy_body": "我认真看到了你的处境。即使暂时没匹配到合适故事，你也不是一个人。",
                "closing": "你已经在寻找答案，这很重要。",
            },
            "parse_error": error_text,
            "raw_json": raw,
        }

    def _parse_result(self, content: str) -> EmpathyResult:
        payload = _safe_json_loads(content)
        parse_error = ""
        if payload is None:
            parse_error = "返回内容不是有效JSON，已进入兜底结构。"
            payload = self._fallback_payload(content, parse_error)

        stories_data = payload.get("stories", [])
        stories: List[Story] = []
        if isinstance(stories_data, list):
            for item in stories_data[:5]:
                if not isinstance(item, dict):
                    continue
                tags = item.get("tags", [])
                keywords = item.get("keywords", [])
                story = Story(
                    story_id=str(item.get("story_id", "")).strip(),
                    protagonist=str(item.get("protagonist", "")).strip(),
                    starting_point=str(item.get("starting_point", "")).strip(),
                    key_choice=str(item.get("key_choice", "")).strip(),
                    year3=str(item.get("year3", "")).strip(),
                    year5=str(item.get("year5", "")).strip(),
                    one_word=str(item.get("one_word", "")).strip(),
                    tags=[str(x).strip() for x in tags] if isinstance(tags, list) else [],
                    keywords=[str(x).strip() for x in keywords] if isinstance(keywords, list) else [],
                    title=str(item.get("title", "")).strip(),
                    similarity_reason=str(item.get("similarity_reason", "")).strip(),
                    resonance=str(item.get("resonance", "")).strip(),
                )
                stories.append(story)

        reflection_raw = payload.get("reflection", {})
        if not isinstance(reflection_raw, dict):
            reflection_raw = {}
        reflection = EmpathyReflection(
            empathy_title=str(reflection_raw.get("empathy_title", "同行者想说")).strip(),
            empathy_body=str(reflection_raw.get("empathy_body", "")).strip(),
            closing=str(reflection_raw.get("closing", "")).strip(),
        )

        return EmpathyResult(
            stories=stories,
            reflection=reflection,
            raw_json=content,
            parse_error=parse_error,
            matched_tags=[],
        )

    def match(self, user_tags: List[str], user_description: str) -> EmpathyResult:
        tags = [str(tag).strip() for tag in (user_tags or []) if str(tag).strip()]
        description = str(user_description or "").strip()

        selected_stories = self.story_loader.select_related_stories(tags, description, min_count=8, max_count=12)
        story_samples = self.story_loader.format_story_samples(selected_stories)
        sanitized_description = sanitize_chat_for_api(description)
        prompt = self._build_main_prompt(tags, sanitized_description, story_samples)

        def _api_call() -> str:
            return model_router.call(
                prompt=prompt,
                task_type="empathy_match",
                system_prompt="你是同行者，请严格输出JSON。",
                temperature=0.7,
                max_tokens=4000,
                timeout=float(self.config.HARD_TIMEOUT_SECONDS),
            )

        content = self._run_with_hard_timeout(
            _api_call,
            timeout_seconds=self.config.HARD_TIMEOUT_SECONDS,
        ).strip()
        result = self._parse_result(content)
        result.matched_tags = tags

        self.history.append(
            {
                "input": {"tags": tags, "description": description},
                "result": result.to_dict(),
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
        return result

    def get_story_detail(self, story_id: str, user_situation: str, story_basic: str) -> str:
        print(f"[DEBUG] get_story_detail called, story_id: {story_id}")
        sid = str(story_id or "").strip()
        situation = sanitize_chat_for_api(str(user_situation or "").strip())

        if story_basic:
            basic_text = str(story_basic)
        else:
            story = self.story_loader.get_story(sid)
            if story:
                basic_text = "\n".join([
                    f"故事编号: {story.story_id}",
                    f"主角画像: {story.protagonist}",
                    f"起点状态: {story.starting_point}",
                    f"关键选择: {story.key_choice}",
                    f"3年后: {story.year3}",
                    f"5年后: {story.year5}",
                    f"一句话: {story.one_word}",
                    f"标签: {' '.join(story.tags)}",
                ])
            else:
                basic_text = f"故事编号: {sid}"

        prompt = self._build_detail_prompt(sid, situation, basic_text)
        print(f"[DEBUG] detail prompt length: {len(prompt)}")

        def _api_call() -> str:
            print("[DEBUG] empathy_detail API call starting...")
            result = model_router.call(
                prompt=prompt,
                task_type="empathy_detail",
                system_prompt="你是同行者，请按模板输出。",
                temperature=0.8,
                max_tokens=2000,
                timeout=float(self.config.HARD_TIMEOUT_SECONDS),
            )
            print(f"[DEBUG] empathy_detail API call finished, length: {len(result)}")
            return result

        try:
            return self._run_with_hard_timeout(
                _api_call,
                timeout_seconds=self.config.HARD_TIMEOUT_SECONDS,
            ).strip()
        except Exception as exc:
            print(f"[DEBUG] get_story_detail failed: {repr(exc)}")
            return "我一时没回上来，能再说一遍吗？"
