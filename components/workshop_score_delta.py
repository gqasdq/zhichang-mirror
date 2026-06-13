"""金子工坊 — 采纳优化后的分数增量估算（无需整份简历重评）。"""

from __future__ import annotations

from typing import Any

CHANGE_TYPE_DELTA: dict[str, dict[str, int]] = {
    "STAR补全": {"star": 5},
    "量化改写": {"quantify": 6},
    "关键词嵌入": {"keyword": 4},
    "去口语化": {"keyword": 3},
    "逻辑重组": {"star": 3},
}


def compute_overall(star: int, quantify: int, keyword: int) -> float:
    return round(star * 0.4 + quantify * 0.3 + keyword * 0.3, 1)


def apply_optimization_delta(
    scores: dict[str, Any],
    *,
    optimize_types: list[str] | None = None,
    changes: list[dict] | None = None,
) -> dict[str, float | int]:
    """根据本次采纳的优化类型，在现有分数上叠加小幅增量。"""
    star = int(scores.get("star", 0))
    quantify = int(scores.get("quantify", 0))
    keyword = int(scores.get("keyword", 0))

    applied: set[str] = set()
    candidates: list[str] = list(optimize_types or [])
    for item in changes or []:
        if not isinstance(item, dict):
            continue
        raw = str(item.get("type", ""))
        for part in raw.split("|"):
            part = part.strip()
            if part:
                candidates.append(part)

    for label in candidates:
        if label in applied:
            continue
        deltas = CHANGE_TYPE_DELTA.get(label)
        if not deltas:
            continue
        applied.add(label)
        star = min(100, star + int(deltas.get("star", 0)))
        quantify = min(100, quantify + int(deltas.get("quantify", 0)))
        keyword = min(100, keyword + int(deltas.get("keyword", 0)))

    return {
        "star": star,
        "quantify": quantify,
        "keyword": keyword,
        "overall": compute_overall(star, quantify, keyword),
    }
