"""认知偏差检测引擎 — 纯本地计算，不调用 AI。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from utils.emotion_adapter import EmotionAdapter

BiasLevel = Literal["严重低估", "轻度低估", "基本准确", "轻度高估", "严重高估"]

# 情绪状态下求职者平均自评偏差（自评 - 客观，负值=低估）
EMOTION_BASELINE: dict[str, float] = {
    EmotionAdapter.ANXIOUS: -23.0,
    EmotionAdapter.FRUSTRATED: -18.0,
    EmotionAdapter.CONFUSED: -12.0,
    EmotionAdapter.CALM: -5.0,
}

from core.constants import (
    BIAS_ACCURATE_HIGH,
    BIAS_MILD_OVER,
    BIAS_MILD_UNDER,
    BIAS_SEVERE_UNDER,
)

THRESHOLDS = [
    (-100, BIAS_SEVERE_UNDER, "严重低估"),
    (BIAS_SEVERE_UNDER, BIAS_MILD_UNDER, "轻度低估"),
    (BIAS_MILD_UNDER, BIAS_ACCURATE_HIGH, "基本准确"),
    (BIAS_ACCURATE_HIGH, BIAS_MILD_OVER, "轻度高估"),
    (BIAS_MILD_OVER, 100, "严重高估"),
]


@dataclass
class BiasResult:
    self_score: int
    objective_score: int
    bias_value: float
    severity: BiasLevel
    percentile: int
    correction_one_liner: str
    detailed_analysis: str


def _classify_severity(bias: float) -> BiasLevel:
    for low, high, label in THRESHOLDS:
        if low < bias <= high:
            return label  # type: ignore[return-value]
    if bias <= -30:
        return "严重低估"
    if bias > 20:
        return "严重高估"
    return "基本准确"


def _estimate_percentile(bias: float, emotion_state: str) -> int:
    """简化模型：偏离该情绪基准越远，百分位越高。"""
    baseline = EMOTION_BASELINE.get(emotion_state, EMOTION_BASELINE[EmotionAdapter.CALM])
    deviation = abs(bias - baseline)
    # 0~40 映射到 50~99
    pct = int(min(99, max(50, 50 + deviation * 1.2)))
    return pct


def _build_correction(bias: float, objective: int, self_score: int) -> str:
    diff = objective - self_score
    if bias <= -15:
        return f"你的实际匹配度比你以为的高 {abs(diff):.0f}%"
    if bias >= 15:
        return f"客观评估略低于你的自评，建议对照 JD 查漏补缺"
    return "你的直觉与客观评估基本一致，可以继续细化简历"


def _build_detailed_analysis(bias: float, severity: BiasLevel, emotion_state: str) -> str:
    parts: list[str] = []

    if severity in ("严重低估", "轻度低估"):
        parts.append(
            "在求职压力下，大脑容易放大威胁、缩小成就——这是正常的保护机制，"
            "但会扭曲你对自己能力的判断。"
        )
        parts.append(
            "**耶克斯-多德森定律**指出：中等焦虑有助于表现，但过高焦虑会显著拉低自我评估的准确性。"
            "（Yerkes & Dodson, 1908）"
        )
        parts.append(
            "**CBT 认知重构**建议：把「我不行」改写为「这条 JD 我满足了 X 项要求」，"
            "用具体证据替代笼统否定。"
        )
        parts.append(
            "**积极心理学优势视角**：你的经历中已有可验证的成果，只是焦虑状态下难以被主动提取。"
            "（Seligman, 2002）"
        )
    elif severity in ("轻度高估", "严重高估"):
        parts.append(
            "适度的自信有助于投递，但过高的自评可能让你忽略 JD 中的关键缺口。"
        )
        parts.append(
            "**CBT 认知重构**：用「证据清单」对照 JD 每一条要求，区分「做过」与「匹配」。"
        )
    else:
        parts.append("你的自评与客观分析较为一致，说明你对自身能力有相对清晰的认知。")
        parts.append(
            "**积极心理学**：在此基础上聚焦 1–2 个可快速提升的维度，比全面焦虑更有效。"
        )

    baseline = EMOTION_BASELINE.get(emotion_state, -5)
    parts.append(
        f"\n*数据说明：{emotion_state}状态下，求职者平均会低估自己约 {abs(baseline):.0f} 个百分点。*"
    )
    return "\n\n".join(parts)


def detect_cognitive_bias(
    self_score: int,
    objective_score: int,
    emotion_state: str,
) -> BiasResult:
    """计算认知偏差结果。"""
    self_s = max(0, min(100, int(self_score)))
    obj_s = max(0, min(100, int(objective_score)))
    bias = float(self_s - obj_s)
    severity = _classify_severity(bias)
    percentile = _estimate_percentile(bias, emotion_state)

    return BiasResult(
        self_score=self_s,
        objective_score=obj_s,
        bias_value=bias,
        severity=severity,
        percentile=percentile,
        correction_one_liner=_build_correction(bias, obj_s, self_s),
        detailed_analysis=_build_detailed_analysis(bias, severity, emotion_state),
    )


def should_show_bias_detection(emotion_state: str) -> bool:
    return emotion_state in (
        EmotionAdapter.ANXIOUS,
        EmotionAdapter.FRUSTRATED,
        EmotionAdapter.CONFUSED,
    )
