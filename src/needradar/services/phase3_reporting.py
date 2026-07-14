from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from needradar.services.extraction_metrics import TEXT_FIELDS, _char_ngram_dice

CONFIGURATIONS = ("no_rag", "rag", "rag_hitl")
COMPARISON_FIELDS = (
    "requirement_presence_accuracy",
    "sentiment_accuracy",
    "emotion_accuracy",
    "title_mean_dice",
    "description_mean_dice",
    "pain_point_mean_dice",
    "use_case_mean_dice",
    "duplicate_rate",
    "proxy_edit_rate",
    "total_tokens",
    "cost_cny",
)
SHARED_EXPERIMENT_FIELDS = (
    "schema_version",
    "dataset_sha256",
    "gold_sha256",
    "selection_sha256",
    "prompt_sha256",
    "model_id",
    "provider_params",
    "pricing",
    "max_discussion_chars",
)


def _read_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    records = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        record_id = record["id"]
        if record_id in records:
            raise ValueError(f"duplicate record ID in {path}: {record_id}")
        records[record_id] = record
    return records


def _delta(current: float, baseline: float) -> dict[str, float | None]:
    absolute = current - baseline
    return {
        "baseline": baseline,
        "current": current,
        "absolute_change": absolute,
        "relative_change": absolute / baseline if baseline else None,
    }


def _platform_accuracy(metrics: dict) -> dict[str, float]:
    result = {}
    for platform, values in metrics["failure_analysis"]["by_platform"].items():
        confusion = values["requirement_presence_confusion"]
        result[platform] = (confusion["true_positive"] + confusion["true_negative"]) / values["record_count"]
    return result


def build_phase3_report(
    run_root: Path,
    discussion_path: Path,
    gold_path: Path,
) -> dict[str, Any]:
    discussions = _read_jsonl(discussion_path)
    gold = _read_jsonl(gold_path)
    runs = {name: json.loads((run_root / name / "run.json").read_text(encoding="utf-8")) for name in CONFIGURATIONS}
    metrics = {
        name: json.loads((run_root / name / "metrics.json").read_text(encoding="utf-8")) for name in CONFIGURATIONS
    }
    predictions = {name: _read_jsonl(run_root / name / "predictions.jsonl") for name in CONFIGURATIONS}

    baseline_run = runs["no_rag"]
    mismatched_fields = [
        field
        for field in SHARED_EXPERIMENT_FIELDS
        if any(run.get(field) != baseline_run.get(field) for run in runs.values())
    ]
    if mismatched_fields:
        raise ValueError(
            "Phase 3 configurations do not have shared experiment provenance: " + ", ".join(mismatched_fields)
        )
    if any(run.get("configuration") != name for name, run in runs.items()):
        raise ValueError("Phase 3 run configuration does not match its directory")
    if any(runs["rag_hitl"].get(field) != runs["rag"].get(field) for field in ("rag_params", "retriever_provenance")):
        raise ValueError("Phase 3 RAG provenance differs between rag and rag_hitl")

    expected_ids = set(gold)
    if set(discussions) != expected_ids:
        raise ValueError("Phase 3 discussion IDs do not match gold IDs")
    if any(set(configuration_predictions) != expected_ids for configuration_predictions in predictions.values()):
        raise ValueError("Phase 3 prediction IDs do not match gold IDs")
    if any(run["requested"] != len(expected_ids) or run["completed"] != len(expected_ids) for run in runs.values()):
        raise ValueError("Phase 3 configuration is incomplete")

    summaries = {name: metrics[name]["phase3"]["summary"] for name in CONFIGURATIONS}
    rag_comparison = {field: _delta(summaries["rag"][field], summaries["no_rag"][field]) for field in COMPARISON_FIELDS}

    transitions = {"improved": 0, "worsened": 0, "unchanged": 0}
    categorical_transitions = {
        field: {"improved": 0, "worsened": 0, "unchanged": 0} for field in ("sentiment", "emotion")
    }
    cases = []
    for record_id, expected in gold.items():
        baseline = predictions["no_rag"][record_id]
        rag = predictions["rag"][record_id]
        baseline_correct = baseline["requirement_present"] == expected["requirement_present"]
        rag_correct = rag["requirement_present"] == expected["requirement_present"]
        if rag_correct and not baseline_correct:
            transitions["improved"] += 1
        elif baseline_correct and not rag_correct:
            transitions["worsened"] += 1
        else:
            transitions["unchanged"] += 1

        if expected["requirement_present"] != "yes":
            continue
        if baseline["requirement_present"] != "yes" or rag["requirement_present"] != "yes":
            continue
        for field in categorical_transitions:
            baseline_field_correct = baseline[field] == expected[field]
            rag_field_correct = rag[field] == expected[field]
            if rag_field_correct and not baseline_field_correct:
                categorical_transitions[field]["improved"] += 1
            elif baseline_field_correct and not rag_field_correct:
                categorical_transitions[field]["worsened"] += 1
            else:
                categorical_transitions[field]["unchanged"] += 1

        field_deltas = {
            field: _char_ngram_dice(expected[field], rag[field]) - _char_ngram_dice(expected[field], baseline[field])
            for field in TEXT_FIELDS
        }
        discussion = discussions[record_id]
        cases.append(
            {
                "id": record_id,
                "platform": discussion["platform"],
                "source_url": discussion["source_url"],
                "discussion_title": discussion["title"],
                "mean_text_similarity_change": sum(field_deltas.values()) / len(field_deltas),
                "field_changes": field_deltas,
            }
        )

    no_rag_platform = _platform_accuracy(metrics["no_rag"])
    rag_platform = _platform_accuracy(metrics["rag"])
    platform_comparison = {
        platform: _delta(rag_platform[platform], no_rag_platform[platform]) for platform in sorted(no_rag_platform)
    }

    actual_cost = sum(summary["cost_cny"] for summary in summaries.values())
    no_cache_cost = sum(summary["cost_without_cache_cny"] for summary in summaries.values())
    cache_savings = no_cache_cost - actual_cost
    hitl = metrics["rag_hitl"]["phase3"]["hitl"]

    return {
        "methodology": (
            "100 frozen query-stratified discussions; proxy gold from two-agent blind annotation "
            "with 7% targeted human review"
        ),
        "records": len(gold),
        "schema_version": runs["no_rag"]["schema_version"],
        "input_hashes": {
            field: baseline_run[field]
            for field in ("dataset_sha256", "gold_sha256", "selection_sha256", "prompt_sha256")
        },
        "model_id": runs["no_rag"]["model_id"],
        "provider_params": runs["no_rag"]["provider_params"],
        "retriever_provenance": runs["rag"]["retriever_provenance"],
        "configurations": summaries,
        "rag_vs_no_rag": rag_comparison,
        "requirement_presence_transitions": transitions,
        "categorical_transitions": categorical_transitions,
        "platform_requirement_accuracy": platform_comparison,
        "hitl": {
            **hitl,
            "pre_review_requirement_accuracy": metrics["rag_hitl"]["phase3"]["pre_hitl"]["requirement_presence"][
                "accuracy"
            ],
            "post_review_requirement_accuracy": summaries["rag_hitl"]["requirement_presence_accuracy"],
        },
        "cache": {
            "actual_cost_cny": actual_cost,
            "cost_without_cache_cny": no_cache_cost,
            "savings_cny": cache_savings,
            "savings_rate": cache_savings / no_cache_cost if no_cache_cost else 0.0,
        },
        "rag_cases": {
            "largest_gains": sorted(
                cases,
                key=lambda item: (-item["mean_text_similarity_change"], item["id"]),
            )[:5],
            "largest_regressions": sorted(
                cases,
                key=lambda item: (item["mean_text_similarity_change"], item["id"]),
            )[:5],
        },
        "limitations": [
            "The sample is query-stratified and platform is confounded with content type.",
            "The proxy gold has only 7% targeted human review; simulated HITL is not 100-person human evidence.",
            "The current retriever uses fallback-sha256-bow-384 embeddings and always injects top-3 context.",
            "The two RAG model runs are independent stochastic calls; HITL pre-review metrics may differ from the standalone RAG run.",
        ],
    }


def _percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def render_phase3_markdown(report: dict[str, Any]) -> str:
    configurations = report["configurations"]
    rag_delta = report["rag_vs_no_rag"]
    transitions = report["requirement_presence_transitions"]
    hitl = report["hitl"]
    cache = report["cache"]
    no_rag_accuracy = configurations["no_rag"]["requirement_presence_accuracy"]
    rag_accuracy = configurations["rag"]["requirement_presence_accuracy"]
    lines = [
        "# Phase 3 RAG and HITL experiment report",
        "",
        "## Executive summary",
        "",
        (
            f"- Requirement-presence accuracy was {_percent(no_rag_accuracy)} without RAG "
            f"and {_percent(rag_accuracy)} with RAG."
        ),
        (
            "- RAG changed emotion accuracy by "
            f"{rag_delta['emotion_accuracy']['absolute_change'] * 100:+.2f} percentage points, "
            "description similarity by "
            f"{rag_delta['description_mean_dice']['absolute_change'] * 100:+.2f} points, and "
            "pain-point similarity by "
            f"{rag_delta['pain_point_mean_dice']['absolute_change'] * 100:+.2f} points."
        ),
        (
            f"- RAG increased tokens by {_percent(rag_delta['total_tokens']['relative_change'])} "
            f"and actual cost by {_percent(rag_delta['cost_cny']['relative_change'])}."
        ),
        (
            f"- Simulated HITL edited {hitl['edited_records']}/{report['records']} records "
            f"({_percent(hitl['record_edit_rate'])}); post-review accuracy is proxy-assisted, not model quality."
        ),
        (
            f"- Prefix caching reduced combined cost from CNY {cache['cost_without_cache_cny']:.6f} "
            f"to CNY {cache['actual_cost_cny']:.6f}, saving {_percent(cache['savings_rate'])}."
        ),
        "",
        "## Configuration results",
        "",
        "| Configuration | Requirement accuracy | Sentiment | Emotion | Proxy edit rate | Tokens | Cost (CNY) | Cache hit |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name in CONFIGURATIONS:
        summary = configurations[name]
        lines.append(
            f"| `{name}` | {_percent(summary['requirement_presence_accuracy'])} | "
            f"{_percent(summary['sentiment_accuracy'])} | {_percent(summary['emotion_accuracy'])} | "
            f"{_percent(summary['proxy_edit_rate'])} | {summary['total_tokens']:,} | "
            f"{summary['cost_cny']:.6f} | {_percent(summary['cache_hit_rate'])} |"
        )

    lines.extend(
        [
            "",
            "## RAG ablation",
            "",
            "| Metric | No RAG | RAG | Absolute change | Relative change |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for field in COMPARISON_FIELDS:
        values = rag_delta[field]
        relative = "n/a" if values["relative_change"] is None else _percent(values["relative_change"])
        lines.append(
            f"| `{field}` | {values['baseline']:.6f} | {values['current']:.6f} | "
            f"{values['absolute_change']:+.6f} | {relative} |"
        )

    lines.extend(
        [
            "",
            (
                "Requirement-presence correctness transitions: "
                f"{transitions['improved']} improved, {transitions['worsened']} worsened, "
                f"and {transitions['unchanged']} unchanged."
            ),
            "",
            "### Categorical correctness transitions",
            "",
            "| Field | Improved | Worsened | Unchanged |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for field, values in report["categorical_transitions"].items():
        lines.append(f"| {field} | {values['improved']} | {values['worsened']} | {values['unchanged']} |")

    lines.extend(
        [
            "",
            "### Platform requirement accuracy",
            "",
            "| Platform | No RAG | RAG | Absolute change |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for platform, values in report["platform_requirement_accuracy"].items():
        lines.append(
            f"| {platform} | {_percent(values['baseline'])} | {_percent(values['current'])} | "
            f"{values['absolute_change'] * 100:+.2f} points |"
        )

    lines.extend(
        [
            "",
            "## HITL burden",
            "",
            f"- Pre-review requirement accuracy: {_percent(hitl['pre_review_requirement_accuracy'])}",
            f"- Post-review requirement accuracy: {_percent(hitl['post_review_requirement_accuracy'])}",
            f"- Edited records: {hitl['edited_records']}/{report['records']} ({_percent(hitl['record_edit_rate'])})",
            f"- Edited fields: {hitl['edited_fields']}",
            f"- Field counts: `{json.dumps(hitl['field_counts'], ensure_ascii=False, sort_keys=True)}`",
            "",
            "## Largest RAG text-similarity changes",
            "",
            "### Gains",
            "",
        ]
    )
    for case in report["rag_cases"]["largest_gains"]:
        lines.append(
            f"- `{case['id']}` ({case['platform']}): {case['mean_text_similarity_change']:+.3f} — "
            f"{case['discussion_title']}"
        )
    lines.extend(["", "### Regressions", ""])
    for case in report["rag_cases"]["largest_regressions"]:
        lines.append(
            f"- `{case['id']}` ({case['platform']}): {case['mean_text_similarity_change']:+.3f} — "
            f"{case['discussion_title']}"
        )

    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {limitation}" for limitation in report["limitations"])
    lines.extend(
        [
            "",
            "## Reproduce",
            "",
            "```bash",
            "PYTHONPATH=src .venv/bin/python scripts/report_phase3_experiment.py",
            "PYTHONPATH=src .venv/bin/python -m pytest tests/unit/test_phase3_reporting.py -q",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def write_phase3_report(
    report: dict[str, Any],
    json_path: Path,
    markdown_path: Path,
) -> None:
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_phase3_markdown(report), encoding="utf-8")
