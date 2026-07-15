"""Freeze, dry-run, execute, resume, and report the SiliconFlow rerank experiment."""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import io
import json
import math
import os
import statistics
import subprocess
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from needradar.services.reranker import MODEL_IDS, RerankCandidate, RerankerError, SiliconFlowReranker

ROOT = Path(__file__).resolve().parents[1]
EVALUATION_DIR = ROOT / "evaluation" / "rerank"
SNAPSHOT_PATH = EVALUATION_DIR / "candidates.jsonl"
MANIFEST_PATH = EVALUATION_DIR / "manifest.json"
ANNOTATION_PATH = EVALUATION_DIR / "annotation-template.csv"
RECALL_LATENCY_PATH = EVALUATION_DIR / "recall-latency.jsonl"
LABELS_PATH = EVALUATION_DIR / "labels-adjudicated.csv"
LABELS_MANIFEST_TEMPLATE_PATH = EVALUATION_DIR / "labels-manifest-template.json"
LABELS_MANIFEST_PATH = EVALUATION_DIR / "labels-adjudicated.manifest.json"
REPORT_JSON_PATH = EVALUATION_DIR / "report.json"
REPORT_MD_PATH = EVALUATION_DIR / "report.md"
HASHES_PATH = EVALUATION_DIR / "artifact-hashes.json"
CACHE_DIR = ROOT / "data" / "rerank-cache"
FAILURES_PATH = EVALUATION_DIR / "failures.jsonl"

RECALL_K = 20
PRODUCTION_TOP_K = 3
MAX_DOCUMENT_CHARS = 2_000
DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_MAX_ATTEMPTS = 3
PROPOSED_BUDGET_CNY = 0.23
MODEL_MODES = ("bge", "qwen3")
PRICING_CNY_PER_MILLION_INPUT = {
    "BAAI/bge-reranker-v2-m3": 0.0,
    "Qwen/Qwen3-Reranker-0.6B": 0.07,
}
PRICING_EVIDENCE_URL = "https://www.siliconflow.cn/pricing"
API_DOC_URL = "https://docs.siliconflow.cn/cn/api-reference/rerank/create-rerank"
REQUEST_OPTIONS = {
    "top_k": RECALL_K,
    "return_documents": False,
    "timeout_seconds": DEFAULT_TIMEOUT_SECONDS,
    "max_attempts": DEFAULT_MAX_ATTEMPTS,
    "max_document_chars": MAX_DOCUMENT_CHARS,
}
SINGLE_EXPERT_PROTOCOL = "single-expert-blind-test-retest-v1"
SINGLE_EXPERT_REVIEW_METHOD = "single_expert_blind_test_retest"
SINGLE_EXPERT_RETEST_FRACTION = 0.1
SINGLE_EXPERT_EXACT_AGREEMENT_MINIMUM = 0.85
SINGLE_EXPERT_WEIGHTED_KAPPA_MINIMUM = 0.8


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    data = path.read_bytes()
    # CSV artifacts are text-normalized by Git; hash a canonical CRLF form so
    # manifests remain valid after checkout on platforms with different EOLs.
    if path.suffix.lower() == ".csv":
        data = data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    return _sha256_bytes(data)


def _hash_value(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return _sha256_bytes(payload)


def _git_state(root: Path) -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--short"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.splitlines()
    return {"commit": commit, "dirty": bool(status), "diff_status": status}


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def write_hash_manifest(paths: list[Path], output_path: Path, *, root: Path = ROOT) -> dict[str, str]:
    hashes = {}
    for path in paths:
        if not path.exists():
            continue
        try:
            display_path = str(path.relative_to(root))
        except ValueError:
            display_path = str(path)
        hashes[display_path] = _sha256_file(path)
    output_path.write_text(json.dumps(hashes, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return hashes


def validate_hash_manifest(path: Path = HASHES_PATH, *, root: Path = ROOT) -> dict[str, str]:
    hashes = json.loads(path.read_text(encoding="utf-8"))
    for display_path, expected in hashes.items():
        artifact_path = Path(display_path)
        if not artifact_path.is_absolute():
            artifact_path = root / artifact_path
        if _sha256_file(artifact_path) != expected:
            raise ValueError(f"artifact hash mismatch: {artifact_path}")
    return hashes


def _split(query_id: str) -> str:
    return "dev" if int(hashlib.sha256(query_id.encode()).hexdigest()[:8], 16) % 10 < 3 else "test"


def _blind_id(query_id: str, document_id: str) -> str:
    return hashlib.sha256(f"{query_id}:{document_id}".encode()).hexdigest()[:16]


async def freeze_candidates(
    query_path: Path,
    corpus_path: Path,
    snapshot_path: Path = SNAPSHOT_PATH,
    manifest_path: Path = MANIFEST_PATH,
    annotation_path: Path = ANNOTATION_PATH,
    *,
    retriever: Any | None = None,
) -> dict[str, Any]:
    queries = _read_jsonl(query_path)
    if retriever is None:
        from needradar.services.phase3_corpus import Phase3CorpusRetriever

        selected_retriever = Phase3CorpusRetriever(corpus_path)
    else:
        selected_retriever = retriever
    records = []
    annotation_rows = []
    recall_timings = []
    for query_record in queries:
        query = query_record["title"].strip()
        recall_started = time.monotonic()
        results = await selected_retriever.retrieve_hybrid(query, n_results=RECALL_K)
        recall_timings.append(
            {
                "query_id": query_record["id"],
                "latency_ms": round((time.monotonic() - recall_started) * 1000, 3),
            }
        )
        candidates = []
        for rank, result in enumerate(results, start=1):
            metadata = dict(result.metadata or {})
            if metadata.get("recall", {}).get("mode") != "hybrid_rrf":
                raise RuntimeError(f"query {query_record['id']} did not complete genuine hybrid recall")
            document = (result.document or "")[:MAX_DOCUMENT_CHARS]
            blind_id = _blind_id(query_record["id"], result.id)
            candidate = {
                "document_id": result.id,
                "blind_document_id": blind_id,
                "text": document,
                "original_rank": rank,
                "original_score": float(result.score),
                "source_metadata": metadata,
            }
            candidates.append(candidate)
            annotation_rows.append(
                {
                    "query_id": query_record["id"],
                    "query": query,
                    "split": _split(query_record["id"]),
                    "blind_document_id": blind_id,
                    "platform": metadata.get("platform", ""),
                    "title": metadata.get("title", ""),
                    "text_excerpt": document[:800].replace("\n", " "),
                    "relevance_grade": "",
                    "notes": "",
                }
            )
        if len(candidates) != RECALL_K:
            raise RuntimeError(f"query {query_record['id']} returned {len(candidates)} candidates; expected {RECALL_K}")
        records.append(
            {
                "query_id": query_record["id"],
                "query": query,
                "split": _split(query_record["id"]),
                "query_metadata": {
                    "platform": query_record.get("platform", ""),
                    "source_url": query_record.get("source_url", ""),
                },
                "candidates": candidates,
            }
        )

    _write_jsonl(snapshot_path, records)
    recall_latency_path = snapshot_path.with_name(RECALL_LATENCY_PATH.name)
    _write_jsonl(recall_latency_path, recall_timings)
    annotation_rows.sort(key=lambda row: _hash_value([row["query_id"], row["blind_document_id"]]))
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(annotation_rows[0]))
    writer.writeheader()
    writer.writerows(annotation_rows)
    annotation_path.parent.mkdir(parents=True, exist_ok=True)
    annotation_path.write_text(buffer.getvalue(), encoding="utf-8")
    labels_path = annotation_path.with_name(LABELS_PATH.name)
    labels_manifest_template_path = annotation_path.with_name(LABELS_MANIFEST_TEMPLATE_PATH.name)
    labels_manifest_path = annotation_path.with_name(LABELS_MANIFEST_PATH.name)
    labels_manifest_template = {
        "schema_version": 2,
        "labels_path": _display_path(labels_path),
        "labels_sha256": None,
        "review_method": None,
        "reviewer_count": None,
        "independent_review": None,
        "system_blinded": True,
        "adjudicated": False,
        "exact_agreement": None,
        "weighted_kappa": None,
        "accepted_review_methods": ["dual_independent_blind", SINGLE_EXPERT_REVIEW_METHOD],
        "completed_at": None,
    }
    labels_manifest_template_path.write_text(
        json.dumps(labels_manifest_template, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    provenance = selected_retriever.get_provenance() if hasattr(selected_retriever, "get_provenance") else {}
    split_counts = {name: sum(record["split"] == name for record in records) for name in ("dev", "test")}
    manifest = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data": {
            "query_path": _display_path(query_path),
            "query_sha256": _sha256_file(query_path),
            "corpus_path": _display_path(corpus_path),
            "corpus_sha256": _sha256_file(corpus_path),
            "candidate_snapshot_path": _display_path(snapshot_path),
            "candidate_snapshot_sha256": _sha256_file(snapshot_path),
            "recall_latency_path": _display_path(recall_latency_path),
            "recall_latency_sha256": _sha256_file(recall_latency_path),
            "annotation_path": _display_path(annotation_path),
            "annotation_sha256": _sha256_file(annotation_path),
            "labels_manifest_template_path": _display_path(labels_manifest_template_path),
            "labels_manifest_template_sha256": _sha256_file(labels_manifest_template_path),
            "query_count": len(records),
            "candidate_count": sum(len(record["candidates"]) for record in records),
            "split_counts": split_counts,
            "relevance_labels": "missing_human_labels",
            "label_provenance": "annotation template only; no agent-generated relevance gold",
            "expected_adjudicated_label_path": _display_path(labels_path),
            "expected_adjudicated_label_manifest_path": _display_path(labels_manifest_path),
        },
        "recall": {
            "method": "hybrid_dense_cosine_lexical_ngram_rrf",
            "claimed_hybrid": True,
            "top_k": RECALL_K,
            "fusion": {"method": "reciprocal_rank_fusion", "rrf_k": 60},
            "latency_ms": {
                "p50": _percentile([item["latency_ms"] for item in recall_timings], 0.5),
                "p95": _percentile([item["latency_ms"] for item in recall_timings], 0.95),
                "measurement": "single local frozen-corpus pass with a warm table",
            },
            "provenance": provenance,
        },
        "api": {
            "base_url": "https://api.siliconflow.cn/v1",
            "documentation": API_DOC_URL,
            "models": [MODEL_IDS[mode] for mode in MODEL_MODES],
            "provider_model_revision": None,
            "model_drift_risk": "Provider does not expose an immutable model revision in the documented response.",
        },
        "request": {
            "production_top_k": PRODUCTION_TOP_K,
            "experiment_top_k": RECALL_K,
            "return_documents": False,
            "timeout_seconds": DEFAULT_TIMEOUT_SECONDS,
            "max_attempts": DEFAULT_MAX_ATTEMPTS,
            "max_document_chars": MAX_DOCUMENT_CHARS,
            "gate_calibration": "per-model on dev split; test split is evaluation-only",
        },
        "pricing": {
            "currency": "CNY",
            "per_million_input_tokens": PRICING_CNY_PER_MILLION_INPUT,
            "evidence_url": PRICING_EVIDENCE_URL,
            "observed_at": "2026-07-15",
            "proposed_hard_budget_cny": PROPOSED_BUDGET_CNY,
            "approved": False,
        },
        "metrics": {
            "quality": [
                "MRR@10",
                "nDCG@10",
                "candidate Recall@3",
                "Precision@3",
                "irrelevant Top-3 rate",
                "platform/query-language/candidate-length slices",
            ],
            "system": [
                "API P50/P95 latency",
                "success rate and failure types",
                "input/output/total tokens",
                "actual and per-query cost",
                "retry count",
                "estimated downstream context token change",
            ],
        },
        "decision_rules": [
            "A reranker must improve test-split ranking quality over the no-rerank baseline.",
            "Material unexplained regression in a supported slice blocks promotion.",
            "When quality is close, prefer lower P95 latency, cost, and failure rate.",
            "Pareto tradeoffs remain explicit; no business SLA is invented.",
            "Insufficient evidence keeps BGE as production candidate, not an optimum claim.",
            "If neither model beats baseline, keep reranking disabled.",
        ],
        "code": _git_state(ROOT),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_hash_manifest(
        [manifest_path, snapshot_path, recall_latency_path, annotation_path, labels_manifest_template_path],
        manifest_path.with_name(HASHES_PATH.name),
        root=ROOT,
    )
    return manifest


def validate_frozen_artifacts(manifest_path: Path = MANIFEST_PATH) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for path_key, hash_key in (
        ("query_path", "query_sha256"),
        ("corpus_path", "corpus_sha256"),
        ("candidate_snapshot_path", "candidate_snapshot_sha256"),
        ("recall_latency_path", "recall_latency_sha256"),
        ("annotation_path", "annotation_sha256"),
        ("labels_manifest_template_path", "labels_manifest_template_sha256"),
    ):
        path = ROOT / manifest["data"][path_key]
        if _sha256_file(path) != manifest["data"][hash_key]:
            raise ValueError(f"artifact hash mismatch: {path}")
    return manifest


def _token_upper_bound(record: dict[str, Any]) -> int:
    return len(record["query"].encode()) + sum(len(item["text"].encode()) for item in record["candidates"]) + 64


def dry_run(
    snapshot_path: Path = SNAPSHOT_PATH,
    modes: tuple[str, ...] = MODEL_MODES,
    limit: int | None = None,
) -> dict[str, Any]:
    records = _read_jsonl(snapshot_path)
    if limit is not None:
        records = records[:limit]
    input_tokens = sum(_token_upper_bound(record) for record in records)
    models = [MODEL_IDS[mode] for mode in modes]
    model_estimates = {}
    for model_id in models:
        assert model_id is not None
        price = PRICING_CNY_PER_MILLION_INPUT[model_id]
        model_estimates[model_id] = {
            "requests": len(records),
            "conservative_input_token_upper_bound": input_tokens,
            "price_cny_per_million_input_tokens": price,
            "cost_upper_bound_cny": input_tokens * price / 1_000_000,
        }
    total_cost_upper_bound = sum(item["cost_upper_bound_cny"] for item in model_estimates.values())
    return {
        "dry_run": True,
        "queries": len(records),
        "candidates_per_query": RECALL_K,
        "provider_requests": len(records) * len(models),
        "models": model_estimates,
        "total_cost_upper_bound_cny": total_cost_upper_bound,
        "proposed_hard_budget_cny": PROPOSED_BUDGET_CNY,
        "proposed_budget_sufficient": total_cost_upper_bound <= PROPOSED_BUDGET_CNY,
        "external_payload": (
            f"Frozen public query titles plus up to {RECALL_K} de-authored public candidates per query, "
            f"each truncated to {MAX_DOCUMENT_CHARS} characters"
        ),
        "gold_sent_externally": False,
        "quality_selection_status": "blocked_missing_human_relevance_labels",
    }


def cache_key(model_id: str, record: dict[str, Any], request_options: dict[str, Any]) -> tuple[str, dict[str, str]]:
    parts = {
        "model_id": model_id,
        "query_hash": _hash_value(record["query"]),
        "candidate_set_hash": _hash_value(record["candidates"]),
        "request_options_hash": _hash_value(request_options),
    }
    return _hash_value(parts), parts


def _upsert_failure(path: Path, failure: dict[str, Any]) -> None:
    records = {(record["model_id"], record["query_id"]): record for record in _read_jsonl(path)}
    records[(failure["model_id"], failure["query_id"])] = failure
    _write_jsonl(path, [records[key] for key in sorted(records)])


def _clear_failure(path: Path, *, model_id: str, query_id: str) -> None:
    if not path.exists():
        return
    records = [
        record
        for record in _read_jsonl(path)
        if (record.get("model_id"), record.get("query_id")) != (model_id, query_id)
    ]
    _write_jsonl(path, records)


def _append_execution(manifest_path: Path, execution: dict[str, Any]) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.setdefault("executions", []).append(execution)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


async def execute_experiment(
    snapshot_path: Path,
    *,
    modes: tuple[str, ...],
    max_cost_cny: float,
    cache_dir: Path = CACHE_DIR,
    limit: int | None = None,
    manifest_path: Path = MANIFEST_PATH,
    failures_path: Path = FAILURES_PATH,
    api_key: str | None = None,
    reranker_factory: Any = SiliconFlowReranker,
) -> dict[str, Any]:
    estimate = dry_run(snapshot_path, modes, limit)
    if estimate["total_cost_upper_bound_cny"] > max_cost_cny:
        raise ValueError(
            f"dry-run ceiling CNY {estimate['total_cost_upper_bound_cny']:.6f} exceeds hard budget CNY {max_cost_cny:.6f}"
        )
    if api_key is None:
        load_dotenv(ROOT / ".env.local", override=False)
        api_key = os.environ.get("SILICONFLOW_API_KEY") or os.environ.get("NR_SILICONFLOW_API_KEY") or ""
    if not api_key:
        raise RuntimeError("SILICONFLOW_API_KEY is not configured")

    records = _read_jsonl(snapshot_path)
    if limit is not None:
        records = records[:limit]
    cache_dir.mkdir(parents=True, exist_ok=True)
    started_at = datetime.now(timezone.utc).isoformat()
    completed = 0
    resumed = 0
    failures = []
    total_cost = 0.0
    provider_attempts = 0
    status = "completed"
    stop_reason = None
    try:
        for mode in modes:
            model_id = MODEL_IDS[mode]
            assert model_id is not None
            reranker = reranker_factory(
                mode=mode,
                api_key=api_key,
                timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
                max_attempts=DEFAULT_MAX_ATTEMPTS,
            )
            consecutive_failures = 0
            try:
                for record in records:
                    key, parts = cache_key(model_id, record, REQUEST_OPTIONS)
                    cache_path = cache_dir / f"{key}.json"
                    if cache_path.exists():
                        cached = json.loads(cache_path.read_text(encoding="utf-8"))
                        if cached.get("status") == "success" and all(
                            cached.get(name) == value for name, value in parts.items()
                        ):
                            resumed += 1
                            _clear_failure(failures_path, model_id=model_id, query_id=record["query_id"])
                            continue
                    candidates = [
                        RerankCandidate(
                            document_id=item["document_id"],
                            text=item["text"],
                            original_rank=item["original_rank"],
                            original_score=item["original_score"],
                            metadata=item["source_metadata"],
                        )
                        for item in record["candidates"]
                    ]
                    try:
                        outcome = await reranker.rerank(record["query"], candidates, top_k=RECALL_K, fail_open=False)
                    except RerankerError as error:
                        provider_attempts += 1 + error.retry_count
                        failure = {
                            "query_id": record["query_id"],
                            "model_id": model_id,
                            **parts,
                            "occurred_at": datetime.now(timezone.utc).isoformat(),
                            "error_type": error.error_type,
                            "error_reason": str(error)[:500],
                            "retry_count": error.retry_count,
                        }
                        failures.append(failure)
                        _upsert_failure(failures_path, failure)
                        consecutive_failures += 1
                        if error.error_type in {"model_mismatch", "invalid_response"} or consecutive_failures >= 3:
                            raise RuntimeError("experiment stop condition reached after provider failure") from error
                        continue
                    consecutive_failures = 0
                    provider_attempts += 1 + outcome.retry_count
                    cost = outcome.usage.input_tokens * PRICING_CNY_PER_MILLION_INPUT[model_id] / 1_000_000
                    total_cost += cost
                    cache_record = {
                        "status": "success",
                        **parts,
                        "query_id": record["query_id"],
                        "split": record["split"],
                        "executed_at": datetime.now(timezone.utc).isoformat(),
                        "cost_cny": cost,
                        "outcome": asdict(outcome),
                    }
                    cache_path.write_text(
                        json.dumps(cache_record, ensure_ascii=False, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
                    _clear_failure(failures_path, model_id=model_id, query_id=record["query_id"])
                    completed += 1
                    if total_cost >= max_cost_cny:
                        raise RuntimeError("hard budget reached; refusing additional provider requests")
            finally:
                await reranker.close()
    except Exception as error:
        status = "stopped"
        stop_reason = f"{type(error).__name__}: {str(error)[:300]}"
        raise
    finally:
        execution = {
            "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "stop_reason": stop_reason,
            "modes": list(modes),
            "query_count": len(records),
            "selection_sha256": _hash_value([record["query_id"] for record in records]),
            "candidate_snapshot_sha256": _sha256_file(snapshot_path),
            "request_options_sha256": _hash_value(REQUEST_OPTIONS),
            "completed": completed,
            "resumed": resumed,
            "failures": len(failures),
            "provider_attempts": provider_attempts,
            "actual_cost_cny": total_cost,
            "hard_budget_cny": max_cost_cny,
        }
        _append_execution(manifest_path, execution)
    return {
        "completed": completed,
        "resumed": resumed,
        "failures": len(failures),
        "failure_types": sorted({failure["error_type"] for failure in failures}),
        "provider_attempts": provider_attempts,
        "actual_cost_cny": total_cost,
        "hard_budget_cny": max_cost_cny,
    }


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * percentile
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - index) + ordered[upper] * (index - lower)


def _read_grade_csv(path: Path) -> tuple[dict[str, int], dict[str, dict[str, str]]] | None:
    if not path.exists():
        return None
    rows = list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8-sig"))))
    if not rows:
        return None
    grades: dict[str, int] = {}
    by_id: dict[str, dict[str, str]] = {}
    for row in rows:
        blind_id = row.get("blind_document_id", "").strip()
        value = row.get("relevance_grade", "").strip()
        if not blind_id or blind_id in grades or value not in {"0", "1", "2"}:
            return None
        grades[blind_id] = int(value)
        by_id[blind_id] = row
    return grades, by_id


def _deterministic_retest_ids(source_hash: str, blind_ids: set[str]) -> list[str]:
    sample_count = math.ceil(len(blind_ids) * SINGLE_EXPERT_RETEST_FRACTION)
    return sorted(
        blind_ids,
        key=lambda blind_id: _sha256_bytes(f"{source_hash}:retest:{blind_id}".encode()),
    )[:sample_count]


def _quadratic_weighted_kappa(first: dict[str, int], second: dict[str, int], ids: list[str]) -> float | None:
    matrix = [[0, 0, 0] for _ in range(3)]
    for blind_id in ids:
        matrix[first[blind_id]][second[blind_id]] += 1
    total = len(ids)
    first_marginal = [sum(row) for row in matrix]
    second_marginal = [sum(matrix[row][column] for row in range(3)) for column in range(3)]
    observed = 0.0
    expected = 0.0
    for first_grade in range(3):
        for second_grade in range(3):
            weight = ((first_grade - second_grade) / 2) ** 2
            observed += weight * matrix[first_grade][second_grade] / total
            expected += weight * first_marginal[first_grade] * second_marginal[second_grade] / total**2
    return None if expected == 0 else 1 - observed / expected


def _manifest_number(manifest: dict[str, Any], name: str) -> float | None:
    value = manifest.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return float(value)


def _single_expert_provenance_valid(
    manifest: dict[str, Any],
    manifest_path: Path,
    labels: dict[str, int],
    label_rows: dict[str, dict[str, str]],
    source_template_path: Path,
) -> bool:
    expected = set(labels)
    source_hash = manifest.get("source_template_sha256")
    if (
        manifest.get("schema_version") != 2
        or manifest.get("protocol_version") != SINGLE_EXPERT_PROTOCOL
        or manifest.get("review_method") != SINGLE_EXPERT_REVIEW_METHOD
        or manifest.get("reviewer_count") != 1
        or manifest.get("independent_review") is not False
        or manifest.get("system_blinded") is not True
        or manifest.get("adjudicated") is not True
        or manifest.get("all_disagreements_adjudicated") is not True
        or manifest.get("candidate_count") != len(expected)
        or not source_template_path.exists()
        or source_hash != _sha256_file(source_template_path)
        or not manifest.get("first_pass_completed_at")
        or not manifest.get("retest_started_at")
        or not manifest.get("retest_completed_at")
    ):
        return False

    first_name = manifest.get("first_pass_path")
    retest_name = manifest.get("retest_path")
    if (
        not isinstance(first_name, str)
        or not isinstance(retest_name, str)
        or Path(first_name).name != first_name
        or Path(retest_name).name != retest_name
    ):
        return False
    first_path = manifest_path.parent / first_name
    retest_path = manifest_path.parent / retest_name
    if (
        not first_path.exists()
        or not retest_path.exists()
        or manifest.get("first_pass_sha256") != _sha256_file(first_path)
        or manifest.get("retest_sha256") != _sha256_file(retest_path)
    ):
        return False
    first_loaded = _read_grade_csv(first_path)
    retest_loaded = _read_grade_csv(retest_path)
    if first_loaded is None or retest_loaded is None:
        return False
    first, _ = first_loaded
    retest, _ = retest_loaded
    retest_ids = _deterministic_retest_ids(source_hash, expected)
    if set(first) != expected or set(retest) != set(retest_ids):
        return False

    agreement = sum(first[blind_id] == retest[blind_id] for blind_id in retest_ids) / len(retest_ids)
    kappa = _quadratic_weighted_kappa(first, retest, retest_ids)
    disagreements = [blind_id for blind_id in retest_ids if first[blind_id] != retest[blind_id]]
    for blind_id in expected - set(disagreements):
        if labels[blind_id] != first[blind_id]:
            return False
    for blind_id in disagreements:
        if not label_rows[blind_id].get("notes", "").strip().startswith("[self-adjudicated]"):
            return False

    exact_manifest = _manifest_number(manifest, "exact_agreement")
    kappa_manifest = _manifest_number(manifest, "weighted_kappa")
    retest_fraction = _manifest_number(manifest, "retest_fraction")
    retest_delay = _manifest_number(manifest, "retest_delay_hours")
    acceptance = manifest.get("acceptance")
    return bool(
        exact_manifest is not None
        and math.isclose(exact_manifest, agreement, abs_tol=1e-12)
        and kappa is not None
        and kappa_manifest is not None
        and math.isclose(kappa_manifest, kappa, abs_tol=1e-12)
        and agreement >= SINGLE_EXPERT_EXACT_AGREEMENT_MINIMUM
        and kappa >= SINGLE_EXPERT_WEIGHTED_KAPPA_MINIMUM
        and retest_fraction is not None
        and math.isclose(retest_fraction, SINGLE_EXPERT_RETEST_FRACTION, abs_tol=1e-12)
        and manifest.get("retest_sample_count") == len(retest_ids)
        and manifest.get("disagreement_count") == len(disagreements)
        and retest_delay is not None
        and retest_delay >= 0
        and isinstance(acceptance, dict)
        and acceptance.get("exact_agreement_minimum") == SINGLE_EXPERT_EXACT_AGREEMENT_MINIMUM
        and acceptance.get("weighted_kappa_minimum") == SINGLE_EXPERT_WEIGHTED_KAPPA_MINIMUM
        and acceptance.get("passed") is True
    )


def _load_completed_labels(
    path: Path,
    snapshot: list[dict[str, Any]],
    manifest_path: Path = LABELS_MANIFEST_PATH,
    source_template_path: Path = ANNOTATION_PATH,
) -> tuple[dict[str, int], dict[str, Any]] | None:
    if not path.exists() or not manifest_path.exists():
        return None
    label_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    loaded = _read_grade_csv(path)
    if loaded is None:
        return None
    labels, label_rows = loaded
    expected = {item["blind_document_id"] for record in snapshot for item in record["candidates"]}
    if (
        set(labels) != expected
        or label_manifest.get("labels_sha256") != _sha256_file(path)
        or label_manifest.get("adjudicated") is not True
        or not label_manifest.get("completed_at")
    ):
        return None
    if label_manifest.get("review_method") == SINGLE_EXPERT_REVIEW_METHOD:
        if not _single_expert_provenance_valid(
            label_manifest,
            manifest_path,
            labels,
            label_rows,
            source_template_path,
        ):
            return None
    elif (
        label_manifest.get("review_method") not in {None, "dual_independent_blind"}
        or int(label_manifest.get("reviewer_count") or 0) < 2
        or label_manifest.get("independent_review") is not True
    ):
        return None
    return labels, label_manifest


def ranking_metrics(
    rankings: dict[str, list[str]],
    snapshot_by_id: dict[str, dict[str, Any]],
    labels: dict[str, int],
    *,
    split: str = "test",
    query_ids: set[str] | None = None,
) -> dict[str, Any]:
    per_query = []
    for query_id, ranking in rankings.items():
        record = snapshot_by_id[query_id]
        if record["split"] != split or (query_ids is not None and query_id not in query_ids):
            continue
        per_query.append(_query_metrics(record, ranking, labels))
    keys = per_query[0].keys() if per_query else ()
    return {
        "valid_queries": len(per_query),
        **{key: statistics.fmean(item[key] for item in per_query) for key in keys},
    }


def _query_metrics(record: dict[str, Any], ranking: list[str], labels: dict[str, int]) -> dict[str, float]:
    grades_by_id = {item["document_id"]: labels[item["blind_document_id"]] for item in record["candidates"]}
    grades = [grades_by_id.get(document_id, 0) for document_id in ranking]
    first_relevant = next((rank for rank, grade in enumerate(grades[:10], start=1) if grade > 0), None)
    dcg = sum((2**grade - 1) / math.log2(rank + 1) for rank, grade in enumerate(grades[:10], start=1))
    ideal = sorted(grades_by_id.values(), reverse=True)[:10]
    idcg = sum((2**grade - 1) / math.log2(rank + 1) for rank, grade in enumerate(ideal, start=1))
    top3 = grades[:3]
    relevant_total = sum(grade > 0 for grade in grades_by_id.values())
    relevant_top3 = sum(grade > 0 for grade in top3)
    return {
        "mrr_at_10": 0.0 if first_relevant is None else 1 / first_relevant,
        "ndcg_at_10": dcg / idcg if idcg else 0.0,
        "candidate_recall_at_3": relevant_top3 / relevant_total if relevant_total else 0.0,
        "precision_at_3": relevant_top3 / len(top3) if top3 else 0.0,
        "irrelevant_top3_rate": sum(grade == 0 for grade in top3) / len(top3) if top3 else 0.0,
    }


def _slice_groups(snapshot: list[dict[str, Any]]) -> dict[str, dict[str, set[str]]]:
    groups: dict[str, dict[str, set[str]]] = {"platform": {}, "query_language": {}, "candidate_length": {}}
    for record in snapshot:
        query_id = record["query_id"]
        platform = record["query_metadata"].get("platform", "unknown") or "unknown"
        has_cjk = any("\u4e00" <= char <= "\u9fff" for char in record["query"])
        has_latin = any(char.isascii() and char.isalpha() for char in record["query"])
        language = "mixed" if has_cjk and has_latin else "cjk" if has_cjk else "non_cjk"
        average_length = statistics.fmean(len(item["text"]) for item in record["candidates"])
        length_bucket = (
            "short_lt_500" if average_length < 500 else "medium_500_1499" if average_length < 1500 else "long_ge_1500"
        )
        for dimension, value in (
            ("platform", platform),
            ("query_language", language),
            ("candidate_length", length_bucket),
        ):
            groups[dimension].setdefault(value, set()).add(query_id)
    return groups


def _negative_cases(
    rankings: dict[str, dict[str, list[str]]],
    snapshot_by_id: dict[str, dict[str, Any]],
    labels: dict[str, int],
) -> dict[str, list[dict[str, Any]]]:
    baseline_rankings = rankings["none"]
    result = {}
    for name, model_rankings in rankings.items():
        if name == "none" or name.endswith("+gate"):
            continue
        cases = []
        for query_id, model_ranking in model_rankings.items():
            record = snapshot_by_id[query_id]
            if record["split"] != "test":
                continue
            baseline = _query_metrics(record, baseline_rankings[query_id], labels)
            current = _query_metrics(record, model_ranking, labels)
            ndcg_change = current["ndcg_at_10"] - baseline["ndcg_at_10"]
            recall_change = current["candidate_recall_at_3"] - baseline["candidate_recall_at_3"]
            if ndcg_change >= 0 and recall_change >= 0:
                continue
            cases.append(
                {
                    "query_id": query_id,
                    "platform": record["query_metadata"].get("platform", ""),
                    "ndcg_at_10_change": ndcg_change,
                    "candidate_recall_at_3_change": recall_change,
                    "baseline_top3": baseline_rankings[query_id][:3],
                    "model_top3": model_ranking[:3],
                }
            )
        result[name] = sorted(cases, key=lambda case: (case["ndcg_at_10_change"], case["query_id"]))[:20]
    return result


def calibrate_gate_threshold(
    model_records: dict[str, dict[str, Any]],
    snapshot_by_id: dict[str, dict[str, Any]],
    labels: dict[str, int],
) -> dict[str, Any] | None:
    expected_dev_ids = {query_id for query_id, record in snapshot_by_id.items() if record["split"] == "dev"}
    if not expected_dev_ids or not expected_dev_ids.issubset(model_records):
        return None
    dev_records = [item for query_id, item in model_records.items() if snapshot_by_id[query_id]["split"] == "dev"]
    scores = sorted(
        {
            float(result["relevance_score"])
            for item in dev_records
            for result in item["outcome"]["items"][:PRODUCTION_TOP_K]
            if result.get("relevance_score") is not None
        }
    )
    if not scores:
        return None
    candidates = [scores[0] - 1e-12, *scores, scores[-1] + 1e-12]
    best = None
    for threshold in candidates:
        true_positive = false_positive = false_negative = 0
        for item in dev_records:
            record = snapshot_by_id[item["query_id"]]
            labels_by_id = {
                candidate["document_id"]: labels[candidate["blind_document_id"]] for candidate in record["candidates"]
            }
            top3 = item["outcome"]["items"][:PRODUCTION_TOP_K]
            for result in top3:
                relevant = labels_by_id[result["document_id"]] > 0
                included = float(result["relevance_score"]) >= threshold
                true_positive += relevant and included
                false_positive += not relevant and included
                false_negative += relevant and not included
        precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
        recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        candidate = {
            "threshold": threshold,
            "objective": "binary relevance F1 over reranked dev Top 3",
            "dev_true_positive": true_positive,
            "dev_false_positive": false_positive,
            "dev_false_negative": false_negative,
            "dev_precision": precision,
            "dev_recall": recall,
            "dev_f1": f1,
        }
        if best is None or (f1, precision, -threshold) > (best["dev_f1"], best["dev_precision"], -best["threshold"]):
            best = candidate
    return best


def _responses_for_snapshot(
    snapshot: list[dict[str, Any]], cache_dir: Path = CACHE_DIR
) -> dict[str, dict[str, dict[str, Any]]]:
    responses: dict[str, dict[str, dict[str, Any]]] = {}
    if not cache_dir.exists():
        return responses
    for model_id in [MODEL_IDS[mode] for mode in MODEL_MODES]:
        assert model_id is not None
        for record in snapshot:
            key, parts = cache_key(model_id, record, REQUEST_OPTIONS)
            path = cache_dir / f"{key}.json"
            if not path.exists():
                continue
            cached = json.loads(path.read_text(encoding="utf-8"))
            if cached.get("status") != "success" or any(cached.get(name) != value for name, value in parts.items()):
                continue
            responses.setdefault(model_id, {})[record["query_id"]] = cached
    return responses


def _failures_for_snapshot(
    snapshot: list[dict[str, Any]],
    responses: dict[str, dict[str, dict[str, Any]]],
    failures_path: Path = FAILURES_PATH,
) -> list[dict[str, Any]]:
    stored = {(failure.get("model_id"), failure.get("query_id")): failure for failure in _read_jsonl(failures_path)}
    current = []
    for model_id in [MODEL_IDS[mode] for mode in MODEL_MODES]:
        assert model_id is not None
        for record in snapshot:
            query_id = record["query_id"]
            if query_id in responses.get(model_id, {}):
                continue
            _, parts = cache_key(model_id, record, REQUEST_OPTIONS)
            failure = stored.get((model_id, query_id))
            if failure and all(failure.get(name) == value for name, value in parts.items()):
                current.append(failure)
    return current


def _quality_dominates(left: dict[str, Any], right: dict[str, Any]) -> bool:
    higher_is_better = ("mrr_at_10", "ndcg_at_10", "candidate_recall_at_3", "precision_at_3")
    lower_is_better = ("irrelevant_top3_rate",)
    no_worse = all(left[key] >= right[key] for key in higher_is_better) and all(
        left[key] <= right[key] for key in lower_is_better
    )
    strictly_better = any(left[key] > right[key] for key in higher_is_better) or any(
        left[key] < right[key] for key in lower_is_better
    )
    return no_worse and strictly_better


def _system_dominates(left: dict[str, Any], right: dict[str, Any]) -> bool:
    keys = ("failed_queries", "latency_p95_ms", "actual_cost_cny")
    left_values = tuple(float("inf") if left[key] is None else left[key] for key in keys)
    right_values = tuple(float("inf") if right[key] is None else right[key] for key in keys)
    return all(a <= b for a, b in zip(left_values, right_values)) and any(
        a < b for a, b in zip(left_values, right_values)
    )


def _cached_cost_metrics(model_records: dict[str, dict[str, Any]]) -> dict[str, float | None]:
    total = sum(record.get("cost_cny", 0.0) for record in model_records.values())
    return {
        "actual_cost_cny": total,
        "cost_per_successful_query_cny": total / len(model_records) if model_records else None,
    }


def _verification_scope_note(real_api_successes: int) -> str:
    if real_api_successes:
        return (
            f"Real API smoke validated {real_api_successes} successful request/response paths. "
            "It does not establish full frozen-set quality or production reliability."
        )
    return (
        "Fake-provider tests and offline artifacts validate implementation and reproducibility only. "
        "Real API capability remains unverified until the approval-gated smoke tests complete."
    )


def _system_no_worse(left: dict[str, Any], right: dict[str, Any]) -> bool:
    keys = ("failed_queries", "latency_p95_ms", "actual_cost_cny")
    left_values = tuple(float("inf") if left[key] is None else left[key] for key in keys)
    right_values = tuple(float("inf") if right[key] is None else right[key] for key in keys)
    return all(a <= b for a, b in zip(left_values, right_values))


def decide_selection(
    quality: dict[str, Any],
    systems: dict[str, dict[str, Any]],
    model_ids: tuple[str, str],
) -> dict[str, Any]:
    baseline = quality["none"]
    eligible = [model_id for model_id in model_ids if _quality_dominates(quality[model_id], baseline)]
    slice_regressions = {}
    for model_id in eligible:
        regressions = []
        for platform, metrics in quality.get("slices", {}).get("platform", {}).items():
            if model_id not in metrics or "none" not in metrics:
                continue
            model_slice = metrics[model_id]
            baseline_slice = metrics["none"]
            if model_slice.get("valid_queries", 0) and (
                model_slice["ndcg_at_10"] < baseline_slice["ndcg_at_10"]
                or model_slice["candidate_recall_at_3"] < baseline_slice["candidate_recall_at_3"]
            ):
                regressions.append(platform)
        if regressions:
            slice_regressions[model_id] = regressions
    if not eligible:
        return {
            "status": "disabled",
            "selected_model_id": None,
            "reason": "Neither reranker dominates the no-rerank baseline on frozen test quality.",
            "slice_regressions": slice_regressions,
        }
    if len(eligible) == 1:
        selected = eligible[0]
        if selected in slice_regressions:
            return {
                "status": "pareto_tradeoff",
                "selected_model_id": None,
                "reason": "The only baseline-improving model regresses on a platform slice.",
                "slice_regressions": slice_regressions,
            }
        return {
            "status": "selected",
            "selected_model_id": selected,
            "reason": "One model dominates baseline quality without a detected platform-slice regression.",
            "slice_regressions": slice_regressions,
        }

    left, right = eligible
    if (
        left not in slice_regressions
        and _quality_dominates(quality[left], quality[right])
        and _system_no_worse(systems[left], systems[right])
    ):
        selected = left
    elif (
        right not in slice_regressions
        and _quality_dominates(quality[right], quality[left])
        and _system_no_worse(systems[right], systems[left])
    ):
        selected = right
    elif (
        quality[left] == quality[right]
        and left not in slice_regressions
        and _system_dominates(systems[left], systems[right])
    ):
        selected = left
    elif (
        quality[left] == quality[right]
        and right not in slice_regressions
        and _system_dominates(systems[right], systems[left])
    ):
        selected = right
    else:
        return {
            "status": "pareto_tradeoff",
            "selected_model_id": None,
            "reason": "Eligible models form a quality, latency, cost, failure, or slice tradeoff.",
            "slice_regressions": slice_regressions,
        }
    return {
        "status": "selected",
        "selected_model_id": selected,
        "reason": "The selected model dominates the alternative under the frozen decision rules.",
        "slice_regressions": slice_regressions,
    }


def rebuild_report(
    snapshot_path: Path = SNAPSHOT_PATH,
    annotation_path: Path = LABELS_PATH,
    labels_manifest_path: Path = LABELS_MANIFEST_PATH,
    cache_dir: Path = CACHE_DIR,
) -> dict[str, Any]:
    manifest = validate_frozen_artifacts()
    snapshot = _read_jsonl(snapshot_path)
    snapshot_by_id = {record["query_id"]: record for record in snapshot}
    recall_timings = {
        record["query_id"]: record["latency_ms"]
        for record in _read_jsonl(ROOT / manifest["data"]["recall_latency_path"])
    }
    responses = _responses_for_snapshot(snapshot, cache_dir)
    loaded_labels = _load_completed_labels(annotation_path, snapshot, labels_manifest_path)
    labels, label_manifest = loaded_labels if loaded_labels is not None else (None, None)
    label_method = label_manifest.get("review_method", "dual_independent_blind") if label_manifest else None
    label_status = (
        "single_expert_test_retest_validated"
        if label_method == SINGLE_EXPERT_REVIEW_METHOD
        else "dual_independent_human_labels"
        if labels is not None
        else "missing_human_labels"
    )
    failures = _failures_for_snapshot(snapshot, responses)
    failure_counts: dict[str, int] = {}
    for failure in failures:
        key = f"{failure.get('model_id')}:{failure.get('error_type')}"
        failure_counts[key] = failure_counts.get(key, 0) + 1

    systems = {}
    rankings = {
        "none": {record["query_id"]: [item["document_id"] for item in record["candidates"]] for record in snapshot}
    }
    for model_id in [MODEL_IDS[mode] for mode in MODEL_MODES]:
        assert model_id is not None
        model_records = responses.get(model_id, {})
        latencies = [item["outcome"]["latency_ms"] for item in model_records.values()]
        end_to_end_latencies = [
            recall_timings[query_id] + item["outcome"]["latency_ms"] for query_id, item in model_records.items()
        ]
        usages = [item["outcome"]["usage"] for item in model_records.values()]
        context_tokens = sum(
            len(result["text"].encode())
            for item in model_records.values()
            for result in item["outcome"]["items"][:PRODUCTION_TOP_K]
        )
        baseline_context_tokens = sum(
            len(item["text"].encode())
            for record in snapshot
            if record["query_id"] in model_records
            for item in record["candidates"][:PRODUCTION_TOP_K]
        )
        model_failures = sum(failure.get("model_id") == model_id for failure in failures)
        valid_denominator = len(model_records) + model_failures
        systems[model_id] = {
            "successful_queries": len(model_records),
            "failed_queries": model_failures,
            "valid_denominator": valid_denominator,
            "success_rate": len(model_records) / valid_denominator if valid_denominator else None,
            "latency_p50_ms": _percentile(latencies, 0.5),
            "latency_p95_ms": _percentile(latencies, 0.95),
            "end_to_end_latency_p50_ms": _percentile(end_to_end_latencies, 0.5),
            "end_to_end_latency_p95_ms": _percentile(end_to_end_latencies, 0.95),
            "input_tokens": sum(item.get("input_tokens", 0) for item in usages),
            "output_tokens": sum(item.get("output_tokens", 0) for item in usages),
            "total_tokens": sum(item.get("total_tokens", 0) for item in usages),
            **_cached_cost_metrics(model_records),
            "retry_count": sum(item["outcome"].get("retry_count", 0) for item in model_records.values()),
            "estimated_context_token_upper_bound_change": (
                context_tokens - baseline_context_tokens if model_records else None
            ),
        }
        rankings[model_id] = {
            query_id: [result["document_id"] for result in item["outcome"]["items"]]
            for query_id, item in model_records.items()
        }

    quality = None
    gate_calibration = {}
    negative_cases = {}
    if labels is not None:
        quality = {name: ranking_metrics(ranking, snapshot_by_id, labels) for name, ranking in rankings.items()}
        for mode in MODEL_MODES:
            model_id = MODEL_IDS[mode]
            assert model_id is not None
            calibration = calibrate_gate_threshold(responses.get(model_id, {}), snapshot_by_id, labels)
            gate_calibration[model_id] = calibration
            if calibration is None:
                continue
            threshold = calibration["threshold"]
            gated_rankings = {
                query_id: [
                    result["document_id"]
                    for result in item["outcome"]["items"]
                    if float(result["relevance_score"]) >= threshold
                ][:PRODUCTION_TOP_K]
                for query_id, item in responses.get(model_id, {}).items()
            }
            gate_name = f"{model_id}+gate"
            rankings[gate_name] = gated_rankings
            quality[gate_name] = ranking_metrics(gated_rankings, snapshot_by_id, labels)
            gated_context_tokens = sum(
                len(
                    next(
                        candidate["text"]
                        for candidate in snapshot_by_id[query_id]["candidates"]
                        if candidate["document_id"] == document_id
                    ).encode()
                )
                for query_id, document_ids in gated_rankings.items()
                for document_id in document_ids
            )
            ungated_baseline_tokens = sum(
                len(candidate["text"].encode())
                for query_id in gated_rankings
                for candidate in snapshot_by_id[query_id]["candidates"][:PRODUCTION_TOP_K]
            )
            systems[gate_name] = {
                **systems[model_id],
                "api_metrics_reused_from": model_id,
                "additional_provider_requests": 0,
                "estimated_context_token_upper_bound_change": gated_context_tokens - ungated_baseline_tokens,
            }
        quality["slices"] = {
            dimension: {
                value: {
                    name: ranking_metrics(ranking, snapshot_by_id, labels, query_ids=query_ids)
                    for name, ranking in rankings.items()
                }
                for value, query_ids in values.items()
            }
            for dimension, values in _slice_groups(snapshot).items()
        }
        negative_cases = _negative_cases(rankings, snapshot_by_id, labels)
    complete_models = all(len(responses.get(MODEL_IDS[mode] or "", {})) == len(snapshot) for mode in MODEL_MODES)
    if labels is None:
        selection = {"status": "blocked", "reason": "Human relevance labels are incomplete."}
    elif not complete_models:
        selection = {"status": "blocked", "reason": "Both exact models have not completed the frozen experiment."}
    else:
        selection = decide_selection(
            quality,
            systems,
            (MODEL_IDS["bge"], MODEL_IDS["qwen3"]),
        )
    if label_method == SINGLE_EXPERT_REVIEW_METHOD:
        selection = {**selection, "evidence_level": "moderate_evidence_single_expert"}
    limitations = [
        "Hybrid recall uses deterministic dense cosine plus n-gram full-text reciprocal-rank fusion.",
        "No production capability or model advantage is claimed without completed human relevance labels and both model runs.",
        "Provider model revisions are not immutable, so later runs may drift.",
        "Context token change is a conservative UTF-8 byte upper bound, not provider tokenizer output.",
    ]
    if label_method == SINGLE_EXPERT_REVIEW_METHOD:
        limitations.append(
            "Relevance labels come from one system-blinded expert with hidden test-retest validation; they are not "
            "multi-reviewer consensus."
        )
    report = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "artifact_hashes_verified": True,
        "manifest_sha256": _sha256_file(MANIFEST_PATH),
        "candidate_snapshot_sha256": manifest["data"]["candidate_snapshot_sha256"],
        "label_status": label_status,
        "label_provenance": label_manifest,
        "quality": quality,
        "gate_calibration": gate_calibration,
        "negative_cases": negative_cases,
        "system": systems,
        "failure_types": failure_counts,
        "selection": selection,
        "limitations": limitations,
    }
    REPORT_JSON_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def display(value: Any, digits: int = 4) -> str:
        return "n/a" if value is None else f"{value:.{digits}f}" if isinstance(value, float) else str(value)

    lines = [
        "# Rerank experiment report",
        "",
        "- Artifact hashes verified: yes",
        f"- Candidate snapshot: `{manifest['data']['candidate_snapshot_sha256']}`",
        f"- Frozen queries/candidates: {len(snapshot)}/{sum(len(record['candidates']) for record in snapshot)}",
        f"- Recall: {manifest['recall']['method']} Top {manifest['recall']['top_k']}",
        f"- Recall P50/P95: {display(manifest['recall']['latency_ms']['p50'], 3)} / "
        f"{display(manifest['recall']['latency_ms']['p95'], 3)} ms",
        f"- Label status: {label_status.replace('_', ' ')}",
        f"- Selection: **{selection['status']}** - {selection['reason']}",
        "",
        "## System comparison",
        "",
        "| Model | Success | API P50 ms | API P95 ms | E2E P95 ms | Tokens | Cost CNY | Failures |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for model_id in (MODEL_IDS["bge"], MODEL_IDS["qwen3"]):
        system = systems[model_id]
        lines.append(
            f"| `{model_id}` | {system['successful_queries']}/{system['valid_denominator']} | "
            f"{display(system['latency_p50_ms'], 3)} | {display(system['latency_p95_ms'], 3)} | "
            f"{display(system['end_to_end_latency_p95_ms'], 3)} | {system['total_tokens']} | "
            f"{display(system['actual_cost_cny'], 6)} | {system['failed_queries']} |"
        )
    lines.extend(["", "## Quality comparison", ""])
    if quality is None:
        lines.append("Unavailable until `labels-adjudicated.csv` and its human-review manifest are complete.")
    else:
        lines.extend(
            [
                "| Configuration | MRR@10 | nDCG@10 | Recall@3 | Precision@3 | Irrelevant Top-3 |",
                "| --- | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for name, metrics in quality.items():
            if name == "slices":
                continue
            lines.append(
                f"| `{name}` | {display(metrics['mrr_at_10'])} | {display(metrics['ndcg_at_10'])} | "
                f"{display(metrics['candidate_recall_at_3'])} | {display(metrics['precision_at_3'])} | "
                f"{display(metrics['irrelevant_top3_rate'])} |"
            )
    lines.extend(["", "## Failures and negative cases", ""])
    lines.append(f"Failure types: `{json.dumps(failure_counts, ensure_ascii=False, sort_keys=True)}`")
    if negative_cases:
        lines.extend(
            f"- `{model_id}`: {len(cases)} retained worst negative-benefit cases"
            for model_id, cases in negative_cases.items()
        )
    else:
        lines.append("Negative-benefit cases are unavailable without labels and completed model responses.")
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {limitation}" for limitation in report["limitations"])
    real_api_successes = sum(systems[model_id]["successful_queries"] for model_id in MODEL_IDS.values() if model_id)
    lines.extend(["", _verification_scope_note(real_api_successes)])
    REPORT_MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_hash_manifest(
        [
            MANIFEST_PATH,
            snapshot_path,
            ROOT / manifest["data"]["recall_latency_path"],
            ANNOTATION_PATH,
            annotation_path,
            labels_manifest_path,
            LABELS_MANIFEST_TEMPLATE_PATH,
            EVALUATION_DIR / "annotation-protocol.md",
            REPORT_JSON_PATH,
            REPORT_MD_PATH,
        ],
        HASHES_PATH,
    )
    validate_hash_manifest(HASHES_PATH)
    return report


def _modes(values: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", action="store_true", help="Freeze top-20 candidates and annotation package")
    parser.add_argument("--execute", action="store_true", help="Perform real SiliconFlow calls")
    parser.add_argument("--rebuild-report", action="store_true", help="Rebuild reports from cache without API calls")
    parser.add_argument("--models", nargs="+", choices=MODEL_MODES, default=list(MODEL_MODES))
    parser.add_argument("--max-cost-cny", type=float, help="Required hard budget for --execute")
    parser.add_argument("--limit", type=int, help="Limit queries for an approved smoke test")
    parser.add_argument("--labels", type=Path, default=LABELS_PATH, help="Adjudicated human relevance CSV")
    parser.add_argument(
        "--labels-manifest",
        type=Path,
        default=LABELS_MANIFEST_PATH,
        help="Human review and adjudication provenance JSON",
    )
    args = parser.parse_args()
    query_path = ROOT / "evaluation" / "phase2" / "discussions.jsonl"
    corpus_path = ROOT / "evaluation" / "phase3" / "rag-corpus.jsonl"
    if args.freeze:
        result = asyncio.run(freeze_candidates(query_path, corpus_path))
    elif args.execute:
        if args.max_cost_cny is None or args.max_cost_cny <= 0:
            raise SystemExit("--execute requires a positive --max-cost-cny hard budget")
        result = asyncio.run(
            execute_experiment(
                SNAPSHOT_PATH,
                modes=_modes(args.models),
                max_cost_cny=args.max_cost_cny,
                limit=args.limit,
            )
        )
    elif args.rebuild_report:
        result = rebuild_report(annotation_path=args.labels, labels_manifest_path=args.labels_manifest)
    else:
        validate_frozen_artifacts()
        if HASHES_PATH.exists():
            validate_hash_manifest(HASHES_PATH)
        result = dry_run(SNAPSHOT_PATH, _modes(args.models), args.limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
