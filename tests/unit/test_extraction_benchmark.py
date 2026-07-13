import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from needradar.schemas.schemas import EmotionEnum, ExtractedRequirement, SentimentEnum
from needradar.services.extraction_benchmark import run_extraction_benchmark


@pytest.mark.asyncio
async def test_benchmark_rejects_rule_noise_and_extracts_relevant_item(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "prompts.yaml").write_text(
        "requirement_extraction: extract\n", encoding="utf-8"
    )
    dataset = tmp_path / "discussions.jsonl"
    records = [
        {
            "id": "short",
            "platform": "github",
            "source_url": "https://example.test/short",
            "title": "Short",
            "content": "tiny",
            "tags": [],
        },
        {
            "id": "relevant",
            "platform": "github",
            "source_url": "https://example.test/relevant",
            "title": "Need CSV export",
            "content": "We repeatedly copy records by hand and need a CSV export for weekly reports.",
            "tags": [],
        },
    ]
    dataset.write_text(
        "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
    )
    provider = MagicMock()
    provider.extract_structured = AsyncMock(
        return_value=ExtractedRequirement(
            title="CSV export",
            description="Export records",
            pain_point="Manual copying",
            use_case="Weekly reports",
            sentiment=SentimentEnum.MODERATE,
            emotion=EmotionEnum.NEUTRAL,
            confidence=0.9,
        )
    )
    provider.pop_last_usage.return_value = {
        "input_tokens": 100,
        "output_tokens": 20,
        "total_tokens": 120,
        "cost_cny": 0.01,
    }
    output = tmp_path / "predictions.jsonl"

    report = await run_extraction_benchmark(dataset, output, tmp_path, provider)
    predictions = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]

    assert [prediction["requirement_present"] for prediction in predictions] == ["no", "yes"]
    assert predictions[0]["rejection_reason"]
    assert predictions[1]["title"] == "CSV export"
    provider.extract_structured.assert_awaited_once()
    assert report["usage_this_run"]["cost_cny"] == 0.01
    assert report["rag_enabled"] is False


@pytest.mark.asyncio
async def test_benchmark_resumes_existing_predictions(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "prompts.yaml").write_text(
        "requirement_extraction: extract\n", encoding="utf-8"
    )
    record = {
        "id": "done",
        "platform": "github",
        "source_url": "https://example.test/done",
        "title": "Done",
        "content": "Already processed content that is long enough for the filter to accept it.",
    }
    dataset = tmp_path / "discussions.jsonl"
    dataset.write_text(json.dumps(record) + "\n", encoding="utf-8")
    output = tmp_path / "predictions.jsonl"
    output.write_text(
        json.dumps({"id": "done", "requirement_present": "no"}) + "\n",
        encoding="utf-8",
    )
    provider = MagicMock()

    report = await run_extraction_benchmark(dataset, output, tmp_path, provider)

    assert report["completed"] == 1
    assert report["resumed"] == 1
    provider.extract_structured.assert_not_called()


@pytest.mark.asyncio
async def test_benchmark_retries_and_records_persistent_parse_failure(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "prompts.yaml").write_text(
        "requirement_extraction: extract\n", encoding="utf-8"
    )
    record = {
        "id": "broken",
        "platform": "github",
        "source_url": "https://example.test/broken",
        "title": "Need a reliable export feature",
        "content": "The current manual export workflow repeatedly fails and wastes significant time.",
    }
    dataset = tmp_path / "discussions.jsonl"
    dataset.write_text(json.dumps(record) + "\n", encoding="utf-8")
    provider = MagicMock()
    provider.extract_structured = AsyncMock(side_effect=ValueError("invalid JSON"))
    provider.pop_last_usage.return_value = {"total_tokens": 10, "cost_cny": 0.001}
    output = tmp_path / "predictions.jsonl"

    report = await run_extraction_benchmark(dataset, output, tmp_path, provider)
    prediction = json.loads(output.read_text(encoding="utf-8"))

    assert provider.extract_structured.await_count == 2
    assert prediction["requirement_present"] == "error"
    assert "invalid JSON" in prediction["extraction_error"]
    assert report["extraction_failures"] == 1
    assert report["usage_this_run"]["cost_cny"] == 0.002
