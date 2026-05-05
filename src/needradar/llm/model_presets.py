from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ModelPreset:
    id: str
    name: str
    provider: str
    litellm_model: str
    base_url: str
    max_tokens: int = 4096
    temperature: float = 0.3
    api_key: str = ""

    def mask_key(self) -> str:
        if not self.api_key:
            return ""
        if len(self.api_key) <= 8:
            return "****"
        return self.api_key[:4] + "*" * (len(self.api_key) - 8) + self.api_key[-4:]

    def to_dict(self, include_key: bool = False) -> dict:
        d = {
            "id": self.id,
            "name": self.name,
            "provider": self.provider,
            "litellm_model": self.litellm_model,
            "base_url": self.base_url,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "has_api_key": bool(self.api_key),
            "api_key_masked": self.mask_key(),
        }
        if include_key:
            d["api_key"] = self.api_key
        return d


PRESETS: dict[str, ModelPreset] = {
    "deepseek-v4-pro": ModelPreset(
        id="deepseek-v4-pro",
        name="DeepSeek V4 Pro",
        provider="deepseek",
        litellm_model="openai/deepseek-v4-pro",
        base_url="https://api.deepseek.com",
    ),
    "deepseek-v4-flash": ModelPreset(
        id="deepseek-v4-flash",
        name="DeepSeek V4 Flash",
        provider="deepseek",
        litellm_model="openai/deepseek-v4-flash",
        base_url="https://api.deepseek.com",
    ),
}
