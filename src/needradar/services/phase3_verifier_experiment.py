from __future__ import annotations

import hashlib
import json
from collections import Counter
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from typing import Any

from needradar.services.content_verifier import ContentVerifier, VerificationStageError
from needradar.services.phase3_verifier_benchmark import validate_verifier_benchmark
from needradar.services.phase3_verifier_metrics import compose_score, score_verifier_predictions

SCHEMA_VERSION = 2
EXTRACTION_CONFIGS = ("rule_only", "llm_only", "hybrid")
EVIDENCE_CONFIGS = ("no_evidence", "titles_only", "snippet_200", "snippet_800")
SCORE_CONFIGS = ("fact_only", "fact_consistency", "full_weighted")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records), encoding="utf-8"
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _pop_usage(provider: Any) -> dict[str, Any]:
    pop = getattr(provider, "pop_last_usage", None)
    return (pop() if pop else None) or {}


def _record_usage(entries: list[dict[str, Any]], provider: Any, stage: str, configuration: str) -> None:
    usage = _pop_usage(provider)
    if usage:
        entries.append({"stage": stage, "configuration": configuration, "usage": usage})


def _record_traces(entries: list[dict[str, Any]], verifier: ContentVerifier, stage: str, configuration: str) -> None:
    entries.extend({**trace, "stage": stage, "configuration": configuration} for trace in verifier.pop_call_traces())


def _claims(claims) -> list[dict[str, Any]]:
    return [asdict(claim) for claim in claims]


def _usage_summary(records: list[dict[str, Any]], pricing: dict[str, float]) -> dict[str, float | int]:
    usages = [entry["usage"] for record in records for entry in record["usage"]]
    input_tokens = sum(int(usage.get("input_tokens", 0)) for usage in usages)
    output_tokens = sum(int(usage.get("output_tokens", 0)) for usage in usages)
    cached_tokens = sum(int(usage.get("cached_tokens", 0)) for usage in usages)
    actual_cost = sum(float(usage.get("cost_cny", 0.0)) for usage in usages)
    no_cache_cost = (
        input_tokens * pricing.get("input_per_million", 0.0) + output_tokens * pricing.get("output_per_million", 0.0)
    ) / 1_000_000
    responses_with_usage = len(usages)
    actual_calls = sum(int(record.get("provider_attempts", 0)) for record in records)
    retry_attempts = sum(
        int(history.get("provider_attempts", 0)) for record in records for history in record.get("retry_history", [])
    )
    final_stage_calls = actual_calls - retry_attempts
    naive_calls = len(records) * 20
    planned_dag_calls = len(records) * 5
    return {
        "actual_calls": actual_calls,
        "responses_with_usage": responses_with_usage,
        "retry_attempts": retry_attempts,
        "final_stage_calls": final_stage_calls,
        "planned_dag_calls": planned_dag_calls,
        "naive_independent_calls": naive_calls,
        "artifact_reuse_calls_saved": naive_calls - planned_dag_calls,
        "stage_calls_skipped": planned_dag_calls - final_stage_calls,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_tokens": cached_tokens,
        "total_tokens": input_tokens + output_tokens,
        "actual_cost_cny": actual_cost,
        "cost_without_provider_cache_cny": no_cache_cost,
        "provider_cache_savings_cny": no_cache_cost - actual_cost,
    }


def estimate_verifier_calls(record_count: int) -> dict[str, int]:
    return {
        "records": record_count,
        "actual_calls": record_count * 5,
        "naive_independent_calls": record_count * 20,
        "artifact_reuse_calls_saved": record_count * 15,
    }


def _stage_summary(records: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    counts: dict[str, Counter] = {}
    for record in records:
        for stage, result in record["stage_statuses"].items():
            counts.setdefault(stage, Counter())[result["status"]] += 1
            for configuration, configured_result in result.get("configurations", {}).items():
                key = f"{stage}.{configuration}"
                counts.setdefault(key, Counter())[configured_result["status"]] += 1
    return {stage: dict(sorted(values.items())) for stage, values in sorted(counts.items())}


def _has_failed_stage(record: dict[str, Any]) -> bool:
    return any(
        result["status"] == "failed"
        or any(configured["status"] == "failed" for configured in result.get("configurations", {}).values())
        for result in record["stage_statuses"].values()
    )


async def run_verifier_experiment(
    input_path: Path,
    gold_path: Path,
    manifest_path: Path,
    output_dir: Path,
    provider: Any,
    *,
    model_id: str,
    provider_params: dict[str, Any],
    pricing: dict[str, float],
    retry_failed: bool = False,
    max_provider_attempts: int = 150,
) -> dict[str, Any]:
    validate_verifier_benchmark(input_path, gold_path, manifest_path, require_complete=True)
    inputs = _read_jsonl(input_path)
    gold = _read_jsonl(gold_path)
    effective_provider_params = {
        **provider_params,
        "extra_body": {"thinking": {"type": "disabled"}},
    }
    provenance = {
        "schema_version": SCHEMA_VERSION,
        "input_sha256": _sha256(input_path),
        "gold_sha256": _sha256(gold_path),
        "manifest_sha256": _sha256(manifest_path),
        "model_id": model_id,
        "provider_params": effective_provider_params,
        "pricing": pricing,
        "configurations": {
            "extraction": list(EXTRACTION_CONFIGS),
            "evidence": list(EVIDENCE_CONFIGS),
            "score": list(SCORE_CONFIGS),
        },
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    run_path = output_dir / "run.json"
    prediction_path = output_dir / "predictions.jsonl"
    metrics_path = output_dir / "metrics.json"
    if run_path.exists():
        stored = json.loads(run_path.read_text(encoding="utf-8"))
        if any(stored.get(key) != value for key, value in provenance.items()):
            raise ValueError("existing verifier run provenance does not match")
    completed = {record["id"]: record for record in _read_jsonl(prediction_path)} if prediction_path.exists() else {}
    retry_records = {}
    if retry_failed:
        retry_records = {record_id: record for record_id, record in completed.items() if _has_failed_stage(record)}
        for record_id in retry_records:
            del completed[record_id]
    total_provider_attempts = sum(record.get("provider_attempts", 0) for record in completed.values()) + sum(
        record.get("provider_attempts", 0) for record in retry_records.values()
    )
    verifier = ContentVerifier(provider=provider, strict=True)

    for input_record in inputs:
        record_id = input_record["id"]
        if record_id in completed:
            continue
        if total_provider_attempts + 5 > max_provider_attempts:
            raise RuntimeError(f"verifier provider-attempt cap would exceed {max_provider_attempts}")
        body = input_record["report_body"]
        sources = input_record["sources"]
        usage = []
        call_traces = []
        provider_attempts = 0
        stage_statuses = {"input_loading": {"status": "success", "reason": ""}}
        rule_claims = verifier._rule_based_claims(body)
        try:
            llm_claims = await verifier._llm_extract_claims_batch(body)
            stage_statuses["claim_extraction"] = {"status": "success", "reason": ""}
        except VerificationStageError as error:
            llm_claims = []
            stage_statuses["claim_extraction"] = {"status": "failed", "reason": str(error)}
        provider_attempts += verifier.pop_provider_attempts()
        _record_traces(call_traces, verifier, "claim_extraction", "llm_only")
        _record_usage(usage, provider, "claim_extraction", "llm_only")
        llm_succeeded = stage_statuses["claim_extraction"]["status"] == "success"
        hybrid_claims = (
            verifier._deduplicate_claims(deepcopy(llm_claims) + deepcopy(rule_claims)) if llm_succeeded else []
        )
        hybrid_succeeded = llm_succeeded and len(hybrid_claims) <= 12
        if llm_succeeded and not hybrid_succeeded:
            hybrid_claims = []
            stage_statuses["claim_extraction"] = {
                "status": "failed",
                "reason": "hybrid extraction exceeds the 12-claim call cap",
            }
        stage_statuses["claim_extraction"]["configurations"] = {
            "rule_only": {"status": "success", "reason": ""},
            "llm_only": {
                "status": "success" if llm_succeeded else "failed",
                "reason": "" if llm_succeeded else stage_statuses["claim_extraction"]["reason"],
            },
            "hybrid": {
                "status": "success" if hybrid_succeeded else "failed",
                "reason": "" if hybrid_succeeded else stage_statuses["claim_extraction"]["reason"],
            },
        }
        extraction_succeeded = hybrid_succeeded
        extraction = {
            "rule_only": _claims(rule_claims),
            "llm_only": _claims(llm_claims),
            "hybrid": _claims(hybrid_claims),
        }
        evidence = {}
        no_evidence_claims = await verifier._fact_check_claims(deepcopy(hybrid_claims), [])
        evidence_objects = {"no_evidence": no_evidence_claims}
        evidence["no_evidence"] = _claims(no_evidence_claims)
        stage_statuses["source_resolution"] = {"status": "success", "reason": ""}
        fact_failures = []
        failed_evidence_configs = set()
        fact_statuses = {}
        for name, source_chars, include_content in (
            ("titles_only", 0, False),
            ("snippet_200", 200, True),
            ("snippet_800", 800, True),
        ):
            if not hybrid_claims:
                checked = []
                reason = "claim extraction unavailable" if not extraction_succeeded else "no extracted claims"
                fact_statuses[name] = {"status": "skipped", "reason": reason}
            else:
                try:
                    checked = await verifier._fact_check_claims(
                        deepcopy(hybrid_claims),
                        sources,
                        source_chars=source_chars,
                        include_content=include_content,
                    )
                    fact_statuses[name] = {"status": "success", "reason": ""}
                except VerificationStageError as error:
                    checked = []
                    fact_failures.append(f"{name}: {error}")
                    failed_evidence_configs.add(name)
                    fact_statuses[name] = {"status": "failed", "reason": str(error)}
            provider_attempts += verifier.pop_provider_attempts()
            _record_traces(call_traces, verifier, "fact_check", name)
            _record_usage(usage, provider, "fact_check", name)
            evidence_objects[name] = checked
            evidence[name] = _claims(checked)
        stage_statuses["fact_check"] = {
            "status": "failed" if fact_failures else "success" if hybrid_claims else "skipped",
            "reason": "; ".join(fact_failures) if fact_failures else "" if hybrid_claims else "no claims",
            "configurations": fact_statuses,
        }
        try:
            consistency_score = await verifier._check_consistency(body, hybrid_claims)
            stage_statuses["consistency"] = {"status": "success", "reason": ""}
        except VerificationStageError as error:
            consistency_score = None
            stage_statuses["consistency"] = {"status": "failed", "reason": str(error)}
        provider_attempts += verifier.pop_provider_attempts()
        _record_traces(call_traces, verifier, "consistency", "full")
        _record_usage(usage, provider, "consistency", "full")
        full_claims = (
            []
            if not extraction_succeeded or not hybrid_claims or "snippet_200" in failed_evidence_configs
            else deepcopy(hybrid_claims)
        )
        for claim, checked in zip(full_claims, evidence["snippet_200"]):
            claim.verdict = checked["verdict"]
            claim.confidence = checked["confidence"]
            claim.evidence = checked["evidence"]
            claim.risk_flags = checked["risk_flags"]
        source_score = verifier._assess_source_reliability(sources, input_record["report_meta"])
        evidence_scores = {}
        for name, checked_claims in evidence_objects.items():
            available = extraction_succeeded and bool(checked_claims) and name not in failed_evidence_configs
            if not available:
                evidence_scores[name] = None
                continue
            fact_component = verifier._aggregate(checked_claims, 0.0, source_score).fact_check_score
            evidence_scores[name] = compose_score(fact_component, consistency_score, source_score)
        fact_score = verifier._aggregate(full_claims, 0.0, source_score).fact_check_score if full_claims else None
        score_variants = {
            "fact_only": compose_score(fact_score, None, None),
            "fact_consistency": (
                compose_score(fact_score, consistency_score, None) if consistency_score is not None else None
            ),
            "full_weighted": (
                compose_score(fact_score, consistency_score, source_score) if consistency_score is not None else None
            ),
        }
        suggestions = verifier._generate_suggestions(full_claims)
        new_record = {
            "id": record_id,
            "extraction": extraction,
            "evidence": evidence,
            "resolved_source_ids": [source["id"] for source in sources],
            "consistency_score": consistency_score,
            "internal_contradiction": consistency_score < 80 if consistency_score is not None else None,
            "source_reliability_score": source_score,
            "evidence_scores": evidence_scores,
            "score_variants": score_variants,
            "suggestions": [
                {
                    **suggestion,
                    "claim_id": next(
                        (claim.claim_id for claim in full_claims if claim.text == suggestion["claim"]), ""
                    ),
                }
                for suggestion in suggestions
            ],
            "usage": usage,
            "call_traces": call_traces,
            "provider_attempts": provider_attempts,
            "stage_statuses": stage_statuses,
            "artifacts": {
                "llm_claims": _artifact_hash(extraction["llm_only"]),
                "hybrid_claims": _artifact_hash(extraction["hybrid"]),
                **{f"evidence_{name}": _artifact_hash(value) for name, value in evidence.items()},
            },
        }
        total_provider_attempts += provider_attempts
        previous = retry_records.get(record_id)
        if previous:
            new_record["usage"] = previous["usage"] + new_record["usage"]
            new_record["call_traces"] = previous["call_traces"] + new_record["call_traces"]
            new_record["provider_attempts"] += previous["provider_attempts"]
            new_record["retry_count"] = int(previous.get("retry_count", 0)) + 1
            new_record["retry_history"] = [
                *previous.get("retry_history", []),
                {
                    "stage_statuses": previous["stage_statuses"],
                    "provider_attempts": previous["provider_attempts"],
                    "artifacts": previous["artifacts"],
                },
            ]
        completed[record_id] = new_record
        ordered = [completed[item["id"]] for item in inputs if item["id"] in completed]
        _write_jsonl(prediction_path, ordered)
        run_path.write_text(
            json.dumps({**provenance, "requested": len(inputs), "completed": len(ordered)}, indent=2) + "\n",
            encoding="utf-8",
        )

    records = [completed[item["id"]] for item in inputs]
    extraction_metrics = {}
    for configuration in EXTRACTION_CONFIGS:
        valid_records = [
            record
            for record in records
            if record["stage_statuses"]["claim_extraction"]["configurations"][configuration]["status"] == "success"
        ]
        valid_ids = {record["id"] for record in valid_records}
        predictions = [{"id": record["id"], "claims": record["extraction"][configuration]} for record in valid_records]
        result = score_verifier_predictions(
            [record for record in inputs if record["id"] in valid_ids],
            [record for record in gold if record["id"] in valid_ids],
            predictions,
        )["claim_extraction"]
        extraction_metrics[configuration] = {"records": len(valid_records), **result}
    evidence_metrics = {}
    for configuration in EVIDENCE_CONFIGS:
        valid_records = []
        for record in records:
            if record["stage_statuses"]["claim_extraction"]["configurations"]["hybrid"]["status"] != "success":
                continue
            if not record["extraction"]["hybrid"]:
                continue
            if configuration != "no_evidence":
                status = record["stage_statuses"]["fact_check"]["configurations"][configuration]["status"]
                if status != "success":
                    continue
            valid_records.append(record)
        valid_ids = {record["id"] for record in valid_records}
        predictions = [
            {
                "id": record["id"],
                "claims": record["evidence"][configuration],
                "resolved_source_ids": [] if configuration == "no_evidence" else record["resolved_source_ids"],
                "internal_contradiction": record["internal_contradiction"],
                "overall_score": record["evidence_scores"][configuration],
                "suggestions": record["suggestions"] if configuration == "snippet_200" else [],
            }
            for record in valid_records
        ]
        evidence_metrics[configuration] = {
            "records": len(valid_records),
            **score_verifier_predictions(
                [record for record in inputs if record["id"] in valid_ids],
                [record for record in gold if record["id"] in valid_ids],
                predictions,
            ),
        }
    score_metrics = {}
    for configuration in SCORE_CONFIGS:
        valid_records = [
            record
            for record in records
            if record["score_variants"][configuration] is not None
            and record["stage_statuses"]["fact_check"]["configurations"]["snippet_200"]["status"] == "success"
        ]
        valid_ids = {record["id"] for record in valid_records}
        predictions = [
            {
                "id": record["id"],
                "claims": record["evidence"]["snippet_200"],
                "resolved_source_ids": record["resolved_source_ids"],
                "internal_contradiction": record["internal_contradiction"],
                "overall_score": record["score_variants"][configuration],
                "suggestions": record["suggestions"],
            }
            for record in valid_records
        ]
        score_metrics[configuration] = score_verifier_predictions(
            [record for record in inputs if record["id"] in valid_ids],
            [record for record in gold if record["id"] in valid_ids],
            predictions,
        )["ranking"]
    stage_summary = _stage_summary(records)
    metrics = {
        "extraction": extraction_metrics,
        "evidence": evidence_metrics,
        "score_composition": score_metrics,
        "stage_summary": stage_summary,
        "usage": _usage_summary(records, pricing),
    }
    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    run = {
        **provenance,
        "requested": len(inputs),
        "completed": len(records),
        "stage_summary": stage_summary,
        "usage": metrics["usage"],
    }
    run_path.write_text(json.dumps(run, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return run
