from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from needradar.services.phase3_verifier_experiment import estimate_verifier_calls, run_verifier_experiment


class FakeProvider:
    def __init__(self) -> None:
        self.last_usage = None
        self.fallback_values = []
        self.extra_bodies = []

    async def complete(self, messages, **kwargs):
        self.fallback_values.append(kwargs.get("fallback_to_default"))
        self.extra_bodies.append(kwargs.get("extra_body"))
        self.last_usage = {
            "input_tokens": 100,
            "output_tokens": 20,
            "cached_tokens": 80,
            "cost_cny": 0.0001,
        }
        system = messages[0]["content"]
        if "提取所有可验证" in system:
            return "[]"
        if "事实核查验证引擎" in system:
            claim_text = messages[1]["content"].split("待验证声明：\n", 1)[1]
            count = len(re.findall(r"^\d+\. ", claim_text, re.MULTILINE))
            return json.dumps(
                [
                    {
                        "idx": index,
                        "verdict": "supported",
                        "confidence": 0.9,
                        "evidence": "fixture",
                        "flags": [],
                    }
                    for index in range(1, count + 1)
                ]
            )
        if "逻辑矛盾" in system:
            return json.dumps({"consistent": True, "score": 90, "issues": []})
        raise AssertionError(system)

    def pop_last_usage(self):
        usage = self.last_usage
        self.last_usage = None
        return usage


class OneMalformedFactProvider(FakeProvider):
    def __init__(self) -> None:
        super().__init__()
        self.fact_calls = 0

    async def complete(self, messages, **kwargs):
        if "事实核查验证引擎" in messages[0]["content"]:
            self.fact_calls += 1
            if self.fact_calls == 1:
                self.fallback_values.append(kwargs.get("fallback_to_default"))
                self.last_usage = {"input_tokens": 10, "output_tokens": 2, "cached_tokens": 0, "cost_cny": 0.0}
                return "{}"
        return await super().complete(messages, **kwargs)


class OneFailedExtractionProvider(FakeProvider):
    def __init__(self) -> None:
        super().__init__()
        self.failed = False

    async def complete(self, messages, **kwargs):
        if "提取所有可验证" in messages[0]["content"] and not self.failed:
            self.failed = True
            self.fallback_values.append(kwargs.get("fallback_to_default"))
            self.extra_bodies.append(kwargs.get("extra_body"))
            raise RuntimeError("provider unavailable")
        return await super().complete(messages, **kwargs)


@pytest.mark.asyncio
async def test_runs_stage_dag_with_strict_provider_reuse_and_resume(tmp_path):
    provider = FakeProvider()
    output_dir = tmp_path / "run"
    kwargs = {
        "model_id": "fake:model",
        "provider_params": {"temperature": 0.0, "fallback_to_default": False},
        "pricing": {"input_per_million": 1.0, "output_per_million": 2.0},
    }

    run = await run_verifier_experiment(
        Path("evaluation/phase3/verifier-benchmark.jsonl"),
        Path("evaluation/phase3/verifier-gold.jsonl"),
        Path("evaluation/phase3/verifier-benchmark-manifest.json"),
        output_dir,
        provider,
        **kwargs,
    )

    assert run["requested"] == run["completed"] == 30
    assert run["usage"]["actual_calls"] < run["usage"]["naive_independent_calls"]
    assert run["usage"]["actual_calls"] <= estimate_verifier_calls(30)["actual_calls"]
    assert run["usage"]["artifact_reuse_calls_saved"] == 450
    assert run["usage"]["stage_calls_skipped"] == 36
    assert provider.fallback_values and set(provider.fallback_values) == {False}
    assert provider.extra_bodies and set(json.dumps(value, sort_keys=True) for value in provider.extra_bodies) == {
        '{"thinking": {"type": "disabled"}}'
    }
    assert (output_dir / "predictions.jsonl").exists()
    assert (output_dir / "metrics.json").exists()
    predictions = [json.loads(line) for line in (output_dir / "predictions.jsonl").read_text().splitlines()]
    assert predictions[0]["call_traces"]
    assert all(
        {"stage", "configuration", "prompt_sha256", "input_sha256"} <= set(trace)
        for trace in predictions[0]["call_traces"]
    )

    calls_before_resume = len(provider.fallback_values)
    await run_verifier_experiment(
        Path("evaluation/phase3/verifier-benchmark.jsonl"),
        Path("evaluation/phase3/verifier-gold.jsonl"),
        Path("evaluation/phase3/verifier-benchmark-manifest.json"),
        output_dir,
        provider,
        **kwargs,
    )
    assert len(provider.fallback_values) == calls_before_resume

    with pytest.raises(ValueError, match="provenance"):
        await run_verifier_experiment(
            Path("evaluation/phase3/verifier-benchmark.jsonl"),
            Path("evaluation/phase3/verifier-gold.jsonl"),
            Path("evaluation/phase3/verifier-benchmark-manifest.json"),
            output_dir,
            provider,
            **{**kwargs, "model_id": "different:model"},
        )


def test_call_estimate_reports_artifact_reuse():
    assert estimate_verifier_calls(30) == {
        "records": 30,
        "actual_calls": 150,
        "naive_independent_calls": 600,
        "artifact_reuse_calls_saved": 450,
    }


@pytest.mark.asyncio
async def test_record_stage_failure_is_persisted_without_aborting_batch(tmp_path):
    output_dir = tmp_path / "run"
    provider = OneMalformedFactProvider()
    run = await run_verifier_experiment(
        Path("evaluation/phase3/verifier-benchmark.jsonl"),
        Path("evaluation/phase3/verifier-gold.jsonl"),
        Path("evaluation/phase3/verifier-benchmark-manifest.json"),
        output_dir,
        provider,
        model_id="fake:model",
        provider_params={"fallback_to_default": False},
        pricing={"input_per_million": 1.0, "output_per_million": 2.0},
    )
    predictions = [json.loads(line) for line in (output_dir / "predictions.jsonl").read_text().splitlines()]

    assert run["completed"] == 30
    assert predictions[0]["stage_statuses"]["fact_check"]["status"] == "failed"
    assert "titles_only" in predictions[0]["stage_statuses"]["fact_check"]["reason"]

    calls_before_retry = len(provider.fallback_values)
    retried = await run_verifier_experiment(
        Path("evaluation/phase3/verifier-benchmark.jsonl"),
        Path("evaluation/phase3/verifier-gold.jsonl"),
        Path("evaluation/phase3/verifier-benchmark-manifest.json"),
        output_dir,
        provider,
        model_id="fake:model",
        provider_params={"fallback_to_default": False},
        pricing={"input_per_million": 1.0, "output_per_million": 2.0},
        retry_failed=True,
    )
    retried_predictions = [json.loads(line) for line in (output_dir / "predictions.jsonl").read_text().splitlines()]

    assert len(provider.fallback_values) - calls_before_retry == 5
    assert retried_predictions[0]["stage_statuses"]["fact_check"]["status"] == "success"
    assert retried_predictions[0]["retry_count"] == 1
    assert retried_predictions[0]["retry_history"][0]["stage_statuses"]["fact_check"]["status"] == "failed"
    assert retried["usage"]["actual_calls"] == run["usage"]["actual_calls"] + 5


@pytest.mark.asyncio
async def test_failed_extraction_has_no_hybrid_or_downstream_score(tmp_path):
    output_dir = tmp_path / "run"
    run = await run_verifier_experiment(
        Path("evaluation/phase3/verifier-benchmark.jsonl"),
        Path("evaluation/phase3/verifier-gold.jsonl"),
        Path("evaluation/phase3/verifier-benchmark-manifest.json"),
        output_dir,
        OneFailedExtractionProvider(),
        model_id="fake:model",
        provider_params={"fallback_to_default": False, "thinking": "disabled"},
        pricing={"input_per_million": 1.0, "output_per_million": 2.0},
    )
    predictions = [json.loads(line) for line in (output_dir / "predictions.jsonl").read_text().splitlines()]
    failed = predictions[0]

    assert failed["stage_statuses"]["claim_extraction"]["status"] == "failed"
    assert failed["extraction"]["hybrid"] == []
    assert all(value is None for value in failed["evidence_scores"].values())
    assert all(value is None for value in failed["score_variants"].values())
    assert failed["provider_attempts"] == 2
    assert run["usage"]["actual_calls"] > run["usage"]["responses_with_usage"]
