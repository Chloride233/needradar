from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_phase3_cache_smoke_artifacts_reproduce_accounting():
    root = Path("evaluation/phase3/runs/cache-smoke")
    configurations = ("no_rag", "rag", "rag_hitl")
    actual_cost = 0.0
    no_cache_cost = 0.0
    shared_values = set()

    for configuration in configurations:
        run = json.loads((root / configuration / "run.json").read_text(encoding="utf-8"))
        metrics = json.loads((root / configuration / "metrics.json").read_text(encoding="utf-8"))
        predictions = [
            json.loads(line)
            for line in (root / configuration / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        summary = metrics["phase3"]["summary"]

        assert run["schema_version"] == 2
        assert run["configuration"] == configuration
        assert run["requested"] == run["completed"] == len(predictions) == 5
        assert run["extraction_failures"] == run["retrieval_failures"] == 0
        assert run["provider_params"]["cache_prefix"] is True
        assert (
            sum(item["usage"]["extraction"]["cached_tokens"] for item in predictions)
            == run["usage"]["extraction"]["cached_tokens"]
        )
        assert summary["cached_tokens"] == run["usage"]["extraction"]["cached_tokens"]
        assert summary["cache_hit_rate"] == pytest.approx(
            summary["cached_tokens"] / run["usage"]["extraction"]["input_tokens"]
        )
        assert summary["cost_without_cache_cny"] == pytest.approx(summary["cost_cny"] + summary["cache_savings_cny"])

        actual_cost += summary["cost_cny"]
        no_cache_cost += summary["cost_without_cache_cny"]
        shared_values.add((run["dataset_sha256"], run["gold_sha256"], run["selection_sha256"], run["prompt_sha256"]))

    assert len(shared_values) == 1
    assert actual_cost == pytest.approx(0.028404)
    assert no_cache_cost == pytest.approx(0.076333856)
    assert 1 - actual_cost / no_cache_cost == pytest.approx(0.627897744350816)
