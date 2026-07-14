from __future__ import annotations

import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from needradar.schemas.schemas import ExtractedRequirement, RawDiscussionItem
from needradar.services.extraction_benchmark import _load_extraction_prompt
from needradar.services.extraction_metrics import (
    CATEGORICAL_FIELDS,
    TEXT_FIELDS,
    _char_ngram_dice,
    score_extractions,
)
from needradar.services.noise_filter import _rule_filter

CONFIGURATIONS = ("no_rag", "rag", "rag_hitl")
DEFAULT_RAG_PARAMS = {"n_results": 3, "min_score": 0.0, "max_chars": 1500}
DEFAULT_MAX_DISCUSSION_CHARS = 47_000
SCHEMA_VERSION = 3
USAGE_KEYS = ("input_tokens", "output_tokens", "cached_tokens", "total_tokens", "cost_cny")


def _empty_usage() -> dict[str, int | float]:
    return {
        "input_tokens": 0,
        "output_tokens": 0,
        "cached_tokens": 0,
        "total_tokens": 0,
        "cost_cny": 0.0,
    }


def _add_usage(target: dict, source: dict | None) -> None:
    for key in USAGE_KEYS:
        target[key] += (source or {}).get(key, 0)


def _usage_bundle() -> dict[str, dict[str, int | float]]:
    return {"extraction": _empty_usage(), "retrieval": _empty_usage(), "total": _empty_usage()}


def _finalize_usage(bundle: dict[str, dict]) -> None:
    bundle["total"] = _empty_usage()
    _add_usage(bundle["total"], bundle["extraction"])
    _add_usage(bundle["total"], bundle["retrieval"])


def _pop_usage(component: Any) -> dict:
    pop_last_usage = getattr(component, "pop_last_usage", None)
    return (pop_last_usage() if pop_last_usage else None) or {}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    seen = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        record = json.loads(line)
        record_id = record.get("id")
        if not record_id or record_id in seen:
            raise ValueError(f"{path}:{line_number}: missing or duplicate id")
        seen.add(record_id)
        records.append(record)
    return records


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def _core_prediction(record_id: str, extracted: ExtractedRequirement) -> dict[str, Any]:
    return {
        "id": record_id,
        "requirement_present": "yes",
        "title": extracted.title,
        "description": extracted.description,
        "pain_point": extracted.pain_point,
        "use_case": extracted.use_case,
        "sentiment": extracted.sentiment.value,
        "emotion": extracted.emotion.value,
        "confidence": extracted.confidence,
        "rejection_reason": "",
        "extraction_error": "",
    }


def _error_prediction(record_id: str, *, extraction_error: str = "", retrieval_error: str = "") -> dict:
    return {
        "id": record_id,
        "requirement_present": "error",
        "title": "",
        "description": "",
        "pain_point": "",
        "use_case": "",
        "sentiment": "mild",
        "emotion": "neutral",
        "confidence": 0.0,
        "rejection_reason": "",
        "extraction_error": extraction_error[:500],
        "retrieval_error": retrieval_error[:500],
    }


def _decorate_prediction(
    prediction: dict,
    configuration: str,
    rag_context_used: bool,
    usage: dict,
) -> dict:
    prediction.update(
        {
            "configuration": configuration,
            "rag_context_used": rag_context_used,
            "hitl_edited": False,
            "hitl_edited_fields": [],
            "pre_hitl_prediction": None,
            "usage": usage,
        }
    )
    prediction.setdefault("retrieval_error", "")
    return prediction


def _apply_hitl(prediction: dict, gold: dict) -> None:
    if prediction["requirement_present"] == "error":
        return

    edited_fields = []
    presence_changed = prediction["requirement_present"] != gold["requirement_present"]
    if presence_changed:
        edited_fields = [
            field
            for field in ("requirement_present", *TEXT_FIELDS, *CATEGORICAL_FIELDS)
            if prediction.get(field) != gold.get(field)
        ]
    elif gold["requirement_present"] == "yes":
        edited_fields.extend(
            field for field in TEXT_FIELDS if _char_ngram_dice(prediction.get(field, ""), gold.get(field, "")) < 0.5
        )
        edited_fields.extend(field for field in CATEGORICAL_FIELDS if prediction.get(field) != gold.get(field))

    if not edited_fields:
        return

    prediction["pre_hitl_prediction"] = {
        key: value
        for key, value in prediction.items()
        if key
        not in {
            "configuration",
            "rag_context_used",
            "hitl_edited",
            "hitl_edited_fields",
            "pre_hitl_prediction",
            "usage",
            "retrieval_error",
        }
    }
    fields_to_copy = ("requirement_present", *TEXT_FIELDS, *CATEGORICAL_FIELDS) if presence_changed else edited_fields
    for field in fields_to_copy:
        prediction[field] = gold[field]
    prediction["hitl_edited"] = True
    prediction["hitl_edited_fields"] = edited_fields


def _sum_prediction_usage(predictions: list[dict]) -> dict:
    total = _usage_bundle()
    for prediction in predictions:
        usage = prediction.get("usage", {})
        _add_usage(total["extraction"], usage.get("extraction"))
        _add_usage(total["retrieval"], usage.get("retrieval"))
    _finalize_usage(total)
    return total


def _score_records(discussions: list[dict], gold_records: list[dict], predictions: list[dict]) -> dict:
    with tempfile.TemporaryDirectory(prefix="needradar-phase3-") as directory:
        base = Path(directory)
        discussion_path = base / "discussions.jsonl"
        gold_path = base / "gold.jsonl"
        prediction_path = base / "predictions.jsonl"
        _write_jsonl(discussion_path, discussions)
        _write_jsonl(gold_path, gold_records)
        _write_jsonl(prediction_path, predictions)
        return score_extractions(gold_path, prediction_path, discussion_path)


def _pre_hitl_predictions(predictions: list[dict]) -> list[dict]:
    restored = []
    for prediction in predictions:
        if prediction.get("pre_hitl_prediction"):
            restored.append(prediction["pre_hitl_prediction"])
        else:
            restored.append(prediction)
    return restored


def _metric_summary(
    metrics: dict,
    usage: dict,
    hitl_rate: float,
    pricing: dict[str, float],
) -> dict[str, float | int | None]:
    input_tokens = usage["extraction"]["input_tokens"]
    cached_tokens = min(usage["extraction"]["cached_tokens"], input_tokens)
    cache_savings = None
    if pricing:
        cache_savings = (
            cached_tokens * (pricing["input_per_million"] - pricing["input_cache_hit_per_million"]) / 1_000_000
        )
    actual_cost = usage["total"]["cost_cny"]
    summary: dict[str, float | int | None] = {
        "requirement_presence_accuracy": metrics["requirement_presence"]["accuracy"],
        "sentiment_accuracy": metrics["categorical_field_accuracy"]["sentiment"]["accuracy"],
        "emotion_accuracy": metrics["categorical_field_accuracy"]["emotion"]["accuracy"],
        "duplicate_rate": metrics["duplicates"]["rate_among_accepted"],
        "extraction_failure_rate": metrics["extraction_failures"]["rate"],
        "proxy_edit_rate": metrics["proxy_record_edit_rate"]["rate"],
        "hitl_record_edit_rate": hitl_rate,
        "total_tokens": usage["total"]["total_tokens"],
        "cached_tokens": cached_tokens,
        "cache_hit_rate": cached_tokens / input_tokens if input_tokens else 0.0,
        "cost_cny": actual_cost,
        "cache_savings_cny": cache_savings,
        "cost_without_cache_cny": actual_cost + cache_savings if cache_savings is not None else None,
    }
    for field in TEXT_FIELDS:
        summary[f"{field}_mean_dice"] = metrics["text_field_similarity"][field]["mean_dice"]
    return summary


def _comparison(current: dict, baseline: dict) -> dict:
    result = {}
    for key, current_value in current.items():
        baseline_value = baseline.get(key)
        if current_value is None or baseline_value is None:
            result[key] = {
                "baseline": baseline_value,
                "current": current_value,
                "absolute_change": None,
                "relative_change": None,
            }
            continue
        absolute = current_value - baseline_value
        result[key] = {
            "baseline": baseline_value,
            "current": current_value,
            "absolute_change": absolute,
            "relative_change": absolute / baseline_value if baseline_value else None,
        }
    return result


def _build_run(
    provenance: dict,
    predictions: list[dict],
    requested: int,
    resumed: int,
) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        **provenance,
        "requested": requested,
        "completed": len(predictions),
        "resumed": resumed,
        "extraction_failures": sum(bool(item.get("extraction_error")) for item in predictions),
        "retrieval_failures": sum(bool(item.get("retrieval_error")) for item in predictions),
        "usage": _sum_prediction_usage(predictions),
    }


async def run_phase3_experiment(
    dataset_path: Path,
    gold_path: Path,
    output_dir: Path,
    root: Path,
    provider: Any,
    *,
    configuration: str,
    retriever: Any | None = None,
    model_id: str,
    limit: int | None = None,
    rag_params: dict[str, Any] | None = None,
    provider_params: dict[str, Any] | None = None,
    pricing: dict[str, float] | None = None,
    max_discussion_chars: int = DEFAULT_MAX_DISCUSSION_CHARS,
) -> dict[str, Any]:
    if configuration not in CONFIGURATIONS:
        raise ValueError(f"configuration must be one of {', '.join(CONFIGURATIONS)}")
    uses_rag = configuration != "no_rag"
    if uses_rag and retriever is None:
        raise ValueError(f"retriever is required for {configuration}")
    if max_discussion_chars <= 0:
        raise ValueError("max_discussion_chars must be positive")

    discussions = _read_jsonl(dataset_path)
    if limit is not None:
        discussions = discussions[:limit]
    gold_by_id = {record["id"]: record for record in _read_jsonl(gold_path)}
    missing_gold = [record["id"] for record in discussions if record["id"] not in gold_by_id]
    if missing_gold:
        raise ValueError(f"gold records missing IDs: {', '.join(missing_gold)}")
    gold_records = [gold_by_id[record["id"]] for record in discussions]

    prompt = _load_extraction_prompt(root)
    selected_provider_params = dict(provider_params or {})
    selected_pricing = dict(pricing or {})
    selected_rag_params = dict(DEFAULT_RAG_PARAMS if rag_params is None else rag_params) if uses_rag else {}
    retriever_provenance = {}
    if uses_rag and hasattr(retriever, "get_provenance"):
        retriever_provenance = retriever.get_provenance()
    selected_ids = json.dumps([record["id"] for record in discussions], separators=(",", ":")).encode()
    provenance = {
        "configuration": configuration,
        "dataset_sha256": _sha256_file(dataset_path),
        "gold_sha256": _sha256_file(gold_path),
        "selection_sha256": _sha256_bytes(selected_ids),
        "prompt_sha256": _sha256_bytes(prompt.encode("utf-8")),
        "model_id": model_id,
        "rag_params": selected_rag_params,
        "retriever_provenance": retriever_provenance,
        "provider_params": selected_provider_params,
        "pricing": selected_pricing,
        "max_discussion_chars": max_discussion_chars,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    prediction_path = output_dir / "predictions.jsonl"
    run_path = output_dir / "run.json"
    metrics_path = output_dir / "metrics.json"
    if run_path.exists():
        stored_run = json.loads(run_path.read_text(encoding="utf-8"))
        stored_provenance = {key: stored_run.get(key) for key in provenance}
        if stored_run.get("schema_version") != SCHEMA_VERSION or stored_provenance != provenance:
            raise ValueError("existing run provenance does not match requested experiment")

    existing = _read_jsonl(prediction_path) if prediction_path.exists() else []
    selected_ids_set = {record["id"] for record in discussions}
    completed = {record["id"]: record for record in existing if record["id"] in selected_ids_set}
    resumed = len(completed)

    for discussion in discussions:
        record_id = discussion["id"]
        if record_id in completed:
            continue
        item = RawDiscussionItem(
            platform=discussion["platform"],
            source_url=discussion["source_url"],
            title=discussion["title"],
            content=discussion["content"],
            tags=discussion.get("tags", []),
        )
        usage = _usage_bundle()
        rejected = _rule_filter(item)
        if rejected is not None:
            prediction = {
                "id": record_id,
                "requirement_present": "no",
                "title": "",
                "description": "",
                "pain_point": "",
                "use_case": "",
                "sentiment": "mild",
                "emotion": "neutral",
                "confidence": rejected.confidence,
                "rejection_reason": rejected.reason,
                "extraction_error": "",
            }
            prediction = _decorate_prediction(prediction, configuration, False, usage)
        else:
            rag_context = ""
            if uses_rag:
                try:
                    rag_context = await retriever.retrieve_context(
                        query=item.title,
                        **selected_rag_params,
                    )
                except Exception as error:
                    _add_usage(usage["retrieval"], _pop_usage(retriever))
                    _finalize_usage(usage)
                    prediction = _error_prediction(record_id, retrieval_error=str(error))
                    prediction = _decorate_prediction(prediction, configuration, False, usage)
                else:
                    _add_usage(usage["retrieval"], _pop_usage(retriever))
                    if not rag_context.strip():
                        _finalize_usage(usage)
                        prediction = _error_prediction(record_id, retrieval_error="no RAG context returned")
                        prediction = _decorate_prediction(prediction, configuration, False, usage)
            if not uses_rag or rag_context:
                input_text = f"讨论标题：{item.title}\n\n讨论内容：\n{item.content[:max_discussion_chars]}"
                if rag_context:
                    input_text += (
                        "\n\n以下是 held-out 公开讨论中检索到的补充上下文。"
                        "仅用于帮助理解，不要把上下文中的事实当作当前讨论的事实：\n\n" + rag_context
                    )
                extracted = None
                extraction_error = ""
                for _attempt in range(2):
                    try:
                        extracted = await provider.extract_structured(
                            prompt=prompt,
                            text=input_text,
                            schema=ExtractedRequirement,
                            fallback_to_default=False,
                        )
                        extraction_error = ""
                        break
                    except Exception as error:
                        extraction_error = str(error)
                    finally:
                        _add_usage(usage["extraction"], _pop_usage(provider))
                _finalize_usage(usage)
                if extracted is None:
                    prediction = _error_prediction(record_id, extraction_error=extraction_error)
                else:
                    prediction = _core_prediction(record_id, extracted)
                prediction = _decorate_prediction(prediction, configuration, bool(rag_context), usage)

        if configuration == "rag_hitl":
            _apply_hitl(prediction, gold_by_id[record_id])
        completed[record_id] = prediction
        ordered = [completed[record["id"]] for record in discussions if record["id"] in completed]
        _write_jsonl(prediction_path, ordered)
        run_path.write_text(
            json.dumps(_build_run(provenance, ordered, len(discussions), resumed), indent=2) + "\n",
            encoding="utf-8",
        )

    predictions = [completed[record["id"]] for record in discussions]
    run = _build_run(provenance, predictions, len(discussions), resumed)
    run_path.write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")

    metrics = _score_records(discussions, gold_records, predictions)
    edited = [prediction for prediction in predictions if prediction["hitl_edited"]]
    edited_field_counts = Counter(field for prediction in edited for field in prediction["hitl_edited_fields"])
    hitl_rate = len(edited) / len(predictions) if predictions else 0.0
    summary = _metric_summary(metrics, run["usage"], hitl_rate, selected_pricing)
    pre_hitl = None
    if configuration == "rag_hitl":
        pre_hitl = _score_records(discussions, gold_records, _pre_hitl_predictions(predictions))
    metrics["phase3"] = {
        "configuration": configuration,
        "summary": summary,
        "hitl": {
            "edited_records": len(edited),
            "record_edit_rate": hitl_rate,
            "edited_fields": sum(edited_field_counts.values()),
            "field_counts": dict(sorted(edited_field_counts.items())),
        },
        "pre_hitl": pre_hitl,
        "baseline_comparison": {"status": "unavailable"},
    }
    baseline_path = output_dir.parent / "no_rag" / "metrics.json"
    if configuration == "no_rag":
        metrics["phase3"]["baseline_comparison"] = {
            "status": "baseline",
            "metrics": _comparison(summary, summary),
        }
    elif baseline_path.exists():
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))["phase3"]["summary"]
        metrics["phase3"]["baseline_comparison"] = {
            "status": "available",
            "metrics": _comparison(summary, baseline),
        }
    metrics_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return run


async def run_phase3_suite(
    dataset_path: Path,
    gold_path: Path,
    output_root: Path,
    root: Path,
    provider: Any,
    *,
    retriever: Any,
    model_id: str,
    limit: int | None = None,
    rag_params: dict[str, Any] | None = None,
    provider_params: dict[str, Any] | None = None,
    pricing: dict[str, float] | None = None,
    max_discussion_chars: int = DEFAULT_MAX_DISCUSSION_CHARS,
) -> dict[str, dict[str, Any]]:
    runs = {}
    for configuration in CONFIGURATIONS:
        runs[configuration] = await run_phase3_experiment(
            dataset_path,
            gold_path,
            output_root / configuration,
            root,
            provider,
            configuration=configuration,
            retriever=retriever,
            model_id=model_id,
            limit=limit,
            rag_params=rag_params,
            provider_params=provider_params,
            pricing=pricing,
            max_discussion_chars=max_discussion_chars,
        )
    return runs
