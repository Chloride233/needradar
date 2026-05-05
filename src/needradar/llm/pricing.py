from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ModelPricing:
    input_per_million: float  # cache miss
    input_cache_hit_per_million: float
    output_per_million: float

    def calculate(self, input_tokens: int, output_tokens: int,
                  cached_tokens: int = 0) -> float:
        uncached = max(input_tokens - cached_tokens, 0)
        cost = (uncached * self.input_per_million
                + cached_tokens * self.input_cache_hit_per_million
                + output_tokens * self.output_per_million) / 1_000_000
        return round(cost, 6)


PRICING: dict[str, ModelPricing] = {
    "deepseek-v4-pro": ModelPricing(
        input_per_million=3.0,
        input_cache_hit_per_million=0.025,
        output_per_million=6.0,
    ),
    "deepseek-v4-flash": ModelPricing(
        input_per_million=1.008,
        input_cache_hit_per_million=0.02,
        output_per_million=2.016,
    ),
    "text-embedding-3-small": ModelPricing(
        input_per_million=0.0,
        input_cache_hit_per_million=0.0,
        output_per_million=0.0,
    ),
}


def calculate_cost(model: str, input_tokens: int, output_tokens: int,
                   cached_tokens: int = 0) -> float:
    pricing = PRICING.get(model)
    if not pricing:
        return 0.0
    return pricing.calculate(input_tokens, output_tokens, cached_tokens)
