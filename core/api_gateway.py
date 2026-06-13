"""统一 API 网关 — 限流、计时、重试、日志。"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterator, Optional

from loguru import logger
from openai import APIConnectionError, APITimeoutError, OpenAI, RateLimitError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from core.config import get_settings
from core.constants import API_DEFAULT_TIMEOUT, API_MAX_RETRIES


class GatewayModel(str, Enum):
    DEEPSEEK = "deepseek"
    ZHIPU = "zhipu"


@dataclass
class GatewayMetrics:
    model: str
    task_type: str
    latency_ms: float
    total_tokens: str | int = "unknown"
    success: bool = True
    error: Optional[str] = None
    timestamp: float = 0.0


class APIGateway:
    """统一管理 LLM 外部调用。"""

    def __init__(self) -> None:
        settings = get_settings()
        self._clients: dict[GatewayModel, Optional[OpenAI]] = {
            GatewayModel.DEEPSEEK: None,
            GatewayModel.ZHIPU: None,
        }
        self._call_log: list[GatewayMetrics] = []
        self._rate_counters: dict[str, list[float]] = {}

        if settings.deepseek_api_key:
            self._clients[GatewayModel.DEEPSEEK] = OpenAI(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
                timeout=API_DEFAULT_TIMEOUT,
                max_retries=0,
            )
        if settings.zhipu_api_key:
            self._clients[GatewayModel.ZHIPU] = OpenAI(
                api_key=settings.zhipu_api_key,
                base_url=settings.zhipu_base_url,
                timeout=20.0,
                max_retries=0,
            )

    def _check_rate_limit(self, model: GatewayModel) -> None:
        settings = get_settings()
        if not settings.rate_limit_enabled:
            return
        limit = (
            settings.rate_limit_deepseek
            if model == GatewayModel.DEEPSEEK
            else settings.rate_limit_zhipu
        )
        key = model.value
        now = time.time()
        window = self._rate_counters.setdefault(key, [])
        window[:] = [t for t in window if now - t < 60.0]
        if len(window) >= limit:
            logger.warning(f"Rate limit approached for {key}: {len(window)}/{limit}/min")
        window.append(now)

    def _pick_client(self, preferred: GatewayModel) -> tuple[GatewayModel, OpenAI]:
        client = self._clients.get(preferred)
        if client is not None:
            return preferred, client
        for model in (GatewayModel.ZHIPU, GatewayModel.DEEPSEEK):
            c = self._clients.get(model)
            if c is not None:
                logger.warning(f"Gateway fallback: {preferred.value} -> {model.value}")
                return model, c
        raise RuntimeError("No LLM client initialized. Configure DEEPSEEK_API_KEY or ZHIPU_API_KEY.")

    @retry(
        retry=retry_if_exception_type((APITimeoutError, APIConnectionError, RateLimitError)),
        stop=stop_after_attempt(API_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    def chat_completion(
        self,
        *,
        model: GatewayModel,
        messages: list[dict[str, str]],
        task_type: str = "simple_qa",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        timeout: Optional[float] = None,
        stream: bool = False,
    ) -> Any:
        picked, client = self._pick_client(model)
        self._check_rate_limit(picked)
        settings = get_settings()
        model_name = (
            settings.deepseek_model if picked == GatewayModel.DEEPSEEK else settings.zhipu_model
        )

        kwargs: dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        if timeout is not None:
            kwargs["timeout"] = timeout

        start = time.perf_counter()
        ts = time.time()
        try:
            response = client.chat.completions.create(**kwargs)
            latency = (time.perf_counter() - start) * 1000
            if not stream:
                usage = getattr(response, "usage", None)
                tokens = getattr(usage, "total_tokens", "unknown") if usage else "unknown"
                self._call_log.append(
                    GatewayMetrics(
                        model=picked.value,
                        task_type=task_type,
                        latency_ms=latency,
                        total_tokens=tokens,
                        timestamp=ts,
                    )
                )
                logger.info(
                    f"[gateway] {task_type} model={picked.value} "
                    f"latency={latency:.0f}ms tokens={tokens}"
                )
            return response
        except Exception as exc:
            latency = (time.perf_counter() - start) * 1000
            self._call_log.append(
                GatewayMetrics(
                    model=picked.value,
                    task_type=task_type,
                    latency_ms=latency,
                    success=False,
                    error=str(exc),
                    timestamp=ts,
                )
            )
            logger.error(f"[gateway] {task_type} failed: {type(exc).__name__}: {exc}")
            raise

    def chat_stream(
        self,
        *,
        model: GatewayModel,
        messages: list[dict[str, str]],
        task_type: str = "simple_qa",
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> Iterator[str]:
        stream = self.chat_completion(
            model=model,
            messages=messages,
            task_type=task_type,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    def recent_metrics(self, limit: int = 20) -> list[GatewayMetrics]:
        return self._call_log[-limit:]

    def failure_count(self, model: GatewayModel, window_sec: float = 300.0) -> int:
        """统计时间窗口内某模型的失败次数（用于健康检查）。"""
        now = time.time()
        return sum(
            1
            for metric in self._call_log
            if metric.model == model.value
            and not metric.success
            and metric.timestamp > 0
            and (now - metric.timestamp) <= window_sec
        )


_gateway: Optional[APIGateway] = None


def get_api_gateway() -> APIGateway:
    global _gateway
    if _gateway is None:
        _gateway = APIGateway()
    return _gateway
