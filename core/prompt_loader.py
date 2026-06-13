"""Prompt 加载器 — 支持版本号与缓存。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from core.constants import PROMPT_VERSION

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_PROMPTS_DIR = _PROJECT_ROOT / "prompts"


@lru_cache(maxsize=64)
def load_prompt(relative_path: str, version: str = PROMPT_VERSION) -> str:
    """
    加载 prompt 文本。
    version 参数用于缓存键区分，便于迭代时回滚。
    """
    path = _PROMPTS_DIR / relative_path
    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {relative_path} (v={version})")
    return path.read_text(encoding="utf-8")


def prompt_meta(relative_path: str) -> dict[str, str]:
    """返回 prompt 元信息，供日志与调试。"""
    return {
        "path": relative_path,
        "version": PROMPT_VERSION,
    }
