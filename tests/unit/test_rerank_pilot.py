from __future__ import annotations

from scripts.run_rerank_experiment import MODEL_IDS, SNAPSHOT_PATH, _read_jsonl, _sha256_file
from scripts.run_rerank_pilot import (
    _excluded_before_batch,
    _pool_record,
    bootstrap_interval,
    coverage_summary,
    decide,
    paired_comparison,
    query_metrics,
    select_batch,
)


def test_batch_selection_is_deterministic_stratified_and_nested():
    snapshot = _read_jsonl(SNAPSHOT_PATH)
    source_hash = _sha256_file(SNAPSHOT_PATH)

    first = select_batch(snapshot, batch=1, source_hash=source_hash)
    repeated = select_batch(snapshot, batch=1, source_hash=source_hash)
    second = select_batch(
        snapshot,
        batch=2,
        source_hash=source_hash,
        excluded_ids={record["query_id"] for record in first},
    )

    assert [record["query_id"] for record in first] == [record["query_id"] for record in repeated]
    assert len(first) == 30
    assert len(second) == 20
    assert all(record["split"] == "test" for record in first + second)
    assert {record["query_id"] for record in first}.isdisjoint(record["query_id"] for record in second)
    assert set(record["query_metadata"]["platform"] for record in first) == {"github", "stackoverflow", "juejin"}


def test_repreparing_batch_excludes_only_earlier_batches():
    selection = {
        "batches": {
            "1": {"query_ids": ["q1", "q2"]},
            "2": {"query_ids": ["q3"]},
        }
    }

    assert _excluded_before_batch(selection, 1) == set()
    assert _excluded_before_batch(selection, 2) == {"q1", "q2"}


def test_pool_record_builds_stable_deduplicated_top3_union():
    record = {
        "query_id": "q1",
        "query": "query",
        "split": "test",
        "query_metadata": {"platform": "github"},
        "candidates": [
            {
                "document_id": f"d{index}",
                "blind_document_id": f"b{index}",
                "text": f"document {index}",
                "source_metadata": {},
            }
            for index in range(1, 8)
        ],
    }
    bge = MODEL_IDS["bge"]
    qwen = MODEL_IDS["qwen3"]
    responses = {
        bge: {"q1": {"outcome": {"items": [{"document_id": value} for value in ("d2", "d4", "d5")]}}},
        qwen: {"q1": {"outcome": {"items": [{"document_id": value} for value in ("d1", "d5", "d6")]}}},
    }

    pooled = _pool_record(record, responses)

    assert [candidate["document_id"] for candidate in pooled["candidates"]] == ["d1", "d2", "d3", "d4", "d5", "d6"]
    assert pooled["rankings"]["none"] == ["d1", "d2", "d3"]
    assert set(pooled["ranking_sha256"]) == {"none", bge, qwen}


def test_top3_metrics_use_only_judged_union():
    record = {
        "candidates": [
            {"document_id": "d1", "blind_document_id": "b1"},
            {"document_id": "d2", "blind_document_id": "b2"},
            {"document_id": "d3", "blind_document_id": "b3"},
            {"document_id": "d4", "blind_document_id": "b4"},
        ]
    }

    metrics = query_metrics(record, ["d2", "d1", "d3"], {"b1": 2, "b2": 0, "b3": 1, "b4": 2})

    assert metrics["mrr_at_3"] == 0.5
    assert metrics["precision_at_3"] == 2 / 3
    assert metrics["irrelevant_top3_rate"] == 1 / 3
    assert metrics["pooled_recall_at_3"] == 2 / 3


def test_coverage_summary_reports_all_zero_queries_and_platforms():
    pool = [
        {
            "query_id": "q1",
            "query_metadata": {"platform": "github"},
            "candidates": [{"blind_document_id": "b1"}],
        },
        {
            "query_id": "q2",
            "query_metadata": {"platform": "github"},
            "candidates": [{"blind_document_id": "b2"}],
        },
    ]

    coverage = coverage_summary(pool, {"b1": 0, "b2": 2})

    assert coverage["answerable_queries"] == 1
    assert coverage["all_zero_query_ids"] == ["q1"]
    assert coverage["platforms"]["github"] == {"queries": 2, "answerable_queries": 1}


def test_bootstrap_and_paired_comparison_are_reproducible():
    first = bootstrap_interval([0.1, 0.2, -0.1], samples=100, seed=7)
    second = bootstrap_interval([0.1, 0.2, -0.1], samples=100, seed=7)
    left = {"q1": {"ndcg_at_3": 1.0}, "q2": {"ndcg_at_3": 0.4}}
    right = {"q1": {"ndcg_at_3": 0.5}, "q2": {"ndcg_at_3": 0.4}}

    assert first == second
    comparison = paired_comparison(left, right)
    assert (comparison["wins"], comparison["ties"], comparison["losses"]) == (1, 1, 0)


def test_decision_selects_clear_model_or_requests_only_one_additional_batch():
    bge = MODEL_IDS["bge"]
    qwen = MODEL_IDS["qwen3"]
    systems = {
        bge: {"failed_queries": 0, "latency_p95_ms": 100, "actual_cost_cny": 0},
        qwen: {"failed_queries": 0, "latency_p95_ms": 150, "actual_cost_cny": 0.01},
    }

    def comparison(mean, interval):
        return {"bootstrap": {"mean": mean, "interval": interval}}

    clear = {
        f"{bge}_vs_none": comparison(0.2, [0.1, 0.3]),
        f"{qwen}_vs_none": comparison(0.05, [-0.02, 0.12]),
        f"{bge}_vs_{qwen}": comparison(0.15, [0.03, 0.25]),
    }
    uncertain = {
        f"{bge}_vs_none": comparison(0.1, [-0.01, 0.2]),
        f"{qwen}_vs_none": comparison(0.08, [-0.02, 0.18]),
        f"{bge}_vs_{qwen}": comparison(0.02, [-0.08, 0.1]),
    }

    assert decide(clear, systems, {}, through_batch=1)["selected_model_id"] == bge
    assert decide(uncertain, systems, {}, through_batch=1)["status"] == "inconclusive_add_batch"
    assert decide(uncertain, systems, {}, through_batch=2)["status"] == "inconclusive"
