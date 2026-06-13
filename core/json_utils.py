"""LLM 返回 JSON 的安全解析与常见格式修复。"""

from __future__ import annotations

import json
import re
from typing import Any


def _extract_json_object(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    match = re.search(r"\{[\s\S]*\}", text)
    return match.group(0) if match else ""


def _normalize_smart_quotes(text: str) -> str:
    return (
        text.replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\u2018", "'")
        .replace("\u2019", "'")
    )


def _escape_inner_quotes(json_str: str) -> str:
    """修复 JSON 字符串值内未转义的双引号（LLM 常见错误）。"""
    result: list[str] = []
    i = 0
    in_string = False
    escape = False
    closers = ":,}]"
    while i < len(json_str):
        ch = json_str[i]
        if escape:
            result.append(ch)
            escape = False
            i += 1
            continue
        if ch == "\\":
            result.append(ch)
            escape = True
            i += 1
            continue
        if ch == '"':
            if not in_string:
                in_string = True
                result.append(ch)
            else:
                j = i + 1
                while j < len(json_str) and json_str[j] in " \t\r\n":
                    j += 1
                if j < len(json_str) and json_str[j] in closers:
                    in_string = False
                    result.append(ch)
                else:
                    result.append('\\"')
            i += 1
            continue
        result.append(ch)
        i += 1
    return "".join(result)


def _remove_trailing_commas(json_str: str) -> str:
    return re.sub(r",(\s*[}\]])", r"\1", json_str)


def _repair_json_text(text: str) -> str:
    repaired = _normalize_smart_quotes(text.strip())
    repaired = _remove_trailing_commas(repaired)
    repaired = _escape_inner_quotes(repaired)
    return repaired


def _try_parse(candidate: str) -> dict[str, Any] | None:
    if not candidate:
        return None
    try:
        parsed = json.loads(candidate)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def safe_json_loads(content: str) -> dict[str, Any] | None:
    """从 LLM 输出中尽量解析 JSON 对象，含常见容错修复。"""
    payload = (content or "").strip()
    if not payload:
        return None

    candidates: list[str] = [payload]

    fence_json = re.search(r"```json\s*([\s\S]*?)\s*```", payload, re.IGNORECASE)
    if fence_json:
        candidates.append(fence_json.group(1).strip())

    fence_any = re.search(r"```\s*([\s\S]*?)\s*```", payload)
    if fence_any:
        candidates.append(fence_any.group(1).strip())

    extracted = _extract_json_object(payload)
    if extracted:
        candidates.append(extracted)

    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)

        parsed = _try_parse(candidate)
        if parsed is not None:
            return parsed

        repaired = _repair_json_text(candidate)
        if repaired != candidate:
            parsed = _try_parse(repaired)
            if parsed is not None:
                return parsed

    return None
