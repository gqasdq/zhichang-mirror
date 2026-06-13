"""模型路由器 — 成本感知 + 健康检查 + 任务路由。"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional

from loguru import logger

from core.api_gateway import GatewayModel, get_api_gateway
from core.cache_manager import cache_manager
from core.config import get_settings
from core.constants import API_EMOTION_FAST_TIMEOUT


class ModelType(Enum):
    """模型类型枚举。"""

    DEEPSEEK = "deepseek"
    ZHIPU = "zhipu"


def make_cache_key(
    task_type: str,
    prompt: str,
    *,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    system_prompt: str | None = None,
) -> str:
    """跨进程稳定的缓存键（避免 Python hash() 随机化）。"""
    digest = hashlib.sha256()
    for part in (task_type, prompt, str(temperature), str(max_tokens), system_prompt or ""):
        digest.update(part.encode("utf-8"))
        digest.update(b"\x00")
    return f"{task_type}:{digest.hexdigest()[:32]}:{temperature}:{max_tokens}"


@dataclass
class RoutingDecision:
    """单次路由决策（可展示给前端 / 日志）。"""

    preferred: str
    selected: str
    reason: str
    cost_tier: str = "balanced"
    healthy_models: list[str] = field(default_factory=list)
    task_type: str = ""


class ModelRouter:
    """模型路由器 — 任务路由 + 健康检查 + 成本感知降级。"""

    _HEALTH_WINDOW_SEC = 300.0
    _MAX_FAILURES = 3

    def __init__(self) -> None:
        self.settings = get_settings()
        self.gateway = get_api_gateway()
        self._last_routing: Optional[RoutingDecision] = None
        self._local_failures: dict[str, list[float]] = {
            ModelType.DEEPSEEK.value: [],
            ModelType.ZHIPU.value: [],
        }

    def get_last_routing(self) -> Optional[dict[str, str | list[str]]]:
        if self._last_routing is None:
            return None
        return {
            "preferred": self._last_routing.preferred,
            "selected": self._last_routing.selected,
            "reason": self._last_routing.reason,
            "cost_tier": self._last_routing.cost_tier,
            "healthy_models": list(self._last_routing.healthy_models),
            "task_type": self._last_routing.task_type,
        }

    def _to_gateway_model(self, model_type: ModelType) -> GatewayModel:
        return (
            GatewayModel.DEEPSEEK if model_type == ModelType.DEEPSEEK else GatewayModel.ZHIPU
        )

    def _has_api_key(self, model_type: ModelType) -> bool:
        if model_type == ModelType.DEEPSEEK:
            return bool(self.settings.deepseek_api_key)
        return bool(self.settings.zhipu_api_key)

    def _prune_failures(self, model_key: str) -> None:
        now = time.time()
        window = self._local_failures.setdefault(model_key, [])
        self._local_failures[model_key] = [t for t in window if now - t < self._HEALTH_WINDOW_SEC]

    def _record_failure(self, model_type: ModelType) -> None:
        key = model_type.value
        self._prune_failures(key)
        self._local_failures[key].append(time.time())

    def _gateway_failure_count(self, model_type: ModelType) -> int:
        return self.gateway.failure_count(
            self._to_gateway_model(model_type),
            window_sec=self._HEALTH_WINDOW_SEC,
        )

    def _is_healthy(self, model_type: ModelType) -> bool:
        if not self._has_api_key(model_type):
            return False
        self._prune_failures(model_type.value)
        local_fails = len(self._local_failures.get(model_type.value, []))
        gateway_fails = self._gateway_failure_count(model_type)
        if local_fails >= self._MAX_FAILURES or gateway_fails >= self._MAX_FAILURES:
            return False
        return True

    def _get_available_models(self) -> list[ModelType]:
        available: list[ModelType] = []
        for model_type in (ModelType.DEEPSEEK, ModelType.ZHIPU):
            if self._is_healthy(model_type):
                available.append(model_type)
        return available

    def _get_model_for_task(self, task_type: str, input_length: int) -> ModelType:
        complex_tasks = {
            "complex_analysis",
            "comprehensive_eval",
            "reasoning",
            "bias_detection",
            "future_projection",
            "empathy_match",
            "gene_sequencing",
            "parallel_story",
        }
        if task_type in complex_tasks:
            return ModelType.DEEPSEEK
        if task_type == "emotional_empathy":
            return ModelType.ZHIPU if input_length < 1800 else ModelType.DEEPSEEK
        if task_type in {"emotion_fast", "empathy_stories", "empathy_detail", "parallel_followup"}:
            return ModelType.ZHIPU
        if task_type in {"simple_qa", "template_reply", "quick_summary"} and input_length < 500:
            return ModelType.ZHIPU
        if input_length >= 500:
            return ModelType.DEEPSEEK
        return ModelType.ZHIPU

    def _cost_aware_select(
        self,
        available: list[ModelType],
        task_type: str,
        preferred: ModelType,
    ) -> tuple[ModelType, str, str]:
        """在健康模型池内做成本感知选择。"""
        if not available:
            raise RuntimeError("No healthy model available. Please check API keys and service status.")

        cheap_tasks = {
            "emotion_fast",
            "empathy_stories",
            "empathy_detail",
            "parallel_followup",
            "simple_qa",
            "template_reply",
            "quick_summary",
        }
        heavy_tasks = {
            "complex_analysis",
            "comprehensive_eval",
            "reasoning",
            "bias_detection",
            "future_projection",
            "empathy_match",
            "gene_sequencing",
            "parallel_story",
        }

        if task_type in heavy_tasks:
            if ModelType.DEEPSEEK in available:
                return ModelType.DEEPSEEK, "推理任务优先 DeepSeek", "quality_first"
            return available[0], "DeepSeek 不可用，降级至可用模型", "fallback"

        if task_type in cheap_tasks or task_type == "emotional_empathy":
            if ModelType.ZHIPU in available:
                return ModelType.ZHIPU, "轻量共情任务优先智谱（成本更低）", "cost_first"
            return available[0], "智谱不可用，切换至 DeepSeek", "fallback"

        if preferred in available:
            return preferred, "首选模型健康可用", "balanced"

        other = available[0]
        return other, f"首选 {preferred.value} 不可用，自动切换", "fallback"

    def _resolve_model(self, task_type: str, input_length: int) -> ModelType:
        preferred = self._get_model_for_task(task_type, input_length)
        available = self._get_available_models()
        if not available:
            return self._pick_available_model_legacy(preferred)

        selected, reason, cost_tier = self._cost_aware_select(available, task_type, preferred)
        self._last_routing = RoutingDecision(
            preferred=preferred.value,
            selected=selected.value,
            reason=reason,
            cost_tier=cost_tier,
            healthy_models=[m.value for m in available],
            task_type=task_type,
        )
        if selected != preferred:
            logger.warning(
                "Cost-aware route: task=%s preferred=%s selected=%s reason=%s",
                task_type,
                preferred.value,
                selected.value,
                reason,
            )
        return selected

    def _pick_available_model_legacy(self, preferred: ModelType) -> ModelType:
        """API Key 兜底（无健康池时）。"""
        if preferred == ModelType.DEEPSEEK and self.settings.deepseek_api_key:
            return ModelType.DEEPSEEK
        if preferred == ModelType.ZHIPU and self.settings.zhipu_api_key:
            return ModelType.ZHIPU
        if self.settings.zhipu_api_key:
            logger.warning(f"Model fallback: preferred={preferred.value}, use=zhipu")
            return ModelType.ZHIPU
        if self.settings.deepseek_api_key:
            logger.warning(f"Model fallback: preferred={preferred.value}, use=deepseek")
            return ModelType.DEEPSEEK
        raise RuntimeError("No model client is initialized. Please set at least one API key.")

    def _pick_available_model(self, preferred: ModelType) -> ModelType:
        return self._pick_available_model_legacy(preferred)

    def _execute_call(
        self,
        *,
        model_type: ModelType,
        messages: list[dict[str, str]],
        task_type: str,
        temperature: float,
        max_tokens: int,
        timeout: Optional[float],
    ) -> str:
        response = self.gateway.chat_completion(
            model=self._to_gateway_model(model_type),
            messages=messages,
            task_type=task_type,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )
        result = (response.choices[0].message.content or "").strip()
        if not result:
            logger.warning(f"Empty LLM response for task={task_type}")
            return "暂时无法生成回复，请稍后再试。"
        return result

    def call(
        self,
        prompt: str,
        task_type: str = "simple_qa",
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        timeout: Optional[float] = None,
    ) -> str:
        """同步调用 LLM 并返回完整文本。"""
        cache_key = make_cache_key(
            task_type,
            prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
        )
        cached = cache_manager.get(cache_key)
        if cached is not None:
            logger.debug(f"Cache hit: {cache_key}")
            return cached

        model_type = self._resolve_model(task_type, len(prompt))

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        request_timeout = timeout
        if request_timeout is None and task_type == "emotion_fast":
            request_timeout = API_EMOTION_FAST_TIMEOUT

        try:
            result = self._execute_call(
                model_type=model_type,
                messages=messages,
                task_type=task_type,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=request_timeout,
            )
            cache_manager.set(cache_key, result)
            return result
        except Exception as exc:
            self._record_failure(model_type)
            logger.exception(f"Model call failed task={task_type} model={model_type.value}: {exc}")

            alternate = ModelType.ZHIPU if model_type == ModelType.DEEPSEEK else ModelType.DEEPSEEK
            if alternate != model_type and self._is_healthy(alternate):
                logger.warning("Retrying with alternate model: %s", alternate.value)
                try:
                    result = self._execute_call(
                        model_type=alternate,
                        messages=messages,
                        task_type=task_type,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        timeout=request_timeout,
                    )
                    self._last_routing = RoutingDecision(
                        preferred=model_type.value,
                        selected=alternate.value,
                        reason=f"主模型失败，自动切换: {type(exc).__name__}",
                        cost_tier="failover",
                        healthy_models=[m.value for m in self._get_available_models()],
                        task_type=task_type,
                    )
                    cache_manager.set(cache_key, result)
                    return result
                except Exception as retry_exc:
                    self._record_failure(alternate)
                    logger.exception(f"Alternate model also failed: {retry_exc}")
            raise

    def call_with_messages(
        self,
        messages: list[dict[str, str]],
        task_type: str = "emotion_fast",
        temperature: float = 0.7,
        max_tokens: int = 2000,
        timeout: Optional[float] = None,
    ) -> str:
        """多轮对话：直接传入 messages 列表（含 system / user / assistant）。"""
        if not messages:
            raise ValueError("messages 不能为空")

        model_type = self._resolve_model(task_type, sum(len(m.get("content", "")) for m in messages))
        request_timeout = timeout
        if request_timeout is None and task_type == "emotion_fast":
            request_timeout = API_EMOTION_FAST_TIMEOUT

        return self._execute_call(
            model_type=model_type,
            messages=messages,
            task_type=task_type,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=request_timeout,
        )

    def call_stream(
        self,
        prompt: str,
        task_type: str = "simple_qa",
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ):
        """流式调用 LLM，逐片段返回文本。"""
        model_type = self._resolve_model(task_type, len(prompt))

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        yield from self.gateway.chat_stream(
            model=self._to_gateway_model(model_type),
            messages=messages,
            task_type=task_type,
            temperature=temperature,
            max_tokens=max_tokens,
        )


model_router = ModelRouter()
