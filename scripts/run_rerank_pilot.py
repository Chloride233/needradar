"""Prepare, execute, annotate, and report the reduced Top-3 rerank pilot."""

from __future__ import annotations

import argparse
import asyncio
import csv
import io
import json
import math
import random
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from needradar.services.reranker import MODEL_IDS

if __package__:
    from scripts.run_rerank_experiment import (
        CACHE_DIR,
        MODEL_MODES,
        ROOT,
        SNAPSHOT_PATH,
        _cached_cost_metrics,
        _hash_value,
        _load_completed_labels,
        _percentile,
        _read_jsonl,
        _responses_for_snapshot,
        _sha256_file,
        _write_jsonl,
        dry_run,
        execute_experiment,
        validate_frozen_artifacts,
        validate_hash_manifest,
        write_hash_manifest,
    )
else:
    from run_rerank_experiment import (
        CACHE_DIR,
        MODEL_MODES,
        ROOT,
        SNAPSHOT_PATH,
        _cached_cost_metrics,
        _hash_value,
        _load_completed_labels,
        _percentile,
        _read_jsonl,
        _responses_for_snapshot,
        _sha256_file,
        _write_jsonl,
        dry_run,
        execute_experiment,
        validate_frozen_artifacts,
        validate_hash_manifest,
        write_hash_manifest,
    )

PILOT_DIR = ROOT / "evaluation" / "rerank" / "pilot"
SELECTION_PATH = PILOT_DIR / "selection.json"
MANIFEST_PATH = PILOT_DIR / "manifest.json"
POOL_PATH = PILOT_DIR / "pool.jsonl"
ANNOTATION_PATH = PILOT_DIR / "annotation-template.csv"
LABELS_PATH = PILOT_DIR / "labels-adjudicated.csv"
LABELS_MANIFEST_PATH = PILOT_DIR / "labels-adjudicated.manifest.json"
REPORT_JSON_PATH = PILOT_DIR / "report.json"
REPORT_MD_PATH = PILOT_DIR / "report.md"
HASHES_PATH = PILOT_DIR / "artifact-hashes.json"
FAILURES_PATH = PILOT_DIR / "failures.jsonl"

BATCH_SIZES = {1: 30, 2: 20}
TOP_K = 3
BOOTSTRAP_SAMPLES = 10_000
BOOTSTRAP_SEED = 20260715
REVIEW_COLUMNS = (
    "query_id",
    "query",
    "split",
    "blind_document_id",
    "platform",
    "title",
    "text_excerpt",
    "relevance_grade",
    "notes",
)


def query_language(query: str) -> str:
    has_cjk = any("\u4e00" <= char <= "\u9fff" for char in query)
    has_latin = any(char.isascii() and char.isalpha() for char in query)
    return "mixed" if has_cjk and has_latin else "cjk" if has_cjk else "non_cjk"


def _stratum(record: dict[str, Any]) -> tuple[str, str]:
    platform = record["query_metadata"].get("platform", "unknown") or "unknown"
    return platform, query_language(record["query"])


def _largest_remainder_quotas(groups: dict[tuple[str, str], list[dict[str, Any]]], size: int) -> dict:
    total = sum(len(records) for records in groups.values())
    if size > total:
        raise ValueError(f"cannot select {size} queries from {total} eligible records")
    raw = {key: size * len(records) / total for key, records in groups.items()}
    quotas = {key: math.floor(value) for key, value in raw.items()}
    remaining = size - sum(quotas.values())
    order = sorted(groups, key=lambda key: (-(raw[key] - quotas[key]), key))
    for key in order[:remaining]:
        quotas[key] += 1
    return quotas


def select_batch(
    snapshot: list[dict[str, Any]],
    *,
    batch: int,
    source_hash: str,
    excluded_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    if batch not in BATCH_SIZES:
        raise ValueError(f"unsupported pilot batch: {batch}")
    excluded = excluded_ids or set()
    eligible = [record for record in snapshot if record["split"] == "test" and record["query_id"] not in excluded]
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in eligible:
        groups[_stratum(record)].append(record)
    quotas = _largest_remainder_quotas(groups, BATCH_SIZES[batch])
    selected = []
    for key in sorted(groups):
        ordered = sorted(
            groups[key],
            key=lambda record: _hash_value([source_hash, batch, record["query_id"]]),
        )
        selected.extend(ordered[: quotas[key]])
    return sorted(selected, key=lambda record: record["query_id"])


def _batch_snapshot_path(batch: int) -> Path:
    return PILOT_DIR / f"batch-{batch}-candidates.jsonl"


def _selection_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    strata: dict[str, int] = {}
    for record in records:
        key = "/".join(_stratum(record))
        strata[key] = strata.get(key, 0) + 1
    return {
        "query_count": len(records),
        "query_ids": [record["query_id"] for record in records],
        "selection_sha256": _hash_value([record["query_id"] for record in records]),
        "strata": dict(sorted(strata.items())),
    }


def _excluded_before_batch(selection: dict[str, Any] | None, batch: int) -> set[str]:
    return {
        query_id
        for batch_number, batch_record in (selection or {}).get("batches", {}).items()
        if int(batch_number) < batch
        for query_id in batch_record["query_ids"]
    }


def prepare_batch(batch: int) -> dict[str, Any]:
    if HASHES_PATH.exists():
        validate_hash_manifest(HASHES_PATH, root=ROOT)
    frozen = validate_frozen_artifacts()
    snapshot = _read_jsonl(SNAPSHOT_PATH)
    previous = json.loads(SELECTION_PATH.read_text(encoding="utf-8")) if SELECTION_PATH.exists() else None
    if batch == 2:
        if previous is None or "1" not in previous.get("batches", {}):
            raise RuntimeError("prepare Batch 1 before Batch 2")
        if not REPORT_JSON_PATH.exists():
            raise RuntimeError("Batch 2 requires an inconclusive Batch 1 report")
        report = json.loads(REPORT_JSON_PATH.read_text(encoding="utf-8"))
        if report.get("selection", {}).get("status") != "inconclusive_add_batch":
            raise RuntimeError("Batch 2 is allowed only after an inconclusive Batch 1 report")
    excluded = _excluded_before_batch(previous, batch)
    records = select_batch(
        snapshot,
        batch=batch,
        source_hash=frozen["data"]["candidate_snapshot_sha256"],
        excluded_ids=excluded,
    )
    PILOT_DIR.mkdir(parents=True, exist_ok=True)
    batch_path = _batch_snapshot_path(batch)
    _write_jsonl(batch_path, records)
    selection = previous or {
        "schema_version": 1,
        "candidate_snapshot_path": str(SNAPSHOT_PATH.relative_to(ROOT)),
        "candidate_snapshot_sha256": frozen["data"]["candidate_snapshot_sha256"],
        "eligible_split": "test",
        "stratification": ["platform", "query_language"],
        "batches": {},
    }
    selection["batches"][str(batch)] = {
        **_selection_summary(records),
        "snapshot_path": str(batch_path.relative_to(ROOT)),
        "snapshot_sha256": _sha256_file(batch_path),
    }
    selection["updated_at"] = datetime.now(timezone.utc).isoformat()
    SELECTION_PATH.write_text(json.dumps(selection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8")) if MANIFEST_PATH.exists() else {}
    manifest.update(
        {
            "schema_version": 1,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "candidate_snapshot_sha256": frozen["data"]["candidate_snapshot_sha256"],
            "selection_path": str(SELECTION_PATH.relative_to(ROOT)),
            "selection_sha256": _sha256_file(SELECTION_PATH),
            "top_k": TOP_K,
            "models": [MODEL_IDS[mode] for mode in MODEL_MODES],
            "review_method": "single_expert_blind_test_retest",
            "unsupported_claims": ["MRR@10", "nDCG@10", "full Recall@3", "gate calibration"],
        }
    )
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    estimate = dry_run(batch_path)
    cached = _responses_for_snapshot(records, CACHE_DIR)
    cached_successes = sum(len(cached.get(MODEL_IDS[mode] or "", {})) for mode in MODEL_MODES)
    estimate["batch"] = batch
    estimate["selection_sha256"] = selection["batches"][str(batch)]["selection_sha256"]
    estimate["successful_cache_records"] = cached_successes
    estimate["new_provider_requests"] = estimate["provider_requests"] - cached_successes
    estimate["full_experiment_budget_reference_cny"] = estimate.pop("proposed_hard_budget_cny")
    recommended_budget = math.ceil(estimate["total_cost_upper_bound_cny"] * 100) / 100
    estimate["proposed_hard_budget_cny"] = recommended_budget
    estimate["proposed_budget_sufficient"] = estimate["total_cost_upper_bound_cny"] <= recommended_budget
    _write_hashes()
    return {"selection": selection["batches"][str(batch)], "dry_run": estimate}


def _selected_records(through_batch: int) -> list[dict[str, Any]]:
    selection = json.loads(SELECTION_PATH.read_text(encoding="utf-8"))
    records = []
    for batch in range(1, through_batch + 1):
        batch_record = selection["batches"].get(str(batch))
        if batch_record is None:
            raise RuntimeError(f"pilot Batch {batch} is not prepared")
        path = ROOT / batch_record["snapshot_path"]
        if _sha256_file(path) != batch_record["snapshot_sha256"]:
            raise RuntimeError(f"pilot Batch {batch} snapshot drifted")
        records.extend(_read_jsonl(path))
    return records


def _pool_record(record: dict[str, Any], responses: dict[str, dict[str, dict[str, Any]]]) -> dict[str, Any]:
    query_id = record["query_id"]
    rankings = {"none": [item["document_id"] for item in record["candidates"][:TOP_K]]}
    for mode in MODEL_MODES:
        model_id = MODEL_IDS[mode]
        assert model_id is not None
        rankings[model_id] = [item["document_id"] for item in responses[model_id][query_id]["outcome"]["items"][:TOP_K]]
    candidate_by_id = {item["document_id"]: item for item in record["candidates"]}
    union_ids = list(dict.fromkeys(document_id for ranking in rankings.values() for document_id in ranking))
    if any(document_id not in candidate_by_id for document_id in union_ids):
        raise RuntimeError(f"pilot query {query_id} response contains an unknown document index")
    return {
        "query_id": query_id,
        "query": record["query"],
        "split": record["split"],
        "query_metadata": record["query_metadata"],
        "candidates": [candidate_by_id[document_id] for document_id in union_ids],
        "rankings": rankings,
        "ranking_sha256": {name: _hash_value(ranking) for name, ranking in rankings.items()},
    }


def build_pool(through_batch: int = 1) -> dict[str, Any]:
    records = _selected_records(through_batch)
    responses = _responses_for_snapshot(records, CACHE_DIR)
    missing = {
        model_id: [record["query_id"] for record in records if record["query_id"] not in responses.get(model_id, {})]
        for model_id in (MODEL_IDS["bge"], MODEL_IDS["qwen3"])
    }
    missing = {model_id: query_ids for model_id, query_ids in missing.items() if query_ids}
    if missing:
        raise RuntimeError(f"pilot model responses are incomplete: {json.dumps(missing, sort_keys=True)}")
    pool = [_pool_record(record, responses) for record in records]
    _write_jsonl(POOL_PATH, pool)

    annotation_rows = []
    for record in pool:
        for candidate in record["candidates"]:
            metadata = candidate["source_metadata"]
            annotation_rows.append(
                {
                    "query_id": record["query_id"],
                    "query": record["query"],
                    "split": record["split"],
                    "blind_document_id": candidate["blind_document_id"],
                    "platform": metadata.get("platform", ""),
                    "title": metadata.get("title", ""),
                    "text_excerpt": candidate["text"][:800].replace("\n", " "),
                    "relevance_grade": "",
                    "notes": "",
                }
            )
    source_hash = json.loads(SELECTION_PATH.read_text(encoding="utf-8"))["candidate_snapshot_sha256"]
    annotation_rows.sort(
        key=lambda row: _hash_value([source_hash, "pilot-row", row["query_id"], row["blind_document_id"]])
    )
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=REVIEW_COLUMNS)
    writer.writeheader()
    writer.writerows(annotation_rows)
    ANNOTATION_PATH.write_text(buffer.getvalue(), encoding="utf-8")

    overlaps = []
    for record in pool:
        rankings = record["rankings"]
        bge = set(rankings[MODEL_IDS["bge"]])
        qwen = set(rankings[MODEL_IDS["qwen3"]])
        baseline = set(rankings["none"])
        overlaps.append(
            {
                "query_id": record["query_id"],
                "pool_size": len(record["candidates"]),
                "baseline_bge": len(baseline & bge),
                "baseline_qwen3": len(baseline & qwen),
                "bge_qwen3": len(bge & qwen),
            }
        )
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest["pool"] = {
        "through_batch": through_batch,
        "query_count": len(pool),
        "candidate_count": len(annotation_rows),
        "candidate_count_per_query": {
            "minimum": min(item["pool_size"] for item in overlaps),
            "maximum": max(item["pool_size"] for item in overlaps),
            "mean": statistics.fmean(item["pool_size"] for item in overlaps),
        },
        "pool_path": str(POOL_PATH.relative_to(ROOT)),
        "pool_sha256": _sha256_file(POOL_PATH),
        "annotation_path": str(ANNOTATION_PATH.relative_to(ROOT)),
        "annotation_sha256": _sha256_file(ANNOTATION_PATH),
        "overlap": overlaps,
    }
    manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_hashes()
    return manifest["pool"]


def _write_hashes() -> dict[str, str]:
    artifacts = [SELECTION_PATH, MANIFEST_PATH]
    if SELECTION_PATH.exists():
        selection = json.loads(SELECTION_PATH.read_text(encoding="utf-8"))
        artifacts.extend(ROOT / batch["snapshot_path"] for batch in selection.get("batches", {}).values())
    if POOL_PATH.exists():
        artifacts.extend([POOL_PATH, ANNOTATION_PATH])
    if REPORT_JSON_PATH.exists():
        artifacts.extend([REPORT_JSON_PATH, REPORT_MD_PATH])
    if LABELS_PATH.exists() and LABELS_MANIFEST_PATH.exists():
        artifacts.extend([LABELS_PATH, LABELS_MANIFEST_PATH])
        provenance = json.loads(LABELS_MANIFEST_PATH.read_text(encoding="utf-8"))
        for key in ("first_pass_path", "retest_path"):
            filename = provenance.get(key)
            if isinstance(filename, str) and Path(filename).name == filename:
                review_path = PILOT_DIR / filename
                if review_path.exists():
                    artifacts.append(review_path)
    return write_hash_manifest(artifacts, HASHES_PATH, root=ROOT)


def query_metrics(record: dict[str, Any], ranking: list[str], labels: dict[str, int]) -> dict[str, float]:
    grades_by_id = {
        candidate["document_id"]: labels[candidate["blind_document_id"]] for candidate in record["candidates"]
    }
    grades = [grades_by_id[document_id] for document_id in ranking[:TOP_K]]
    first_relevant = next((rank for rank, grade in enumerate(grades, start=1) if grade > 0), None)
    dcg = sum((2**grade - 1) / math.log2(rank + 1) for rank, grade in enumerate(grades, start=1))
    ideal = sorted(grades_by_id.values(), reverse=True)[:TOP_K]
    idcg = sum((2**grade - 1) / math.log2(rank + 1) for rank, grade in enumerate(ideal, start=1))
    relevant_total = sum(grade > 0 for grade in grades_by_id.values())
    relevant_top3 = sum(grade > 0 for grade in grades)
    return {
        "mrr_at_3": 0.0 if first_relevant is None else 1 / first_relevant,
        "ndcg_at_3": dcg / idcg if idcg else 0.0,
        "pooled_recall_at_3": relevant_top3 / relevant_total if relevant_total else 0.0,
        "precision_at_3": relevant_top3 / len(grades) if grades else 0.0,
        "irrelevant_top3_rate": sum(grade == 0 for grade in grades) / len(grades) if grades else 0.0,
    }


def summarize_metrics(per_query: dict[str, dict[str, float]]) -> dict[str, float | int]:
    keys = next(iter(per_query.values())).keys() if per_query else ()
    return {
        "valid_queries": len(per_query),
        **{key: statistics.fmean(item[key] for item in per_query.values()) for key in keys},
    }


def bootstrap_interval(
    values: list[float],
    *,
    samples: int = BOOTSTRAP_SAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, float | int | list[float]]:
    if not values:
        raise ValueError("bootstrap requires at least one paired query delta")
    rng = random.Random(seed)
    means = sorted(statistics.fmean(rng.choices(values, k=len(values))) for _ in range(samples))
    return {
        "mean": statistics.fmean(values),
        "confidence_level": 0.95,
        "interval": [_percentile(means, 0.025), _percentile(means, 0.975)],
        "samples": samples,
        "seed": seed,
    }


def paired_comparison(
    left: dict[str, dict[str, float]],
    right: dict[str, dict[str, float]],
    metric: str = "ndcg_at_3",
) -> dict[str, Any]:
    query_ids = sorted(set(left) & set(right))
    deltas = [left[query_id][metric] - right[query_id][metric] for query_id in query_ids]
    tolerance = 1e-12
    return {
        "metric": metric,
        "query_count": len(query_ids),
        "wins": sum(delta > tolerance for delta in deltas),
        "ties": sum(abs(delta) <= tolerance for delta in deltas),
        "losses": sum(delta < -tolerance for delta in deltas),
        "bootstrap": bootstrap_interval(deltas),
    }


def _system_metrics(
    selected: list[dict[str, Any]], responses: dict[str, dict[str, dict[str, Any]]]
) -> dict[str, dict[str, Any]]:
    systems = {}
    for mode in MODEL_MODES:
        model_id = MODEL_IDS[mode]
        assert model_id is not None
        model_records = responses.get(model_id, {})
        latencies = [item["outcome"]["latency_ms"] for item in model_records.values()]
        usages = [item["outcome"]["usage"] for item in model_records.values()]
        systems[model_id] = {
            "successful_queries": len(model_records),
            "failed_queries": len(selected) - len(model_records),
            "success_rate": len(model_records) / len(selected) if selected else None,
            "latency_p50_ms": _percentile(latencies, 0.5),
            "latency_p95_ms": _percentile(latencies, 0.95),
            "input_tokens": sum(usage.get("input_tokens", 0) for usage in usages),
            "output_tokens": sum(usage.get("output_tokens", 0) for usage in usages),
            "total_tokens": sum(usage.get("total_tokens", 0) for usage in usages),
            **_cached_cost_metrics(model_records),
            "retry_count": sum(item["outcome"].get("retry_count", 0) for item in model_records.values()),
        }
    return systems


def _system_dominates(left: dict[str, Any], right: dict[str, Any]) -> bool:
    keys = ("failed_queries", "latency_p95_ms", "actual_cost_cny")
    left_values = [float("inf") if left[key] is None else left[key] for key in keys]
    right_values = [float("inf") if right[key] is None else right[key] for key in keys]
    return all(a <= b for a, b in zip(left_values, right_values)) and any(
        a < b for a, b in zip(left_values, right_values)
    )


def decide(
    comparisons: dict[str, dict[str, Any]],
    systems: dict[str, dict[str, Any]],
    slice_regressions: dict[str, list[str]],
    *,
    through_batch: int,
) -> dict[str, Any]:
    bge = MODEL_IDS["bge"]
    qwen = MODEL_IDS["qwen3"]
    assert bge is not None and qwen is not None
    versus_baseline = {model: comparisons[f"{model}_vs_none"]["bootstrap"] for model in (bge, qwen)}
    if all(result["mean"] <= 0 for result in versus_baseline.values()):
        return {
            "status": "no_rerank",
            "selected_model_id": None,
            "reason": "Both rerankers have non-positive mean nDCG@3 deltas versus baseline.",
        }
    clear = [model for model, result in versus_baseline.items() if result["interval"][0] > 0]
    clear = [model for model in clear if not slice_regressions.get(model)]
    if len(clear) == 1:
        return {
            "status": "selected",
            "selected_model_id": clear[0],
            "evidence_level": "pilot_single_expert",
            "reason": "One model has a positive paired nDCG@3 interval versus baseline without a supported slice regression.",
        }
    if len(clear) == 2:
        pair = comparisons[f"{bge}_vs_{qwen}"]["bootstrap"]
        if pair["interval"][0] > 0:
            selected = bge
        elif pair["interval"][1] < 0:
            selected = qwen
        elif _system_dominates(systems[bge], systems[qwen]):
            selected = bge
        elif _system_dominates(systems[qwen], systems[bge]):
            selected = qwen
        else:
            selected = None
        if selected is not None:
            return {
                "status": "selected",
                "selected_model_id": selected,
                "evidence_level": "pilot_single_expert",
                "reason": "Both models improve quality; the selected model wins the paired comparison or system tie-break.",
            }
    if through_batch == 1:
        return {
            "status": "inconclusive_add_batch",
            "selected_model_id": None,
            "reason": "Pilot uncertainty or a quality/system tradeoff remains; Batch 2 may be proposed but not executed automatically.",
        }
    return {
        "status": "inconclusive",
        "selected_model_id": None,
        "reason": "Uncertainty remains after the final pre-registered pilot batch.",
    }


def _slice_quality(
    pool: list[dict[str, Any]],
    per_system: dict[str, dict[str, dict[str, float]]],
) -> tuple[dict[str, Any], dict[str, list[str]]]:
    dimensions: dict[str, dict[str, set[str]]] = {"platform": {}, "query_language": {}}
    for record in pool:
        values = {
            "platform": record["query_metadata"].get("platform", "unknown") or "unknown",
            "query_language": query_language(record["query"]),
        }
        for dimension, value in values.items():
            dimensions[dimension].setdefault(value, set()).add(record["query_id"])
    slices: dict[str, Any] = {}
    regressions: dict[str, list[str]] = defaultdict(list)
    for dimension, groups in dimensions.items():
        slices[dimension] = {}
        for value, query_ids in groups.items():
            slices[dimension][value] = {
                name: summarize_metrics({query_id: metrics[query_id] for query_id in query_ids})
                for name, metrics in per_system.items()
            }
            if len(query_ids) < 5:
                continue
            baseline = slices[dimension][value]["none"]["ndcg_at_3"]
            for model_id in (MODEL_IDS["bge"], MODEL_IDS["qwen3"]):
                assert model_id is not None
                if slices[dimension][value][model_id]["ndcg_at_3"] < baseline:
                    regressions[model_id].append(f"{dimension}:{value}")
    return slices, dict(regressions)


def coverage_summary(pool: list[dict[str, Any]], labels: dict[str, int]) -> dict[str, Any]:
    grade_counts = {grade: sum(value == grade for value in labels.values()) for grade in (0, 1, 2)}
    all_zero_query_ids = []
    platforms: dict[str, dict[str, int]] = defaultdict(lambda: {"queries": 0, "answerable_queries": 0})
    for record in pool:
        platform = record["query_metadata"].get("platform", "unknown") or "unknown"
        answerable = any(labels[candidate["blind_document_id"]] > 0 for candidate in record["candidates"])
        platforms[platform]["queries"] += 1
        platforms[platform]["answerable_queries"] += int(answerable)
        if not answerable:
            all_zero_query_ids.append(record["query_id"])
    answerable_count = len(pool) - len(all_zero_query_ids)
    return {
        "grade_counts": grade_counts,
        "answerable_queries": answerable_count,
        "all_zero_queries": len(all_zero_query_ids),
        "answerable_query_rate": answerable_count / len(pool) if pool else None,
        "all_zero_query_ids": all_zero_query_ids,
        "platforms": dict(sorted(platforms.items())),
    }


def rebuild_report(through_batch: int = 1) -> dict[str, Any]:
    if HASHES_PATH.exists():
        validate_hash_manifest(HASHES_PATH, root=ROOT)
    pool = _read_jsonl(POOL_PATH)
    if not pool:
        raise RuntimeError("build the pilot Top-3 pool before rebuilding its report")
    label_snapshot = [{**record, "candidates": record["candidates"]} for record in pool]
    loaded = _load_completed_labels(LABELS_PATH, label_snapshot, LABELS_MANIFEST_PATH, ANNOTATION_PATH)
    labels, provenance = loaded if loaded is not None else (None, None)
    responses = _responses_for_snapshot(_selected_records(through_batch), CACHE_DIR)
    systems = _system_metrics(pool, responses)
    limitations = [
        "This pilot evaluates only the frozen three-system Top-3 union.",
        "Pooled Recall@3 is not recall against all Recall Top-20 candidates.",
        "MRR@10, nDCG@10, and relevance-gate calibration are not supported by this pilot.",
        "Single-expert test-retest labels are not multi-reviewer consensus.",
    ]
    if provenance is not None and provenance.get("retest_delay_hours", 0) < 48:
        limitations.append(
            f"Retest began after {provenance['retest_delay_hours']:.6f} hours, so agreement measures immediate "
            "self-consistency rather than delayed temporal stability."
        )
    report: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pilot_scope": {
            "through_batch": through_batch,
            "query_count": len(pool),
            "judged_pool_candidate_count": sum(len(record["candidates"]) for record in pool),
            "top_k": TOP_K,
            "recall_definition": "pooled relevant documents in the judged three-system Top-3 union",
        },
        "label_status": "single_expert_test_retest_validated" if labels is not None else "missing_human_labels",
        "label_provenance": provenance,
        "system": systems,
        "quality": None,
        "comparisons": None,
        "slices": None,
        "coverage": None,
        "post_hoc_answerable_sensitivity": None,
        "selection": {"status": "blocked", "reason": "Pilot human relevance labels are incomplete."},
        "limitations": limitations,
    }
    if labels is not None:
        per_system: dict[str, dict[str, dict[str, float]]] = {"none": {}}
        for model_id in (MODEL_IDS["bge"], MODEL_IDS["qwen3"]):
            assert model_id is not None
            per_system[model_id] = {}
        for record in pool:
            for name, ranking in record["rankings"].items():
                per_system[name][record["query_id"]] = query_metrics(record, ranking, labels)
        quality = {name: summarize_metrics(metrics) for name, metrics in per_system.items()}
        bge = MODEL_IDS["bge"]
        qwen = MODEL_IDS["qwen3"]
        assert bge is not None and qwen is not None
        comparisons = {
            f"{bge}_vs_none": paired_comparison(per_system[bge], per_system["none"]),
            f"{qwen}_vs_none": paired_comparison(per_system[qwen], per_system["none"]),
            f"{bge}_vs_{qwen}": paired_comparison(per_system[bge], per_system[qwen]),
        }
        slices, regressions = _slice_quality(pool, per_system)
        coverage = coverage_summary(pool, labels)
        answerable_ids = set(record["query_id"] for record in pool) - set(coverage["all_zero_query_ids"])
        answerable = {
            name: {query_id: metrics[query_id] for query_id in answerable_ids} for name, metrics in per_system.items()
        }
        answerable_sensitivity = {
            "status": "post_hoc_sensitivity_not_primary_decision_evidence",
            "query_count": len(answerable_ids),
            "quality": {name: summarize_metrics(metrics) for name, metrics in answerable.items()},
            "comparisons": {
                f"{bge}_vs_none": paired_comparison(answerable[bge], answerable["none"]),
                f"{qwen}_vs_none": paired_comparison(answerable[qwen], answerable["none"]),
                f"{bge}_vs_{qwen}": paired_comparison(answerable[bge], answerable[qwen]),
            },
        }
        report.update(
            {
                "quality": quality,
                "comparisons": comparisons,
                "slices": slices,
                "slice_regressions": regressions,
                "coverage": coverage,
                "post_hoc_answerable_sensitivity": answerable_sensitivity,
                "selection": decide(comparisons, systems, regressions, through_batch=through_batch),
            }
        )
    REPORT_JSON_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Rerank Top-3 pilot report",
        "",
        f"- Queries: {len(pool)}",
        f"- Judged Top-3 union candidates: {report['pilot_scope']['judged_pool_candidate_count']}",
        f"- Labels: {report['label_status']}",
        f"- Selection: **{report['selection']['status']}** - {report['selection']['reason']}",
        "",
        "## System metrics",
        "",
        "| Model | Success | API P95 ms | Tokens | Cost CNY | Failures |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for model_id, metrics in systems.items():
        lines.append(
            f"| `{model_id}` | {metrics['successful_queries']}/{len(pool)} | "
            f"{metrics['latency_p95_ms'] if metrics['latency_p95_ms'] is not None else 'n/a'} | "
            f"{metrics['total_tokens']} | {metrics['actual_cost_cny']:.6f} | {metrics['failed_queries']} |"
        )
    lines.extend(["", "## Quality", ""])
    if report["quality"] is None:
        lines.append("Unavailable until the reduced single-expert evidence package is complete.")
    else:
        lines.extend(
            [
                "| System | MRR@3 | nDCG@3 | Pooled Recall@3 | Precision@3 | Irrelevant Top-3 |",
                "| --- | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for name, metrics in report["quality"].items():
            lines.append(
                f"| `{name}` | {metrics['mrr_at_3']:.4f} | {metrics['ndcg_at_3']:.4f} | "
                f"{metrics['pooled_recall_at_3']:.4f} | {metrics['precision_at_3']:.4f} | "
                f"{metrics['irrelevant_top3_rate']:.4f} |"
            )
        lines.extend(
            [
                "",
                "## Pool coverage",
                "",
                f"- Queries with at least one relevant pooled candidate: {report['coverage']['answerable_queries']}/{len(pool)}",
                f"- All-zero pooled queries: {report['coverage']['all_zero_queries']}/{len(pool)}",
                "- Answerable-only metrics are post-hoc sensitivity analysis, not primary decision evidence.",
            ]
        )
    lines.extend(["", "## Limitations", "", *[f"- {item}" for item in report["limitations"]]])
    REPORT_MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _write_hashes()
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--prepare", action="store_true")
    actions.add_argument("--execute", action="store_true")
    actions.add_argument("--build-pool", action="store_true")
    actions.add_argument("--rebuild-report", action="store_true")
    parser.add_argument("--batch", type=int, choices=sorted(BATCH_SIZES), default=1)
    parser.add_argument("--max-cost-cny", type=float)
    args = parser.parse_args()

    if args.execute:
        if args.max_cost_cny is None or args.max_cost_cny <= 0:
            raise SystemExit("--execute requires a positive --max-cost-cny")
        _selected_records(args.batch)
        try:
            result = asyncio.run(
                execute_experiment(
                    _batch_snapshot_path(args.batch),
                    modes=MODEL_MODES,
                    max_cost_cny=args.max_cost_cny,
                    manifest_path=MANIFEST_PATH,
                    failures_path=FAILURES_PATH,
                )
            )
        finally:
            _write_hashes()
    elif args.build_pool:
        result = build_pool(args.batch)
    elif args.rebuild_report:
        result = rebuild_report(args.batch)
    else:
        result = prepare_batch(args.batch)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
