from __future__ import annotations

import json
from pathlib import Path

import pytest

from needradar.schemas.schemas import EmotionEnum, ExtractedRequirement, SentimentEnum
from needradar.services.phase3_experiment import run_phase3_experiment, run_phase3_suite


class FakeProvider:
    def __init__(self, outputs: list[ExtractedRequirement]) -> None:
        self.outputs = iter(outputs)
        self.prompts: list[str] = []
        self.texts: list[str] = []
        self._last_usage: dict | None = None

    async def extract_structured(self, prompt: str, text: str, schema, **kwargs):
        self.prompts.append(prompt)
        self.texts.append(text)
        assert kwargs == {"fallback_to_default": False}
        self._last_usage = {
            "input_tokens": 100,
            "output_tokens": 20,
            "cached_tokens": 80,
            "total_tokens": 120,
            "cost_cny": 0.01,
        }
        return next(self.outputs)

    def pop_last_usage(self) -> dict | None:
        usage = self._last_usage
        self._last_usage = None
        return usage


class FakeRetriever:
    def __init__(self, context: str = "historical CSV export request", error: Exception | None = None) -> None:
        self.context = context
        self.error = error
        self.queries: list[str] = []
        self._last_usage: dict | None = None

    async def retrieve_context(self, query: str, **kwargs) -> str:
        self.queries.append(query)
        if self.error:
            raise self.error
        self._last_usage = {
            "input_tokens": 10,
            "output_tokens": 0,
            "total_tokens": 10,
            "cost_cny": 0.001,
        }
        return self.context

    def pop_last_usage(self) -> dict | None:
        usage = self._last_usage
        self._last_usage = None
        return usage

    def get_provenance(self) -> dict:
        return {"corpus_sha256": "fake-corpus", "corpus_records": 1}


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def _fixture_files(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = tmp_path / "project"
    (root / "config").mkdir(parents=True)
    (root / "config" / "prompts.yaml").write_text(
        "requirement_extraction: extract requirement\n",
        encoding="utf-8",
    )
    dataset = tmp_path / "discussions.jsonl"
    gold = tmp_path / "gold.jsonl"
    _write_jsonl(
        dataset,
        [
            {
                "id": "need",
                "platform": "github",
                "source_url": "https://example.test/need",
                "title": "Need CSV export",
                "content": "We repeatedly copy records by hand and need a CSV export for weekly reports.",
                "tags": [],
            }
        ],
    )
    _write_jsonl(
        gold,
        [
            {
                "id": "need",
                "requirement_present": "yes",
                "title": "CSV export",
                "description": "Export records",
                "pain_point": "Manual copying",
                "use_case": "Weekly reports",
                "sentiment": "moderate",
                "emotion": "neutral",
                "evidence_clarity": "clear",
                "human_requirement_reviewed": False,
            }
        ],
    )
    return root, dataset, gold


def _prediction(
    *,
    title: str = "CSV export",
    description: str = "Export records",
    pain_point: str = "Manual copying",
    use_case: str = "Weekly reports",
    sentiment: SentimentEnum = SentimentEnum.MODERATE,
    emotion: EmotionEnum = EmotionEnum.NEUTRAL,
) -> ExtractedRequirement:
    return ExtractedRequirement(
        title=title,
        description=description,
        pain_point=pain_point,
        use_case=use_case,
        sentiment=sentiment,
        emotion=emotion,
        confidence=0.8,
    )


@pytest.mark.asyncio
async def test_no_rag_writes_uniform_artifacts_without_retrieval(tmp_path):
    root, dataset, gold = _fixture_files(tmp_path)
    provider = FakeProvider([_prediction()])
    retriever = FakeRetriever()
    output_dir = tmp_path / "no_rag"

    report = await run_phase3_experiment(
        dataset,
        gold,
        output_dir,
        root,
        provider,
        configuration="no_rag",
        retriever=retriever,
        model_id="fake-model",
    )

    prediction = json.loads((output_dir / "predictions.jsonl").read_text(encoding="utf-8"))
    run = json.loads((output_dir / "run.json").read_text(encoding="utf-8"))
    metrics = json.loads((output_dir / "metrics.json").read_text(encoding="utf-8"))

    assert retriever.queries == []
    assert prediction["configuration"] == "no_rag"
    assert prediction["rag_context_used"] is False
    assert prediction["hitl_edited"] is False
    assert prediction["hitl_edited_fields"] == []
    assert prediction["pre_hitl_prediction"] is None
    assert run["dataset_sha256"]
    assert run["gold_sha256"]
    assert run["prompt_sha256"]
    assert run["usage"]["extraction"]["total_tokens"] == 120
    assert run["usage"]["extraction"]["cached_tokens"] == 80
    assert run["usage"]["retrieval"]["total_tokens"] == 0
    assert metrics["requirement_presence"]["accuracy"] == 1.0
    assert metrics["phase3"]["configuration"] == "no_rag"
    assert report == run


@pytest.mark.asyncio
async def test_rag_injects_context_and_attributes_retrieval_usage(tmp_path):
    root, dataset, gold = _fixture_files(tmp_path)
    provider = FakeProvider([_prediction()])
    retriever = FakeRetriever()
    output_dir = tmp_path / "rag"

    await run_phase3_experiment(
        dataset,
        gold,
        output_dir,
        root,
        provider,
        configuration="rag",
        retriever=retriever,
        model_id="fake-model",
    )

    prediction = json.loads((output_dir / "predictions.jsonl").read_text(encoding="utf-8"))
    run = json.loads((output_dir / "run.json").read_text(encoding="utf-8"))

    assert retriever.queries == ["Need CSV export"]
    assert provider.prompts == ["extract requirement"]
    assert "historical CSV export request" in provider.texts[0]
    assert prediction["rag_context_used"] is True
    assert run["retriever_provenance"]["corpus_sha256"] == "fake-corpus"
    assert run["usage"]["retrieval"]["total_tokens"] == 10
    assert run["usage"]["total"]["total_tokens"] == 130
    assert run["usage"]["total"]["cost_cny"] == pytest.approx(0.011)


@pytest.mark.asyncio
async def test_rag_retrieval_failure_is_not_silently_downgraded(tmp_path):
    root, dataset, gold = _fixture_files(tmp_path)
    provider = FakeProvider([_prediction()])
    retriever = FakeRetriever(error=RuntimeError("index unavailable"))
    output_dir = tmp_path / "rag"

    run = await run_phase3_experiment(
        dataset,
        gold,
        output_dir,
        root,
        provider,
        configuration="rag",
        retriever=retriever,
        model_id="fake-model",
    )

    prediction = json.loads((output_dir / "predictions.jsonl").read_text(encoding="utf-8"))

    assert provider.prompts == []
    assert prediction["requirement_present"] == "error"
    assert prediction["rag_context_used"] is False
    assert "index unavailable" in prediction["retrieval_error"]
    assert run["retrieval_failures"] == 1


@pytest.mark.asyncio
async def test_rag_empty_context_is_an_explicit_failure(tmp_path):
    root, dataset, gold = _fixture_files(tmp_path)
    provider = FakeProvider([_prediction()])

    run = await run_phase3_experiment(
        dataset,
        gold,
        tmp_path / "rag",
        root,
        provider,
        configuration="rag",
        retriever=FakeRetriever(context=""),
        model_id="fake-model",
    )

    assert provider.prompts == []
    assert run["retrieval_failures"] == 1


@pytest.mark.asyncio
async def test_cache_metrics_report_actual_and_no_cache_cost(tmp_path):
    root, dataset, gold = _fixture_files(tmp_path)
    output_dir = tmp_path / "no_rag"

    await run_phase3_experiment(
        dataset,
        gold,
        output_dir,
        root,
        FakeProvider([_prediction()]),
        configuration="no_rag",
        model_id="fake-model",
        provider_params={"temperature": 0.1, "max_tokens": 2000},
        pricing={
            "input_per_million": 1.0,
            "input_cache_hit_per_million": 0.25,
            "output_per_million": 2.0,
        },
    )

    metrics = json.loads((output_dir / "metrics.json").read_text(encoding="utf-8"))
    summary = metrics["phase3"]["summary"]
    assert summary["cached_tokens"] == 80
    assert summary["cache_hit_rate"] == 0.8
    assert summary["cache_savings_cny"] == pytest.approx(0.00006)
    assert summary["cost_cny"] == 0.01
    assert summary["cost_without_cache_cny"] == pytest.approx(0.01006)


@pytest.mark.asyncio
async def test_discussion_content_is_capped_before_rag_context(tmp_path):
    root, dataset, gold = _fixture_files(tmp_path)
    record = json.loads(dataset.read_text(encoding="utf-8"))
    record["content"] = "x" * 49_000
    _write_jsonl(dataset, [record])
    provider = FakeProvider([_prediction()])

    run = await run_phase3_experiment(
        dataset,
        gold,
        tmp_path / "rag",
        root,
        provider,
        configuration="rag",
        retriever=FakeRetriever(context="context " * 200),
        model_id="fake-model",
        max_discussion_chars=47_000,
    )

    assert run["max_discussion_chars"] == 47_000
    assert len(provider.texts[0]) < 50_000
    assert "x" * 47_000 in provider.texts[0]


@pytest.mark.asyncio
async def test_rag_hitl_preserves_pre_review_and_reports_exact_edits(tmp_path):
    root, dataset, gold = _fixture_files(tmp_path)
    provider = FakeProvider(
        [
            _prediction(
                title="Completely unrelated title",
                sentiment=SentimentEnum.STRONG,
            )
        ]
    )
    output_dir = tmp_path / "rag_hitl"

    await run_phase3_experiment(
        dataset,
        gold,
        output_dir,
        root,
        provider,
        configuration="rag_hitl",
        retriever=FakeRetriever(),
        model_id="fake-model",
    )

    prediction = json.loads((output_dir / "predictions.jsonl").read_text(encoding="utf-8"))
    metrics = json.loads((output_dir / "metrics.json").read_text(encoding="utf-8"))

    assert prediction["title"] == "CSV export"
    assert prediction["sentiment"] == "moderate"
    assert prediction["emotion"] == "neutral"
    assert prediction["hitl_edited"] is True
    assert prediction["hitl_edited_fields"] == ["title", "sentiment"]
    assert prediction["pre_hitl_prediction"]["title"] == "Completely unrelated title"
    assert prediction["pre_hitl_prediction"]["sentiment"] == "strong"
    assert metrics["phase3"]["hitl"]["edited_records"] == 1
    assert metrics["phase3"]["hitl"]["edited_fields"] == 2
    assert metrics["phase3"]["pre_hitl"]["categorical_field_accuracy"]["sentiment"]["accuracy"] == 0.0
    assert metrics["categorical_field_accuracy"]["sentiment"]["accuracy"] == 1.0


@pytest.mark.asyncio
async def test_resume_requires_identical_provenance(tmp_path):
    root, dataset, gold = _fixture_files(tmp_path)
    output_dir = tmp_path / "rag"

    await run_phase3_experiment(
        dataset,
        gold,
        output_dir,
        root,
        FakeProvider([_prediction()]),
        configuration="rag",
        retriever=FakeRetriever(),
        model_id="fake-model",
        rag_params={"n_results": 3, "min_score": 0.2, "max_chars": 1500},
    )
    resumed_provider = FakeProvider([])
    run = await run_phase3_experiment(
        dataset,
        gold,
        output_dir,
        root,
        resumed_provider,
        configuration="rag",
        retriever=FakeRetriever(),
        model_id="fake-model",
        rag_params={"n_results": 3, "min_score": 0.2, "max_chars": 1500},
    )

    assert resumed_provider.prompts == []
    assert run["resumed"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changed_field",
    [
        "dataset",
        "gold",
        "prompt",
        "model",
        "configuration",
        "rag_params",
        "provider_params",
        "pricing",
        "max_discussion_chars",
    ],
)
async def test_resume_rejects_changed_provenance(tmp_path, changed_field):
    root, dataset, gold = _fixture_files(tmp_path)
    output_dir = tmp_path / "rag"
    rag_params = {"n_results": 3, "min_score": 0.2, "max_chars": 1500}
    provider_params = {"temperature": 0.1, "max_tokens": 2000}
    pricing = {
        "input_per_million": 1.0,
        "input_cache_hit_per_million": 0.25,
        "output_per_million": 2.0,
    }
    max_discussion_chars = 47_000
    await run_phase3_experiment(
        dataset,
        gold,
        output_dir,
        root,
        FakeProvider([_prediction()]),
        configuration="rag",
        retriever=FakeRetriever(),
        model_id="fake-model",
        rag_params=rag_params,
        provider_params=provider_params,
        pricing=pricing,
        max_discussion_chars=max_discussion_chars,
    )

    configuration = "rag"
    model_id = "fake-model"
    if changed_field == "dataset":
        dataset.write_text(dataset.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    elif changed_field == "gold":
        gold.write_text(gold.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    elif changed_field == "prompt":
        (root / "config" / "prompts.yaml").write_text(
            "requirement_extraction: changed prompt\n",
            encoding="utf-8",
        )
    elif changed_field == "model":
        model_id = "different-model"
    elif changed_field == "configuration":
        configuration = "no_rag"
    elif changed_field == "rag_params":
        rag_params = {**rag_params, "n_results": 5}
    elif changed_field == "provider_params":
        provider_params = {**provider_params, "temperature": 0.2}
    elif changed_field == "pricing":
        pricing = {**pricing, "input_per_million": 2.0}
    else:
        max_discussion_chars = 46_000

    with pytest.raises(ValueError, match="provenance"):
        await run_phase3_experiment(
            dataset,
            gold,
            output_dir,
            root,
            FakeProvider([]),
            configuration=configuration,
            retriever=FakeRetriever(),
            model_id=model_id,
            rag_params=rag_params,
            provider_params=provider_params,
            pricing=pricing,
            max_discussion_chars=max_discussion_chars,
        )


@pytest.mark.asyncio
async def test_suite_uses_no_rag_as_the_comparison_baseline(tmp_path):
    root, dataset, gold = _fixture_files(tmp_path)
    output_root = tmp_path / "phase3"
    provider = FakeProvider([_prediction(), _prediction(), _prediction()])

    runs = await run_phase3_suite(
        dataset,
        gold,
        output_root,
        root,
        provider,
        retriever=FakeRetriever(),
        model_id="fake-model",
    )

    assert set(runs) == {"no_rag", "rag", "rag_hitl"}
    predictions = [
        json.loads((output_root / configuration / "predictions.jsonl").read_text(encoding="utf-8"))
        for configuration in runs
    ]
    assert len({tuple(prediction) for prediction in predictions}) == 1
    rag_metrics = json.loads((output_root / "rag" / "metrics.json").read_text(encoding="utf-8"))
    comparison = rag_metrics["phase3"]["baseline_comparison"]
    assert comparison["status"] == "available"
    assert comparison["metrics"]["requirement_presence_accuracy"]["absolute_change"] == 0.0
    assert runs["no_rag"]["usage"]["total"]["total_tokens"] == 120
    assert runs["rag"]["usage"]["total"]["total_tokens"] == 130
    assert runs["rag_hitl"]["usage"]["total"]["total_tokens"] == 130
