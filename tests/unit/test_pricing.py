"""Tests for LLM pricing module."""
from needradar.llm.pricing import PRICING, ModelPricing, calculate_cost


class TestModelPricing:
    def test_calculate_no_cache(self):
        pricing = ModelPricing(
            input_per_million=2.0,
            input_cache_hit_per_million=0.5,
            output_per_million=4.0,
        )
        cost = pricing.calculate(input_tokens=1000, output_tokens=500)
        assert cost == (1000 * 2.0 + 500 * 4.0) / 1_000_000

    def test_calculate_with_cache(self):
        pricing = ModelPricing(
            input_per_million=3.0,
            input_cache_hit_per_million=0.025,
            output_per_million=6.0,
        )
        cost = pricing.calculate(input_tokens=10_000, output_tokens=5_000, cached_tokens=8_000)
        expected = (2_000 * 3.0 + 8_000 * 0.025 + 5_000 * 6.0) / 1_000_000
        assert cost == expected

    def test_calculate_zero_tokens(self):
        pricing = ModelPricing(
            input_per_million=2.0,
            input_cache_hit_per_million=1.0,
            output_per_million=4.0,
        )
        cost = pricing.calculate(input_tokens=0, output_tokens=0)
        assert cost == 0.0

    def test_cached_exceeds_input_not_negative(self):
        """Cached tokens exceeding input should not produce negative uncached cost."""
        pricing = ModelPricing(
            input_per_million=2.0,
            input_cache_hit_per_million=1.0,
            output_per_million=4.0,
        )
        cost = pricing.calculate(input_tokens=100, output_tokens=50, cached_tokens=200)
        assert cost >= 0.0
        assert cost == (0 * 2.0 + 200 * 1.0 + 50 * 4.0) / 1_000_000

    def test_rounding_precision(self):
        pricing = ModelPricing(
            input_per_million=3.0,
            input_cache_hit_per_million=0.025,
            output_per_million=6.0,
        )
        cost = pricing.calculate(input_tokens=1234, output_tokens=567)
        assert cost == round(cost, 6)


class TestCalculateCost:
    def test_known_model_returns_positive(self):
        cost = calculate_cost("deepseek-v4-pro", input_tokens=1000, output_tokens=500)
        assert cost > 0

    def test_known_model_with_cache(self):
        cost = calculate_cost(
            "deepseek-v4-pro", input_tokens=1000, output_tokens=500, cached_tokens=800
        )
        assert cost > 0

    def test_unknown_model_returns_zero(self):
        cost = calculate_cost("nonexistent-model", input_tokens=1000, output_tokens=500)
        assert cost == 0.0

    def test_flash_cheaper_than_pro(self):
        cost_pro = calculate_cost("deepseek-v4-pro", input_tokens=100_000, output_tokens=10_000)
        cost_flash = calculate_cost("deepseek-v4-flash", input_tokens=100_000, output_tokens=10_000)
        assert cost_flash < cost_pro


class TestPricingRegistry:
    def test_all_models_have_pricing(self):
        assert "deepseek-v4-pro" in PRICING
        assert "deepseek-v4-flash" in PRICING
        assert "text-embedding-3-small" in PRICING

    def test_embedding_model_is_free(self):
        assert PRICING["text-embedding-3-small"].input_per_million == 0.0
        assert PRICING["text-embedding-3-small"].output_per_million == 0.0
