"""体验数据统计 — session 内实时 + JSONL 持久化累计。"""

from __future__ import annotations

import json
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any

import streamlit as st

from core.config import get_settings

_ANALYTICS_LOCK = Lock()


def _analytics_path() -> Path:
    settings = get_settings()
    path = Path(settings.analytics_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def init_analytics() -> None:
    """初始化统计模块，零侵入。"""
    if "analytics_events" not in st.session_state:
        st.session_state.analytics_events = []
    if "session_start_time" not in st.session_state:
        st.session_state.session_start_time = time.time()


def _append_persisted(event: dict[str, Any]) -> None:
    """追加写入 JSONL（跨 session / 关页后仍保留）。"""
    line = json.dumps(event, ensure_ascii=False) + "\n"
    path = _analytics_path()
    with _ANALYTICS_LOCK:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line)


def _load_persisted_events(max_lines: int | None = None) -> list[dict[str, Any]]:
    path = _analytics_path()
    if not path.exists():
        return []

    events: list[dict[str, Any]] = []
    with _ANALYTICS_LOCK:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    if max_lines is not None and len(events) > max_lines:
        return events[-max_lines:]
    return events


def track(event_type: str, data: dict | None = None) -> None:
    """记录一个事件；失败不影响业务。"""
    try:
        event = {
            "type": event_type,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data": data or {},
        }
        if "analytics_events" not in st.session_state:
            st.session_state.analytics_events = []
        st.session_state.analytics_events.append(event)
        _append_persisted(event)
    except Exception:
        pass


def track_module_enter(module_name: str) -> None:
    track("module_enter", {"module": module_name})


def track_module_complete(module_name: str) -> None:
    track("module_complete", {"module": module_name})


def track_emotion_score(start: int, end: int) -> None:
    track("emotion_score", {"start": start, "end": end, "delta": end - start})


def track_chat_rounds(module_name: str, rounds: int) -> None:
    track("chat_rounds", {"module": module_name, "rounds": rounds})


def track_error(module_name: str, error_type: str) -> None:
    track("error_occurred", {"module": module_name, "error_type": error_type})


def _summarize_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    type_counts = Counter(e.get("type", "unknown") for e in events)
    module_enters = Counter(
        (e.get("data") or {}).get("module", "unknown")
        for e in events
        if e.get("type") == "module_enter"
    )
    return {
        "event_type_counts": dict(type_counts),
        "module_enter_counts": dict(module_enters),
    }


def export_analytics(*, include_persisted: bool = True, persisted_max: int = 5000) -> dict:
    """导出统计数据：当前 session + 可选持久化累计。"""
    session_events = list(st.session_state.get("analytics_events", []))
    session_duration = time.time() - st.session_state.get("session_start_time", time.time())

    persisted_events: list[dict[str, Any]] = []
    if include_persisted:
        persisted_events = _load_persisted_events(max_lines=persisted_max)

    all_events = persisted_events + session_events
    summary = _summarize_events(all_events)

    return {
        "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "analytics_file": str(_analytics_path()),
        "session_duration_seconds": round(session_duration, 1),
        "session_events": len(session_events),
        "persisted_events": len(persisted_events),
        "total_events": len(all_events),
        "summary": summary,
        "events": all_events,
    }
