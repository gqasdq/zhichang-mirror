"""全局业务阈值与常量（从代码中抽离，避免硬编码散落）。"""

from __future__ import annotations

# 认知偏差阈值
BIAS_SEVERE_UNDER: float = -30.0
BIAS_MILD_UNDER: float = -15.0
BIAS_ACCURATE_HIGH: float = 10.0
BIAS_MILD_OVER: float = 20.0

# 简历筛选通过率估算（综合分 → 约 X/10 岗位）
PASS_RATE_TIERS: tuple[tuple[float, int], ...] = (
    (80.0, 8),
    (65.0, 6),
    (50.0, 4),
    (35.0, 2),
    (0.0, 1),
)

# 平行宇宙后悔值权重
REGRET_WEIGHT_RISK: float = 0.35
REGRET_WEIGHT_STABILITY: float = 0.35
REGRET_WEIGHT_GROWTH: float = 0.30

# API 网关
API_DEFAULT_TIMEOUT: float = 40.0
API_PARALLEL_TIMEOUT: float = 180.0
API_EMOTION_FAST_TIMEOUT: float = 12.0
API_MAX_RETRIES: int = 2

# Prompt 版本
PROMPT_VERSION: str = "v1.0.0"
