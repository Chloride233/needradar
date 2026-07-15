from __future__ import annotations

import pytest

from needradar.services.collector_comparison import build_workload, expected_counts
from scripts.collector_benchmark_python import run_benchmark


@pytest.mark.parametrize("scenario", ["normal", "retry_10pct", "duplicate_10pct"])
async def test_python_benchmark_uses_production_primitives_with_expected_results(scenario: str):
    workload = build_workload(task_count=20)
    result = await run_benchmark(
        workload,
        scenario=scenario,
        task_count=20,
        concurrency=4,
        delay_seconds=0.0001,
    )
    assert {field: result[field] for field in expected_counts(workload, scenario, 20)} == expected_counts(
        workload, scenario, 20
    )
    assert result["p99_latency_ms"] >= result["p95_latency_ms"] >= result["p50_latency_ms"]


async def test_python_benchmark_rejects_invalid_concurrency():
    with pytest.raises(ValueError, match="concurrency"):
        await run_benchmark(build_workload(task_count=2), scenario="normal", task_count=2, concurrency=0)
