# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING

import litellm
from loguru import logger

from needradar.core.config import settings
from needradar.llm.config_store import load_config, save_preset_config
from needradar.llm.model_presets import PRESETS, ModelPreset
from needradar.llm.pricing import calculate_cost
from needradar.llm.sanitizer import (
    detect_injection,
    safe_json_parse,
    sanitize_user_input,
    validate_llm_output,
)

if TYPE_CHECKING:
    from pydantic import BaseModel

litellm.suppress_debug_info = True

# ── Shared prefix for all NeedRadar LLM calls ──
# This stable prefix is cached by DeepSeek's prefix caching.
# DO NOT modify unless necessary — changing it invalidates all cached prefixes.
SHARED_SYSTEM_PREFIX = (
    "你是 NeedRadar 系统的 AI 引擎。系统用于从全网挖掘用户需求，"
    "生成结构化洞察报告。你必须严格遵守以下法则：\n"
    "- 使用 Markdown 格式输出\n"
    "- 分析必须基于提供的实际数据，禁止编造数据\n"
    "- 数值引用（百分比、数量）必须可追溯到来源数据\n"
    "- 如实标注信息来源，无法确认的标注为[未验证]\n"
)


class LLMProvider:
    """Unified LLM call layer based on litellm.

    Uses DeepSeek V4 Pro when configured, falls back to OpenAI/Anthropic env keys.
    """

    def __init__(self) -> None:
        self._configure_keys()
        self._active_preset_id: str | None = None
        self._health: dict[str, dict] = {}
        self._last_usage: dict | None = None
        self._init_from_env()
        self._load_persisted_config()

    def _configure_keys(self) -> None:
        if settings.openai_api_key:
            litellm.openai_key = settings.openai_api_key
        if settings.anthropic_api_key:
            litellm.anthropic_key = settings.anthropic_api_key

    def _init_from_env(self) -> None:
        if settings.deepseek_api_key:
            PRESETS["deepseek-v4-flash"].api_key = settings.deepseek_api_key
            PRESETS["deepseek-v4-pro"].api_key = settings.deepseek_api_key
            self._active_preset_id = "deepseek-v4-flash"

    def _load_persisted_config(self) -> None:
        config = load_config()
        # Check for any deepseek preset with an API key
        for preset_id in ("deepseek-v4-flash", "deepseek-v4-pro"):
            entry = config.get("presets", {}).get(preset_id, {})
            if entry.get("api_key"):
                PRESETS["deepseek-v4-flash"].api_key = entry["api_key"]
                PRESETS["deepseek-v4-pro"].api_key = entry["api_key"]
                self._active_preset_id = "deepseek-v4-flash"
                if "temperature" in entry:
                    PRESETS["deepseek-v4-flash"].temperature = entry["temperature"]
                if "max_tokens" in entry:
                    PRESETS["deepseek-v4-flash"].max_tokens = entry["max_tokens"]
                return

    @property
    def active_preset(self) -> ModelPreset | None:
        if self._active_preset_id and self._active_preset_id in PRESETS:
            return PRESETS[self._active_preset_id]
        return None

    @property
    def active_preset_id(self) -> str | None:
        return self._active_preset_id

    def activate_preset(self, preset_id: str) -> None:
        """Temporarily switch the active preset without persisting to config."""
        if preset_id not in PRESETS:
            raise ValueError(f"Unknown preset: {preset_id}")
        self._active_preset_id = preset_id

    def get_health(self, preset_id: str) -> dict:
        return self._health.get(preset_id, {})

    def update_preset(self, preset_id: str, *, api_key: str | None = None,
                      temperature: float | None = None, max_tokens: int | None = None) -> ModelPreset:
        if preset_id not in PRESETS:
            raise ValueError(f"Unknown preset: {preset_id}")
        preset = PRESETS[preset_id]
        if api_key is not None:
            preset.api_key = api_key
            self._active_preset_id = preset_id
        if temperature is not None:
            preset.temperature = temperature
        if max_tokens is not None:
            preset.max_tokens = max_tokens
        save_preset_config(
            preset_id,
            api_key=api_key,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return preset

    async def test_connection(self, preset_id: str) -> dict:
        preset = PRESETS.get(preset_id)
        if not preset:
            raise ValueError(f"Unknown preset: {preset_id}")
        if not preset.api_key:
            return {"success": False, "error": "API key not configured", "latency_ms": None}

        start = time.monotonic()
        try:
            response = await litellm.acompletion(
                model=preset.litellm_model,
                messages=[{"role": "user", "content": "Hello, respond with exactly: OK"}],
                api_base=preset.base_url,
                api_key=preset.api_key,
                max_tokens=16,
                temperature=0.0,
            )
            elapsed_ms = int((time.monotonic() - start) * 1000)
            content = response.choices[0].message.content or ""
            result = {"success": True, "response": content, "latency_ms": elapsed_ms}
        except Exception as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            result = {"success": False, "error": str(e), "latency_ms": elapsed_ms}

        self._health[preset_id] = result
        return result

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        response_format: dict | None = None,
        cache_prefix: bool = True,
    ) -> str:
        # Scan user messages for injection attempts
        for msg in messages:
            if msg.get("role") == "user":
                injections = detect_injection(msg["content"])
                if injections:
                    logger.warning("injection_detected", patterns=injections)
                    msg["content"] = sanitize_user_input(msg["content"])

        # Inject shared prefix into first system message for cache reuse
        if cache_prefix and messages and messages[0].get("role") == "system":
            original = messages[0]["content"]
            if not original.startswith(SHARED_SYSTEM_PREFIX):
                messages[0]["content"] = SHARED_SYSTEM_PREFIX + "\n" + original
        elif cache_prefix and messages:
            messages.insert(0, {"role": "system", "content": SHARED_SYSTEM_PREFIX})

        preset = self.active_preset
        if preset:
            return await self._call_model(
                preset, messages,
                model=model, max_tokens=max_tokens,
                temperature=temperature,
                response_format=response_format,
            )
        return await self._call_default(
            messages, model=model, max_tokens=max_tokens,
            temperature=temperature, response_format=response_format,
        )

    async def _call_model(
        self, preset: ModelPreset,
        messages: list[dict[str, str]],
        *, model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        response_format: dict | None = None,
    ) -> str:
        effective_model = model or preset.litellm_model
        effective_max_tokens = max_tokens or preset.max_tokens
        effective_temperature = temperature if temperature is not None else preset.temperature

        response = await litellm.acompletion(
            model=effective_model,
            messages=messages,
            max_tokens=effective_max_tokens,
            temperature=effective_temperature,
            response_format=response_format,
            api_base=preset.base_url,
            api_key=preset.api_key,
        )
        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0
        total_tokens = usage.total_tokens if usage else 0
        cached_tokens = 0
        if usage and hasattr(usage, "prompt_tokens_details") and usage.prompt_tokens_details:
            cached_tokens = getattr(usage.prompt_tokens_details, "cached_tokens", 0) or 0
        cost = calculate_cost(preset.id, input_tokens, output_tokens, cached_tokens)
        self._last_usage = {
            "preset_id": preset.id,
            "model": effective_model,
            "call_type": "completion",
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cached_tokens": cached_tokens,
            "total_tokens": total_tokens,
            "cost_cny": cost,
        }
        logger.info("llm_complete", model=effective_model, tokens=total_tokens, cost_cny=cost)
        return validate_llm_output(response.choices[0].message.content or "")

    async def _call_default(
        self, messages: list[dict[str, str]],
        *, model: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
        response_format: dict | None = None,
    ) -> str:
        effective_model = model or settings.llm_default_model
        effective_max_tokens = max_tokens or settings.llm_default_max_tokens
        effective_temperature = temperature if temperature is not None else settings.llm_default_temperature

        try:
            response = await litellm.acompletion(
                model=effective_model,
                messages=messages,
                max_tokens=effective_max_tokens,
                temperature=effective_temperature,
                response_format=response_format,
                fallbacks=[settings.llm_fallback_model],
            )
            usage = response.usage
            input_tokens = usage.prompt_tokens if usage else 0
            output_tokens = usage.completion_tokens if usage else 0
            total_tokens = usage.total_tokens if usage else 0
            self._last_usage = {
                "preset_id": "default",
                "model": effective_model,
                "call_type": "completion",
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cached_tokens": 0,
                "total_tokens": total_tokens,
                "cost_cny": 0.0,
            }
            logger.info("llm_complete", model=effective_model, tokens=total_tokens)
            return validate_llm_output(response.choices[0].message.content or "")
        except Exception as e:
            logger.error("llm_complete_failed", model=effective_model, error=str(e))
            raise

    def pop_last_usage(self) -> dict | None:
        u = self._last_usage
        self._last_usage = None
        return u

    async def extract_structured(
        self,
        prompt: str,
        text: str,
        schema: type[BaseModel],
    ) -> BaseModel:
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": sanitize_user_input(text)},
        ]
        raw = await self.complete(
            messages,
            response_format={"type": "json_object"},
        )
        data = safe_json_parse(raw)
        if data is None:
            raise ValueError(f"Failed to parse LLM output as JSON: {raw[:200]}")
        if isinstance(data, list) and data:
            data = data[0]
        elif isinstance(data, dict):
            for key in ("requirements", "demands", "items", "data", "result"):
                if key in data and isinstance(data[key], list) and data[key]:
                    data = data[key][0]
                    break
        return schema.model_validate(data)


llm = LLMProvider()
