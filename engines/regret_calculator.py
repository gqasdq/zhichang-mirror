"""平行宇宙后悔值计算 — 纯本地，不调 AI。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from core.constants import REGRET_WEIGHT_GROWTH, REGRET_WEIGHT_RISK, REGRET_WEIGHT_STABILITY

_GROWTH_DISCOUNT_CAP = 40.0
_REGRET_FLOOR = 12.0
_REGRET_CEILING = 88.0
_DISPLAY_LO = 22
_DISPLAY_HI = 68
_MIN_RAW_SPREAD = 10.0

_VAGUE_TOKENS = frozenset({"信息不足", "-", "未知", "待补充", "暂无", "N/A", "n/a"})

_HIGH_RISK_KEYWORDS: dict[str, float] = {
    "跨界": 8.0,
    "转型": 7.0,
    "转行": 7.0,
    "创业": 9.0,
    "替代": 8.0,
    "淘汰": 9.0,
    "瓶颈": 6.0,
    "摸索": 5.0,
    "不确定": 6.0,
    "裁员": 9.0,
    "失败": 5.0,
    "内卷": 5.0,
    "35岁": 7.0,
    "突围": 5.0,
    "新兴": 4.0,
    "试错": 5.0,
    "冷门": 4.0,
}

_STABLE_KEYWORDS: dict[str, float] = {
    "深耕": -7.0,
    "稳定": -6.0,
    "专家": -5.0,
    "积累": -4.0,
    "延续": -4.0,
    "成熟": -3.0,
    "持证": -4.0,
    "国企": -8.0,
    "体制": -7.0,
    "专业对口": -6.0,
}

_PATH_ARCHETYPE_BASE: dict[str, float] = {
    "a": -5.0,
    "b": 3.0,
    "c": 6.0,
}

_SALARY_RANGE_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*[-~到至]\s*(\d+(?:\.\d+)?)\s*万"
)
_SALARY_SINGLE_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*万")
_SALARY_K_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*[kK]")


@dataclass
class PathRegret:
    key: str
    label: str
    regret: int


@dataclass
class RegretComparison:
    paths: list[PathRegret] = field(default_factory=list)
    lower_regret: str = ""
    insight: str = ""
    factors: dict[str, float] = field(default_factory=dict)
    is_tied: bool = False

    @property
    def path_a_label(self) -> str:
        return self._label_for("a", "深耕当下")

    @property
    def path_b_label(self) -> str:
        return self._label_for("b", "拐弯之路")

    @property
    def path_c_label(self) -> str:
        return self._label_for("c", "隐藏可能")

    @property
    def regret_a(self) -> int:
        return self._regret_for("a")

    @property
    def regret_b(self) -> int:
        return self._regret_for("b")

    @property
    def regret_c(self) -> int:
        return self._regret_for("c")

    def _label_for(self, key: str, default: str) -> str:
        for item in self.paths:
            if item.key == key:
                return item.label
        return default

    def _regret_for(self, key: str) -> int:
        for item in self.paths:
            if item.key == key:
                return item.regret
        return 0


def _is_vague(value: str) -> bool:
    text = value.strip()
    return not text or text in _VAGUE_TOKENS


def _mirror_text_blob(mirror: dict[str, Any]) -> str:
    parts = [
        str(mirror.get("title", "")),
        str(mirror.get("summary", "")),
    ]
    for horizon in ("year5", "year10"):
        block = mirror.get(horizon) or {}
        if isinstance(block, dict):
            parts.extend(
                str(block.get(key, ""))
                for key in ("position", "salary", "location", "description")
            )
    risks = mirror.get("risks") or []
    if isinstance(risks, list):
        parts.extend(str(item) for item in risks)
    turning_points = mirror.get("turning_points") or []
    if isinstance(turning_points, list):
        for tp in turning_points:
            if isinstance(tp, dict):
                parts.extend(str(v) for v in tp.values())
            else:
                parts.append(str(tp))
    return "\n".join(part for part in parts if part)


def _keyword_sentiment_score(text: str) -> float:
    score = 0.0
    for keyword, weight in _HIGH_RISK_KEYWORDS.items():
        if keyword in text:
            score += weight
    for keyword, weight in _STABLE_KEYWORDS.items():
        if keyword in text:
            score += weight
    return score


def _parse_salary_mid(text: str) -> float | None:
    values: list[float] = []
    for match in _SALARY_RANGE_PATTERN.finditer(text):
        values.extend([float(match.group(1)), float(match.group(2))])
    if not values:
        for match in _SALARY_SINGLE_PATTERN.finditer(text):
            values.append(float(match.group(1)))
    if not values:
        for match in _SALARY_K_PATTERN.finditer(text):
            values.append(float(match.group(1)) * 0.12)
    if not values:
        return None
    return sum(values) / len(values)


def _salary_trajectory_score(mirror: dict[str, Any]) -> float:
    """薪资轨迹不明或下行，后悔值升高。"""
    y5 = mirror.get("year5") or {}
    y10 = mirror.get("year10") or {}
    if not isinstance(y5, dict):
        y5 = {}
    if not isinstance(y10, dict):
        y10 = {}
    mid5 = _parse_salary_mid(str(y5.get("salary", "")))
    mid10 = _parse_salary_mid(str(y10.get("salary", "")))
    if mid5 is None and mid10 is None:
        return 6.0
    if mid5 is None or mid10 is None:
        return 4.0
    if mid10 < mid5 * 0.85:
        return 12.0
    if mid10 < mid5 * 1.05:
        return 5.0
    return 0.0


def _risk_score(mirror: dict[str, Any]) -> float:
    risks = mirror.get("risks") or []
    if not isinstance(risks, list) or not risks:
        return 0.0
    severity = 0.0
    for item in risks:
        text = str(item)
        item_score = 10.0 + len(text) * 0.12 + _keyword_sentiment_score(text) * 0.6
        severity += min(28.0, item_score)
    return min(100.0, severity)


def _stability_score(mirror: dict[str, Any]) -> float:
    y5 = mirror.get("year5") or {}
    y10 = mirror.get("year10") or {}
    if not isinstance(y5, dict):
        y5 = {}
    if not isinstance(y10, dict):
        y10 = {}
    pos5 = str(y5.get("position", ""))
    pos10 = str(y10.get("position", ""))
    score = 30.0
    if not _is_vague(pos5):
        score += 24.0
    if not _is_vague(pos10):
        score += 18.0
    salary = str(y5.get("salary", ""))
    if any(c.isdigit() for c in salary):
        score += 10.0
    desc5 = str(y5.get("description", ""))
    desc10 = str(y10.get("description", ""))
    if not _is_vague(desc5):
        score += min(8.0, len(desc5) * 0.02)
    if not _is_vague(desc10):
        score += min(8.0, len(desc10) * 0.02)
    blob = _mirror_text_blob(mirror)
    score += min(10.0, max(0.0, -_keyword_sentiment_score(blob) * 0.5))
    return min(100.0, score)


def _growth_score(mirror: dict[str, Any]) -> float:
    tps = mirror.get("turning_points") or []
    count = len(tps) if isinstance(tps, list) else 0
    summary_len = len(str(mirror.get("summary", "")))
    tp_text_len = 0
    if isinstance(tps, list):
        for tp in tps:
            if isinstance(tp, dict):
                tp_text_len += sum(len(str(v)) for v in tp.values())
            else:
                tp_text_len += len(str(tp))
    return min(100.0, count * 8.0 + summary_len * 0.06 + tp_text_len * 0.025)


def _uncertainty_score(mirror: dict[str, Any]) -> float:
    score = 0.0
    for horizon in ("year5", "year10"):
        block = mirror.get(horizon) or {}
        if not isinstance(block, dict):
            block = {}
        if _is_vague(str(block.get("position", ""))):
            score += 14.0
        if _is_vague(str(block.get("description", ""))):
            score += 7.0
        if _is_vague(str(block.get("salary", ""))):
            score += 5.0
    summary = str(mirror.get("summary", "")).strip()
    if len(summary) < 30:
        score += 12.0
    elif len(summary) < 80:
        score += 5.0
    risks = mirror.get("risks") or []
    if isinstance(risks, list) and not risks:
        score += 4.0
    return min(60.0, score)


def _path_archetype_adjustment(path_key: str, mirror: dict[str, Any]) -> float:
    base = _PATH_ARCHETYPE_BASE.get(path_key, 0.0)
    blob = _mirror_text_blob(mirror)
    if any(token in blob for token in ("深耕", "延续", "对口", "专业路线")):
        base -= 3.0
    if any(token in blob for token in ("跨界", "突围", "转行", "拐弯", "换道")):
        base += 4.0
    if any(token in blob for token in ("意外", "隐藏", "小众", "冷门", "被忽视")):
        base += 2.0
    return base


def _compute_regret_raw(mirror: dict[str, Any], *, path_key: str = "") -> float:
    """计算原始后悔分（不做下限钳制，供三路径相对比较）。"""
    blob = _mirror_text_blob(mirror)
    risk = _risk_score(mirror)
    stability = _stability_score(mirror)
    growth = _growth_score(mirror)
    uncertainty = _uncertainty_score(mirror)
    keyword = _keyword_sentiment_score(blob)
    salary_traj = _salary_trajectory_score(mirror)
    archetype = _path_archetype_adjustment(path_key, mirror) if path_key else 0.0
    return (
        risk * REGRET_WEIGHT_RISK
        + (100.0 - stability) * REGRET_WEIGHT_STABILITY
        + uncertainty * 0.20
        + keyword * 0.55
        + salary_traj * 0.35
        + archetype
        - min(growth, _GROWTH_DISCOUNT_CAP) * REGRET_WEIGHT_GROWTH * 0.08
    )


def compute_regret(mirror: dict[str, Any]) -> float:
    """单路径后悔值（带绝对上下限）。"""
    return max(_REGRET_FLOOR, min(_REGRET_CEILING, _compute_regret_raw(mirror)))


def _mirror_signature(mirror: dict[str, Any]) -> str:
    return json.dumps(mirror, ensure_ascii=False, sort_keys=True)


def _normalize_display_regrets(
    entries: list[tuple[str, str, float]],
    *,
    mirrors: list[dict[str, Any]],
) -> tuple[list[PathRegret], bool]:
    """将原始分数映射到可对比的展示区间。"""
    signatures = {_mirror_signature(mirror) for mirror in mirrors}
    if len(signatures) == 1:
        tied_value = int(round((_DISPLAY_LO + _DISPLAY_HI) / 2))
        paths = [PathRegret(key=key, label=label, regret=tied_value) for key, label, _ in entries]
        return paths, True

    raw_values = [score for _, _, score in entries]
    rmin = min(raw_values)
    rmax = max(raw_values)
    spread = rmax - rmin

    if spread < _MIN_RAW_SPREAD:
        mid = sum(raw_values) / len(raw_values)
        factor = _MIN_RAW_SPREAD / max(spread, 0.01)
        scaled = [mid + (value - mid) * factor for value in raw_values]
        rmin = min(scaled)
        rmax = max(scaled)
    else:
        scaled = list(raw_values)

    paths: list[PathRegret] = []
    display_range = _DISPLAY_HI - _DISPLAY_LO
    for (key, label, _), raw_val in zip(entries, scaled):
        pct = _DISPLAY_LO + (raw_val - rmin) / (rmax - rmin) * display_range
        paths.append(PathRegret(key=key, label=label, regret=int(round(pct))))

    paths = _enforce_min_display_gap(paths, entries)
    regrets = {path.regret for path in paths}
    return paths, len(regrets) == 1


_MIN_DISPLAY_GAP = 3


def _enforce_min_display_gap(
    paths: list[PathRegret],
    entries: list[tuple[str, str, float]],
) -> list[PathRegret]:
    """按原始分数排序，将展示值均匀映射到区间内，确保三条路径可区分。"""
    raw_by_key = {key: raw for key, _, raw in entries}
    ordered = sorted(paths, key=lambda item: raw_by_key[item.key])
    count = len(ordered)
    if count <= 1:
        return paths

    regrets = [item.regret for item in ordered]
    needs_respread = len(set(regrets)) < len(regrets)
    if not needs_respread:
        for index in range(1, len(regrets)):
            if regrets[index] - regrets[index - 1] < _MIN_DISPLAY_GAP:
                needs_respread = True
                break
    if not needs_respread:
        return paths

    step = (_DISPLAY_HI - _DISPLAY_LO) / (count - 1)
    adjusted = [
        PathRegret(
            key=item.key,
            label=item.label,
            regret=int(round(_DISPLAY_LO + index * step)),
        )
        for index, item in enumerate(ordered)
    ]
    key_order = {item.key: idx for idx, item in enumerate(paths)}
    return sorted(adjusted, key=lambda item: key_order[item.key])


def _build_insight(paths: list[PathRegret], *, is_tied: bool) -> tuple[str, str]:
    if is_tied:
        value = paths[0].regret if paths else 0
        insight = (
            f"三条路径后悔概率接近（约 {value}%），差异不大，"
            "建议结合你的价值观与风险偏好选择。"
        )
        return "", insight

    min_val = min(p.regret for p in paths)
    lowest = [p for p in paths if p.regret == min_val]
    others = [p for p in paths if p.regret > min_val]

    if len(lowest) > 1:
        labels = "、".join(f"「{p.label}」" for p in lowest)
        insight = f"{labels}后悔概率同为 {min_val}%，均相对更低，可优先从中选择。"
        return lowest[0].label, insight

    other_text = "、".join(f"「{p.label}」{p.regret}%" for p in others)
    winner = lowest[0]
    insight = (
        f"「{winner.label}」后悔概率相对最低（{winner.regret}%），"
        f"其余路径分别为 {other_text}"
    )
    return winner.label, insight


def compare_mirrors(result: dict[str, Any]) -> RegretComparison:
    """对比三条镜面路径的后悔值，返回最低后悔路径。"""
    mirror_defs = (
        ("a", result.get("mirror_a") or {}, "深耕当下"),
        ("b", result.get("mirror_b") or {}, "拐弯之路"),
        ("c", result.get("mirror_c") or {}, "隐藏可能"),
    )
    entries: list[tuple[str, str, float]] = []
    mirrors: list[dict[str, Any]] = []
    factors: dict[str, float] = {}

    for key, mirror, default_label in mirror_defs:
        if not isinstance(mirror, dict):
            mirror = {}
        mirrors.append(mirror)
        label = str(mirror.get("title") or default_label)
        raw = _compute_regret_raw(mirror, path_key=key)
        entries.append((key, label, raw))
        factors[f"{key}_risk"] = _risk_score(mirror)
        factors[f"{key}_stability"] = _stability_score(mirror)
        factors[f"{key}_uncertainty"] = _uncertainty_score(mirror)
        factors[f"{key}_keyword"] = _keyword_sentiment_score(_mirror_text_blob(mirror))

    paths, is_tied = _normalize_display_regrets(entries, mirrors=mirrors)
    lower_regret, insight = _build_insight(paths, is_tied=is_tied)

    return RegretComparison(
        paths=paths,
        lower_regret=lower_regret,
        insight=insight,
        factors=factors,
        is_tied=is_tied,
    )
