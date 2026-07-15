from __future__ import annotations

import csv
import io
import json
from types import SimpleNamespace

import pytest

from needradar.services.reranker import RerankedDocument, RerankerError, RerankOutcome, RerankUsage
from scripts.run_rerank_experiment import (
    MODEL_IDS,
    REQUEST_OPTIONS,
    SINGLE_EXPERT_EXACT_AGREEMENT_MINIMUM,
    SINGLE_EXPERT_PROTOCOL,
    SINGLE_EXPERT_RETEST_FRACTION,
    SINGLE_EXPERT_REVIEW_METHOD,
    SINGLE_EXPERT_WEIGHTED_KAPPA_MINIMUM,
    _cached_cost_metrics,
    _clear_failure,
    _deterministic_retest_ids,
    _failures_for_snapshot,
    _load_completed_labels,
    _negative_cases,
    _quadratic_weighted_kappa,
    _sha256_file,
    _slice_groups,
    _upsert_failure,
    _verification_scope_note,
    cache_key,
    calibrate_gate_threshold,
    decide_selection,
    dry_run,
    execute_experiment,
    freeze_candidates,
    ranking_metrics,
    validate_hash_manifest,
    write_hash_manifest,
)


class FakeRetriever:
    async def retrieve_hybrid(self, query: str, n_results: int):
        assert n_results == 20
        return [
            SimpleNamespace(
                id=f"doc-{index}",
                document=f"document {index}",
                metadata={
                    "platform": "github",
                    "title": f"Document {index}",
                    "recall": {"mode": "hybrid_rrf", "dense_rank": index + 1},
                },
                score=1.0 - index / 100,
            )
            for index in range(20)
        ]

    def get_provenance(self):
        return {"embedding_backend": "fake", "corpus_sha256": "fake"}


def _write_jsonl(path, records):
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")


@pytest.mark.asyncio
async def test_freeze_writes_hashed_snapshot_and_blank_blind_annotation(tmp_path):
    query_path = tmp_path / "queries.jsonl"
    corpus_path = tmp_path / "corpus.jsonl"
    snapshot_path = tmp_path / "candidates.jsonl"
    manifest_path = tmp_path / "manifest.json"
    annotation_path = tmp_path / "annotation.csv"
    _write_jsonl(
        query_path,
        [{"id": "query-1", "title": "CSV export", "platform": "github", "source_url": "https://example.test"}],
    )
    _write_jsonl(corpus_path, [{"id": "corpus"}])

    manifest = await freeze_candidates(
        query_path,
        corpus_path,
        snapshot_path,
        manifest_path,
        annotation_path,
        retriever=FakeRetriever(),
    )

    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    annotation = annotation_path.read_text(encoding="utf-8")
    assert len(snapshot["candidates"]) == 20
    assert manifest["data"]["candidate_count"] == 20
    assert manifest["data"]["recall_latency_sha256"]
    assert manifest["data"]["relevance_labels"] == "missing_human_labels"
    assert manifest["recall"]["claimed_hybrid"] is True
    assert manifest["recall"]["fusion"] == {"method": "reciprocal_rank_fusion", "rrf_k": 60}
    assert "original_rank" not in annotation.splitlines()[0]
    assert all(line.endswith(",") for line in annotation.splitlines()[1:])
    assert (tmp_path / "recall-latency.jsonl").exists()
    assert (tmp_path / "labels-manifest-template.json").exists()


@pytest.mark.asyncio
async def test_freeze_rejects_dense_fallback_as_hybrid_evidence(tmp_path):
    query_path = tmp_path / "queries.jsonl"
    corpus_path = tmp_path / "corpus.jsonl"
    _write_jsonl(query_path, [{"id": "query-1", "title": "CSV export"}])
    _write_jsonl(corpus_path, [{"id": "corpus"}])

    class DenseFallbackRetriever(FakeRetriever):
        async def retrieve_hybrid(self, query: str, n_results: int):
            results = await super().retrieve_hybrid(query, n_results)
            results[0].metadata["recall"] = {"mode": "dense_fallback"}
            return results

    with pytest.raises(RuntimeError, match="genuine hybrid recall"):
        await freeze_candidates(
            query_path,
            corpus_path,
            tmp_path / "candidates.jsonl",
            tmp_path / "manifest.json",
            tmp_path / "annotation.csv",
            retriever=DenseFallbackRetriever(),
        )


def test_dry_run_reports_requests_token_ceiling_and_price(tmp_path):
    snapshot = tmp_path / "candidates.jsonl"
    _write_jsonl(
        snapshot,
        [
            {
                "query_id": "q1",
                "query": "query",
                "split": "test",
                "candidates": [{"document_id": "d1", "text": "abc", "original_rank": 1, "original_score": 0.5}],
            }
        ],
    )

    estimate = dry_run(snapshot)

    assert estimate["provider_requests"] == 2
    assert estimate["models"][MODEL_IDS["bge"]]["cost_upper_bound_cny"] == 0
    assert estimate["models"][MODEL_IDS["qwen3"]]["cost_upper_bound_cny"] > 0
    assert estimate["proposed_budget_sufficient"] is True
    assert estimate["quality_selection_status"] == "blocked_missing_human_relevance_labels"


@pytest.mark.asyncio
async def test_execute_caches_success_resumes_and_records_execution(tmp_path):
    snapshot = tmp_path / "candidates.jsonl"
    cache_dir = tmp_path / "cache"
    failures = tmp_path / "failures.jsonl"
    manifest = tmp_path / "manifest.json"
    _write_jsonl(
        snapshot,
        [
            {
                "query_id": "q1",
                "query": "query",
                "split": "test",
                "candidates": [
                    {
                        "document_id": "d1",
                        "text": "document",
                        "original_rank": 1,
                        "original_score": 0.5,
                        "source_metadata": {"platform": "github"},
                    }
                ],
            }
        ],
    )
    manifest.write_text("{}\n", encoding="utf-8")

    class FakeReranker:
        calls = 0

        def __init__(self, **kwargs):
            pass

        async def rerank(self, query, candidates, **kwargs):
            type(self).calls += 1
            candidate = candidates[0]
            return RerankOutcome(
                items=[
                    RerankedDocument(
                        document_id=candidate.document_id,
                        text=candidate.text,
                        original_rank=candidate.original_rank,
                        original_score=candidate.original_score,
                        reranked_rank=1,
                        relevance_score=0.9,
                        metadata=candidate.metadata,
                    )
                ],
                provider="siliconflow",
                requested_model_id=MODEL_IDS["qwen3"],
                returned_model_id=None,
                request_id="request-1",
                latency_ms=5.0,
                usage=RerankUsage(input_tokens=100, total_tokens=100),
                retry_count=0,
                degraded=False,
            )

        async def close(self):
            pass

    first = await execute_experiment(
        snapshot,
        modes=("qwen3",),
        max_cost_cny=0.01,
        cache_dir=cache_dir,
        manifest_path=manifest,
        failures_path=failures,
        api_key="test-key",
        reranker_factory=FakeReranker,
    )
    second = await execute_experiment(
        snapshot,
        modes=("qwen3",),
        max_cost_cny=0.01,
        cache_dir=cache_dir,
        manifest_path=manifest,
        failures_path=failures,
        api_key="test-key",
        reranker_factory=FakeReranker,
    )

    assert first["completed"] == 1
    assert first["provider_attempts"] == 1
    assert second["completed"] == 0
    assert second["resumed"] == 1
    assert FakeReranker.calls == 1
    assert len(list(cache_dir.glob("*.json"))) == 1
    executions = json.loads(manifest.read_text(encoding="utf-8"))["executions"]
    assert [execution["status"] for execution in executions] == ["completed", "completed"]


@pytest.mark.asyncio
async def test_execute_is_fail_closed_and_records_three_failure_stop(tmp_path):
    snapshot = tmp_path / "candidates.jsonl"
    cache_dir = tmp_path / "cache"
    failures = tmp_path / "failures.jsonl"
    manifest = tmp_path / "manifest.json"
    _write_jsonl(
        snapshot,
        [
            {
                "query_id": f"q{index}",
                "query": f"query {index}",
                "split": "test",
                "candidates": [
                    {
                        "document_id": f"d{index}",
                        "text": "document",
                        "original_rank": 1,
                        "original_score": 0.5,
                        "source_metadata": {},
                    }
                ],
            }
            for index in range(3)
        ],
    )
    manifest.write_text("{}\n", encoding="utf-8")

    class FailingReranker:
        def __init__(self, **kwargs):
            pass

        async def rerank(self, query, candidates, **kwargs):
            raise RerankerError("provider unavailable", error_type="server_error", retry_count=2)

        async def close(self):
            pass

    with pytest.raises(RuntimeError, match="stop condition"):
        await execute_experiment(
            snapshot,
            modes=("bge",),
            max_cost_cny=0.01,
            cache_dir=cache_dir,
            manifest_path=manifest,
            failures_path=failures,
            api_key="test-key",
            reranker_factory=FailingReranker,
        )

    failure_records = [json.loads(line) for line in failures.read_text(encoding="utf-8").splitlines()]
    assert len(failure_records) == 3
    assert all(record["error_type"] == "server_error" for record in failure_records)
    assert not list(cache_dir.glob("*.json"))
    execution = json.loads(manifest.read_text(encoding="utf-8"))["executions"][0]
    assert execution["status"] == "stopped"
    assert execution["provider_attempts"] == 9


def test_cache_key_changes_with_each_provenance_component():
    record = {"query": "query", "candidates": [{"document_id": "d1", "text": "one"}]}
    key, parts = cache_key("model-a", record, {"top_k": 20})

    assert key == cache_key("model-a", record, {"top_k": 20})[0]
    assert key != cache_key("model-b", record, {"top_k": 20})[0]
    assert key != cache_key("model-a", {**record, "query": "other"}, {"top_k": 20})[0]
    assert key != cache_key("model-a", record, {"top_k": 3})[0]
    assert set(parts) == {"model_id", "query_hash", "candidate_set_hash", "request_options_hash"}


def test_cached_cost_metrics_read_cost_from_cache_record():
    records = {
        "q1": {"cost_cny": 0.0004, "outcome": {"usage": {"input_tokens": 10}}},
        "q2": {"cost_cny": 0.0006, "outcome": {"usage": {"input_tokens": 20}}},
    }

    metrics = _cached_cost_metrics(records)

    assert metrics["actual_cost_cny"] == pytest.approx(0.001)
    assert metrics["cost_per_successful_query_cny"] == pytest.approx(0.0005)
    assert _cached_cost_metrics({}) == {
        "actual_cost_cny": 0,
        "cost_per_successful_query_cny": None,
    }


def test_verification_scope_note_distinguishes_smoke_from_full_evidence():
    assert "remains unverified" in _verification_scope_note(0)
    smoke_note = _verification_scope_note(2)
    assert "2 successful" in smoke_note
    assert "does not establish full frozen-set quality" in smoke_note


def test_hash_manifest_detects_artifact_drift(tmp_path):
    artifact = tmp_path / "artifact.json"
    hashes = tmp_path / "hashes.json"
    artifact.write_text('{"value":1}\n', encoding="utf-8")

    written = write_hash_manifest([artifact], hashes, root=tmp_path)

    assert validate_hash_manifest(hashes, root=tmp_path) == written
    artifact.write_text('{"value":2}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="artifact hash mismatch"):
        validate_hash_manifest(hashes, root=tmp_path)


def test_failures_are_upserted_cleared_and_filtered_by_current_cache_key(tmp_path):
    path = tmp_path / "failures.jsonl"
    record = {
        "query_id": "q1",
        "query": "query",
        "split": "test",
        "candidates": [{"document_id": "d1", "text": "one"}],
    }
    model_id = MODEL_IDS["bge"]
    _, parts = cache_key(model_id, record, REQUEST_OPTIONS)
    first = {"model_id": model_id, "query_id": "q1", **parts, "error_type": "timeout"}
    latest = {**first, "error_type": "server_error"}

    _upsert_failure(path, first)
    _upsert_failure(path, latest)

    failures = _failures_for_snapshot([record], {}, path)
    assert len(failures) == 1
    assert failures[0]["error_type"] == "server_error"
    assert _failures_for_snapshot([record], {model_id: {"q1": {}}}, path) == []

    _clear_failure(path, model_id=model_id, query_id="q1")
    assert path.read_text(encoding="utf-8") == ""


def test_ranking_metrics_are_deterministic_for_graded_labels():
    snapshot = {
        "q1": {
            "query_id": "q1",
            "split": "test",
            "candidates": [
                {"document_id": "d1", "blind_document_id": "b1"},
                {"document_id": "d2", "blind_document_id": "b2"},
                {"document_id": "d3", "blind_document_id": "b3"},
            ],
        }
    }

    metrics = ranking_metrics({"q1": ["d2", "d1", "d3"]}, snapshot, {"b1": 2, "b2": 0, "b3": 1})

    assert metrics["valid_queries"] == 1
    assert metrics["mrr_at_10"] == 0.5
    assert metrics["candidate_recall_at_3"] == 1.0
    assert metrics["precision_at_3"] == pytest.approx(2 / 3)
    assert metrics["irrelevant_top3_rate"] == pytest.approx(1 / 3)


def test_completed_labels_require_hash_two_reviewers_and_adjudication(tmp_path):
    labels_path = tmp_path / "labels.csv"
    labels_manifest_path = tmp_path / "labels.manifest.json"
    snapshot = [
        {
            "candidates": [
                {"document_id": "d1", "blind_document_id": "b1"},
                {"document_id": "d2", "blind_document_id": "b2"},
            ]
        }
    ]
    labels_path.write_text("blind_document_id,relevance_grade\nb1,2\nb2,0\n", encoding="utf-8")
    provenance = {
        "labels_sha256": _sha256_file(labels_path),
        "reviewer_count": 2,
        "independent_review": True,
        "adjudicated": True,
        "completed_at": "2026-07-15T00:00:00Z",
    }
    labels_manifest_path.write_text(json.dumps(provenance), encoding="utf-8")

    loaded = _load_completed_labels(labels_path, snapshot, labels_manifest_path)

    assert loaded == ({"b1": 2, "b2": 0}, provenance)
    provenance["adjudicated"] = False
    labels_manifest_path.write_text(json.dumps(provenance), encoding="utf-8")
    assert _load_completed_labels(labels_path, snapshot, labels_manifest_path) is None


def test_completed_labels_accept_verified_single_expert_test_retest(tmp_path):
    labels_path = tmp_path / "labels-adjudicated.csv"
    first_path = tmp_path / "reviewer-single.csv"
    retest_path = tmp_path / "reviewer-retest.csv"
    manifest_path = tmp_path / "labels-adjudicated.manifest.json"
    source_path = tmp_path / "annotation-template.csv"
    source_path.write_text("frozen blind template\n", encoding="utf-8")
    source_hash = _sha256_file(source_path)
    blind_ids = {f"b{index:02d}" for index in range(20)}
    retest_ids = _deterministic_retest_ids(source_hash, blind_ids)
    grades = {blind_id: 0 for blind_id in blind_ids}
    grades[retest_ids[1]] = 2

    def write_grades(path, selected_ids):
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=["blind_document_id", "relevance_grade", "notes"])
        writer.writeheader()
        writer.writerows(
            {"blind_document_id": blind_id, "relevance_grade": grades[blind_id], "notes": ""}
            for blind_id in sorted(selected_ids)
        )
        path.write_text(buffer.getvalue(), encoding="utf-8")

    write_grades(labels_path, blind_ids)
    write_grades(first_path, blind_ids)
    write_grades(retest_path, retest_ids)
    manifest = {
        "schema_version": 2,
        "labels_sha256": _sha256_file(labels_path),
        "first_pass_path": first_path.name,
        "first_pass_sha256": _sha256_file(first_path),
        "retest_path": retest_path.name,
        "retest_sha256": _sha256_file(retest_path),
        "source_template_sha256": source_hash,
        "protocol_version": SINGLE_EXPERT_PROTOCOL,
        "review_method": SINGLE_EXPERT_REVIEW_METHOD,
        "reviewer_count": 1,
        "independent_review": False,
        "system_blinded": True,
        "adjudicated": True,
        "all_disagreements_adjudicated": True,
        "candidate_count": len(blind_ids),
        "retest_fraction": SINGLE_EXPERT_RETEST_FRACTION,
        "retest_sample_count": len(retest_ids),
        "retest_delay_hours": 48.0,
        "exact_agreement": 1.0,
        "weighted_kappa": 1.0,
        "disagreement_count": 0,
        "acceptance": {
            "exact_agreement_minimum": SINGLE_EXPERT_EXACT_AGREEMENT_MINIMUM,
            "weighted_kappa_minimum": SINGLE_EXPERT_WEIGHTED_KAPPA_MINIMUM,
            "passed": True,
        },
        "first_pass_completed_at": "2026-07-13T00:00:00Z",
        "retest_started_at": "2026-07-15T00:00:00Z",
        "retest_completed_at": "2026-07-15T01:00:00Z",
        "completed_at": "2026-07-15T01:10:00Z",
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    snapshot = [{"candidates": [{"blind_document_id": blind_id} for blind_id in sorted(blind_ids)]}]

    loaded = _load_completed_labels(labels_path, snapshot, manifest_path, source_path)

    assert loaded == (grades, manifest)
    manifest["exact_agreement"] = 0.84
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert _load_completed_labels(labels_path, snapshot, manifest_path, source_path) is None


def test_quadratic_weighted_kappa_handles_perfect_and_degenerate_labels():
    ids = ["a", "b", "c"]

    assert _quadratic_weighted_kappa({"a": 0, "b": 1, "c": 2}, {"a": 0, "b": 1, "c": 2}, ids) == 1.0
    assert _quadratic_weighted_kappa({"a": 1, "b": 1, "c": 1}, {"a": 1, "b": 1, "c": 1}, ids) is None


def test_gate_threshold_is_calibrated_only_on_dev_split():
    snapshot = {
        "q-dev": {
            "query_id": "q-dev",
            "split": "dev",
            "candidates": [
                {"document_id": "d1", "blind_document_id": "b1"},
                {"document_id": "d2", "blind_document_id": "b2"},
            ],
        },
        "q-test": {
            "query_id": "q-test",
            "split": "test",
            "candidates": [{"document_id": "d3", "blind_document_id": "b3"}],
        },
    }
    records = {
        "q-dev": {
            "query_id": "q-dev",
            "outcome": {
                "items": [
                    {"document_id": "d1", "relevance_score": 0.9},
                    {"document_id": "d2", "relevance_score": 0.2},
                ]
            },
        },
        "q-test": {
            "query_id": "q-test",
            "outcome": {"items": [{"document_id": "d3", "relevance_score": 0.99}]},
        },
    }

    calibration = calibrate_gate_threshold(records, snapshot, {"b1": 1, "b2": 0, "b3": 0})

    assert calibration is not None
    assert calibration["threshold"] == 0.9
    assert calibration["dev_f1"] == 1.0


def test_selection_rules_choose_dominant_model_or_preserve_tradeoff():
    def metrics(value, irrelevant):
        return {
            "valid_queries": 10,
            "mrr_at_10": value,
            "ndcg_at_10": value,
            "candidate_recall_at_3": value,
            "precision_at_3": value,
            "irrelevant_top3_rate": irrelevant,
        }

    bge = MODEL_IDS["bge"]
    qwen = MODEL_IDS["qwen3"]
    quality = {
        "none": metrics(0.5, 0.5),
        bge: metrics(0.6, 0.4),
        qwen: metrics(0.4, 0.6),
        "platform_slices": {},
    }
    systems = {
        bge: {"failed_queries": 0, "latency_p95_ms": 20, "actual_cost_cny": 0},
        qwen: {"failed_queries": 0, "latency_p95_ms": 30, "actual_cost_cny": 0.1},
    }

    selected = decide_selection(quality, systems, (bge, qwen))
    assert selected["status"] == "selected"
    assert selected["selected_model_id"] == bge

    quality[qwen] = metrics(0.7, 0.3)
    tradeoff = decide_selection(quality, systems, (bge, qwen))
    assert tradeoff["status"] == "pareto_tradeoff"
    assert tradeoff["selected_model_id"] is None


def test_slices_and_negative_cases_are_derived_from_frozen_records():
    snapshot = [
        {
            "query_id": "q1",
            "query": "导出 CSV",
            "split": "test",
            "query_metadata": {"platform": "github"},
            "candidates": [
                {"document_id": "d1", "blind_document_id": "b1", "text": "x" * 100},
                {"document_id": "d2", "blind_document_id": "b2", "text": "y" * 100},
            ],
        }
    ]
    groups = _slice_groups(snapshot)
    assert groups["platform"]["github"] == {"q1"}
    assert groups["query_language"]["mixed"] == {"q1"}
    assert groups["candidate_length"]["short_lt_500"] == {"q1"}

    rankings = {"none": {"q1": ["d1", "d2"]}, "model": {"q1": ["d2", "d1"]}}
    cases = _negative_cases(rankings, {"q1": snapshot[0]}, {"b1": 2, "b2": 0})
    assert cases["model"][0]["query_id"] == "q1"
    assert cases["model"][0]["ndcg_at_10_change"] < 0
