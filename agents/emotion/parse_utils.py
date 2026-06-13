import json
import re
from typing import Any


def extract_json_payload(text: str) -> dict[str, Any] | None:
    """从模型输出中提取JSON对象。"""
    source = (text or "").strip()
    if not source:
        return None

    # 1) 整段即JSON
    try:
        loaded = json.loads(source)
        if isinstance(loaded, dict):
            return loaded
    except Exception:
        pass

    # 2) ```json ... ``` 代码块
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", source, flags=re.IGNORECASE)
    if fence:
        block = fence.group(1).strip()
        try:
            loaded = json.loads(block)
            if isinstance(loaded, dict):
                return loaded
        except Exception:
            pass

    # 3) 提取首个平衡大括号对象
    start = source.find("{")
    if start == -1:
        return None

    depth = 0
    end = -1
    for idx in range(start, len(source)):
        ch = source[idx]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = idx
                break

    if end == -1:
        return None

    maybe_json = source[start : end + 1]
    try:
        loaded = json.loads(maybe_json)
        if isinstance(loaded, dict):
            return loaded
    except Exception:
        return None

    return None


def as_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def as_str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str):
        txt = value.strip()
        if not txt:
            return []
        return [txt]
    return []


def extract_natural_response(text: str) -> str:
    """从模型输出中提取给用户看的自然语言，兼容 JSON 兜底。"""
    raw = (text or "").strip()
    if not raw:
        return raw

    if not raw.startswith("{") and "natural_language_response" not in raw:
        return raw

    data = extract_json_payload(raw)
    if not data:
        return raw

    for key in ("natural_language_response", "content", "response", "text"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()

    blocks = data.get("content_blocks")
    if isinstance(blocks, list):
        parts: list[str] = []
        for block in blocks:
            if isinstance(block, dict):
                content = block.get("content")
                if isinstance(content, str) and content.strip():
                    parts.append(content.strip())
        if parts:
            segments: list[str] = []
            opening = data.get("opening")
            if isinstance(opening, str) and opening.strip():
                segments.append(opening.strip())
            segments.extend(parts)
            closing = data.get("closing")
            if isinstance(closing, str) and closing.strip():
                segments.append(closing.strip())
            return "\n\n".join(segments)

    return raw
