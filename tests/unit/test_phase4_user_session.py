import pytest

from needradar.llm.pricing import ModelPricing
from scripts.run_phase4_user_session import maximum_call_cost, require_call_budget


def test_maximum_call_cost_uses_uncached_input_and_maximum_output():
    pricing = ModelPricing(input_per_million=1.0, input_cache_hit_per_million=0.0, output_per_million=2.0)
    messages = [{"role": "user", "content": "context"}]

    estimated = maximum_call_cost(messages, 1000, pricing)

    assert estimated > 0.002


def test_require_call_budget_rejects_before_call_when_maximum_exceeds_remaining():
    pricing = ModelPricing(input_per_million=1.0, input_cache_hit_per_million=0.0, output_per_million=2.0)

    with pytest.raises(RuntimeError, match="insufficient session budget"):
        require_call_budget(
            spent=0.009,
            max_cost_cny=0.01,
            messages=[{"role": "user", "content": "context"}],
            max_tokens=1000,
            pricing=pricing,
        )
