from needradar.llm.pricing import PRICING, calculate_cost


def test_deepseek_pricing_completion():
    cost = calculate_cost("deepseek-v4-pro", input_tokens=1000, output_tokens=500)
    expected = (1000 * 3.0 + 500 * 6.0) / 1_000_000
    assert cost == round(expected, 6)


def test_deepseek_pricing_cached():
    cost = calculate_cost("deepseek-v4-pro", input_tokens=1000, output_tokens=500, cached_tokens=800)
    expected = (200 * 3.0 + 800 * 0.025 + 500 * 6.0) / 1_000_000
    assert cost == round(expected, 6)


def test_unknown_model_zero_cost():
    cost = calculate_cost("unknown-model", input_tokens=1000, output_tokens=500)
    assert cost == 0.0


def test_zero_tokens():
    cost = calculate_cost("deepseek-v4-pro", input_tokens=0, output_tokens=0)
    assert cost == 0.0


def test_pricing_config_exists():
    assert "deepseek-v4-pro" in PRICING
    p = PRICING["deepseek-v4-pro"]
    assert p.input_per_million == 3.0
    assert p.output_per_million == 6.0
    assert p.input_cache_hit_per_million == 0.025
