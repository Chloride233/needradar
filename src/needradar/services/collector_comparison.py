from __future__ import annotations

import hashlib
import json
import math
import statistics
from pathlib import Path
from typing import Any

from needradar.schemas.schemas import RawDiscussionItem

SCENARIOS = ("normal", "retry_10pct", "duplicate_10pct")
IMPLEMENTATIONS = ("python", "go")
COUNT_FIELDS = (
    "completed_tasks",
    "failed_tasks",
    "retry_attempts",
    "duplicate_count",
    "unique_result_count",
)
METRICS = (
    "wall_seconds",
    "throughput_tasks_per_second",
    "p50_latency_ms",
    "p95_latency_ms",
    "p99_latency_ms",
    "user_cpu_seconds",
    "system_cpu_seconds",
    "peak_rss_bytes",
)
PROCESS_METRICS = ("process_wall_seconds", "startup_overhead_seconds")
STARTUP_METRICS = ("wall_seconds", "user_cpu_seconds", "system_cpu_seconds", "peak_rss_bytes")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def build_workload(task_count: int = 1000, seed: int = 20260715, items_per_task: int = 10) -> dict:
    if task_count < 1 or items_per_task < 2:
        raise ValueError("task_count must be positive and items_per_task must be at least two")
    tasks = [
        {"id": task_id, "submission_index": task_id - 1, "retry_first": task_id % 10 == 0}
        for task_id in range(1, task_count + 1)
    ]
    return {
        "schema_version": 1,
        "seed": seed,
        "task_count": task_count,
        "items_per_task": items_per_task,
        "payload": {
            "source_url_template": "https://fake.test/task-{task_id:06d}/item-{item_index:02d}",
            "title_template": "NeedRadar task {task_id:06d} item {item_index:02d}",
            "content_template": "deterministic collector payload task {task_id:06d} item {item_index:02d}",
        },
        "tasks": tasks,
    }


def validate_workload(workload: dict) -> None:
    if workload.get("schema_version") != 1:
        raise ValueError("unsupported workload schema")
    tasks = workload.get("tasks", [])
    if len(tasks) != workload.get("task_count"):
        raise ValueError("workload task count mismatch")
    expected_ids = list(range(1, len(tasks) + 1))
    if [task.get("id") for task in tasks] != expected_ids:
        raise ValueError("workload task IDs must be contiguous and ordered")
    if [task.get("submission_index") for task in tasks] != list(range(len(tasks))):
        raise ValueError("workload submission order mismatch")
    if workload.get("items_per_task", 0) < 2:
        raise ValueError("workload items_per_task must be at least two")
    if [task["id"] for task in tasks if task.get("retry_first")] != list(range(10, len(tasks) + 1, 10)):
        raise ValueError("workload retry distribution mismatch")
    payload = workload.get("payload", {})
    required_templates = {"source_url_template", "title_template", "content_template"}
    if set(payload) != required_templates:
        raise ValueError("workload payload templates mismatch")


def render_items(workload: dict, task: dict, scenario: str) -> list[RawDiscussionItem]:
    if scenario not in SCENARIOS:
        raise ValueError(f"unsupported scenario: {scenario}")
    payload = workload["payload"]
    values: list[RawDiscussionItem] = []
    for index in range(workload["items_per_task"]):
        content_index = 0 if scenario == "duplicate_10pct" and index == workload["items_per_task"] - 1 else index
        values.append(
            RawDiscussionItem(
                platform="benchmark",
                source_url=payload["source_url_template"].format(task_id=task["id"], item_index=index),
                title=payload["title_template"].format(task_id=task["id"], item_index=content_index),
                content=payload["content_template"].format(task_id=task["id"], item_index=content_index),
                author="benchmark",
                tags=["collector-comparison"],
            )
        )
    return values


def expected_counts(workload: dict, scenario: str, task_count: int) -> dict[str, int]:
    if scenario not in SCENARIOS:
        raise ValueError(f"unsupported scenario: {scenario}")
    if not 1 <= task_count <= workload["task_count"]:
        raise ValueError("task_count is outside the frozen workload")
    tasks = workload["tasks"][:task_count]
    retries = sum(bool(task["retry_first"]) for task in tasks) if scenario == "retry_10pct" else 0
    duplicates = task_count if scenario == "duplicate_10pct" else 0
    return {
        "completed_tasks": task_count,
        "failed_tasks": 0,
        "retry_attempts": retries,
        "duplicate_count": duplicates,
        "unique_result_count": task_count * workload["items_per_task"] - duplicates,
    }


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def validate_result(workload: dict, result: dict, *, task_count: int) -> None:
    if result.get("implementation") not in IMPLEMENTATIONS:
        raise ValueError("unknown benchmark implementation")
    if result.get("scenario") not in SCENARIOS:
        raise ValueError("unknown benchmark scenario")
    if result.get("task_count") != task_count:
        raise ValueError("runner task count mismatch")
    if not isinstance(result.get("concurrency"), int) or result["concurrency"] < 1:
        raise ValueError("runner concurrency must be positive")
    expected = expected_counts(workload, result["scenario"], task_count)
    actual = {field: result.get(field) for field in COUNT_FIELDS}
    if actual != expected:
        raise ValueError(f"functional result mismatch: {actual} != {expected}")
    runner_metrics = METRICS[:5]
    for metric in runner_metrics:
        value = result.get(metric)
        if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError(f"invalid runner metric: {metric}")


def validate_records(manifest: dict, manifest_sha256: str, workload: dict, records: list[dict]) -> None:
    expected_keys = set()
    for scenario in manifest["scenarios"]:
        for concurrency in manifest["formal"]["concurrency"]:
            for implementation in IMPLEMENTATIONS:
                expected_keys.update(
                    (implementation, scenario, concurrency, "warmup", iteration)
                    for iteration in range(1, manifest["formal"]["warmup_runs"] + 1)
                )
                expected_keys.update(
                    (implementation, scenario, concurrency, "measured", iteration)
                    for iteration in range(1, manifest["formal"]["measurement_runs"] + 1)
                )
    if [record.get("order") for record in records] != list(range(1, len(records) + 1)):
        raise ValueError("run record order must be contiguous")
    semantics = {
        "fake_latency_ms": manifest["rules"]["fake_io_ms_per_attempt"],
        "retry_backoff_ms": manifest["rules"]["retry_backoff_ms"],
        "max_attempts": manifest["rules"]["max_attempts"],
        "items_per_task": workload["items_per_task"],
    }
    seen = set()
    for record in records:
        key = (
            record.get("implementation"),
            record.get("scenario"),
            record.get("concurrency"),
            record.get("phase"),
            record.get("iteration"),
        )
        if key in seen:
            raise ValueError(f"duplicate run record: {key}")
        seen.add(key)
        if record.get("manifest_sha256") != manifest_sha256:
            raise ValueError("run record manifest hash mismatch")
        if record.get("workload_sha256") != manifest["artifacts"]["workload_sha256"]:
            raise ValueError("run record workload hash mismatch")
        if record.get("environment") != manifest["environment"]:
            raise ValueError("run record environment mismatch")
        if record.get("runner_commit") != manifest["runner_git"]["commit"]:
            raise ValueError("run record commit mismatch")
        if record.get("workspace_status_sha256") != manifest["runner_git"]["status_sha256"]:
            raise ValueError("run record workspace status mismatch")
        if record.get("formal_load_check", {}).get("known_high_load") is not False:
            raise ValueError("run record has missing or polluted load check")
        for field, expected_value in semantics.items():
            if record.get(field) != expected_value:
                raise ValueError(f"run record frozen semantic mismatch: {field}")
        validate_result(workload, record, task_count=manifest["formal"]["task_count"])
        for metric in (*METRICS, *PROCESS_METRICS):
            value = record.get(metric)
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError(f"invalid measured metric for {key}: {metric}")
    missing = expected_keys - seen
    extra = seen - expected_keys
    if missing or extra:
        raise ValueError(f"run matrix mismatch: missing={len(missing)} extra={len(extra)}")


def validate_startup_records(manifest: dict, manifest_sha256: str, records: list[dict]) -> None:
    expected = {
        (implementation, iteration)
        for implementation in IMPLEMENTATIONS
        for iteration in range(1, manifest["startup"]["measurement_runs"] + 1)
    }
    if [record.get("order") for record in records] != list(range(1, len(records) + 1)):
        raise ValueError("startup record order must be contiguous")
    seen = set()
    for record in records:
        key = (record.get("implementation"), record.get("iteration"))
        if key in seen:
            raise ValueError(f"duplicate startup record: {key}")
        seen.add(key)
        if record.get("manifest_sha256") != manifest_sha256:
            raise ValueError("startup record manifest hash mismatch")
        if record.get("probe") != manifest["startup"]["probe"]:
            raise ValueError("startup probe mismatch")
        if record.get("environment") != manifest["environment"]:
            raise ValueError("startup record environment mismatch")
        if record.get("runner_commit") != manifest["runner_git"]["commit"]:
            raise ValueError("startup record commit mismatch")
        if record.get("workspace_status_sha256") != manifest["runner_git"]["status_sha256"]:
            raise ValueError("startup record workspace status mismatch")
        if record.get("formal_load_check", {}).get("known_high_load") is not False:
            raise ValueError("startup record has missing or polluted load check")
        for metric in ("process_wall_seconds", *STARTUP_METRICS):
            value = record.get(metric)
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError(f"invalid startup metric for {key}: {metric}")
    if seen != expected:
        raise ValueError(f"startup run matrix mismatch: missing={len(expected - seen)} extra={len(seen - expected)}")


def validate_report_provenance(
    report: dict,
    manifest_sha256: str,
    runs_sha256: str,
    startup_runs_sha256: str,
) -> None:
    if report.get("manifest_sha256") != manifest_sha256:
        raise ValueError("existing report manifest hash mismatch")
    if report.get("runs_sha256") != runs_sha256:
        raise ValueError("existing report runs hash mismatch")
    if report.get("startup_runs_sha256") != startup_runs_sha256:
        raise ValueError("existing report startup runs hash mismatch")


def metric_summary(values: list[float]) -> dict[str, float]:
    median = statistics.median(values)
    return {
        "median": median,
        "min": min(values),
        "max": max(values),
        "min_max_spread_percent": (max(values) - min(values)) / median * 100 if median else 0.0,
    }


def percentage_change(go_value: float, python_value: float, *, reduction: bool = False) -> float:
    if python_value == 0:
        raise ValueError("cannot compare against a zero Python metric")
    difference = python_value - go_value if reduction else go_value - python_value
    return difference / python_value * 100


def build_report(
    manifest: dict,
    manifest_sha256: str,
    workload: dict,
    records: list[dict],
    runs_sha256: str,
    startup_records: list[dict],
    startup_runs_sha256: str,
) -> dict:
    validate_records(manifest, manifest_sha256, workload, records)
    validate_startup_records(manifest, manifest_sha256, startup_records)
    measured = [record for record in records if record["phase"] == "measured"]
    combinations = []
    for scenario in manifest["scenarios"]:
        for concurrency in manifest["formal"]["concurrency"]:
            summaries = {}
            for implementation in IMPLEMENTATIONS:
                selected = [
                    record
                    for record in measured
                    if record["implementation"] == implementation
                    and record["scenario"] == scenario
                    and record["concurrency"] == concurrency
                ]
                summaries[implementation] = {
                    metric: metric_summary([float(record[metric]) for record in selected]) for metric in METRICS
                }
            python = summaries["python"]
            go = summaries["go"]
            comparisons = {
                "throughput_increase_percent": percentage_change(
                    go["throughput_tasks_per_second"]["median"],
                    python["throughput_tasks_per_second"]["median"],
                ),
                "p50_latency_reduction_percent": percentage_change(
                    go["p50_latency_ms"]["median"], python["p50_latency_ms"]["median"], reduction=True
                ),
                "p95_latency_reduction_percent": percentage_change(
                    go["p95_latency_ms"]["median"], python["p95_latency_ms"]["median"], reduction=True
                ),
                "p99_latency_reduction_percent": percentage_change(
                    go["p99_latency_ms"]["median"], python["p99_latency_ms"]["median"], reduction=True
                ),
                "peak_rss_reduction_percent": percentage_change(
                    go["peak_rss_bytes"]["median"], python["peak_rss_bytes"]["median"], reduction=True
                ),
            }
            combinations.append(
                {"scenario": scenario, "concurrency": concurrency, "metrics": summaries, "comparison": comparisons}
            )
    comparison_keys = (
        "throughput_increase_percent",
        "p50_latency_reduction_percent",
        "p95_latency_reduction_percent",
        "p99_latency_reduction_percent",
        "peak_rss_reduction_percent",
    )
    comparison_ranges = {
        key: {
            "min": min(combination["comparison"][key] for combination in combinations),
            "max": max(combination["comparison"][key] for combination in combinations),
        }
        for key in comparison_keys
    }
    negative_cases = [
        {
            "scenario": combination["scenario"],
            "concurrency": combination["concurrency"],
            "metric": key,
            "percent": combination["comparison"][key],
        }
        for combination in combinations
        for key in comparison_keys
        if combination["comparison"][key] < 0
    ]
    variation = {
        metric: {
            implementation: max(
                (
                    {
                        "scenario": combination["scenario"],
                        "concurrency": combination["concurrency"],
                        "min_max_spread_percent": combination["metrics"][implementation][metric][
                            "min_max_spread_percent"
                        ],
                    }
                    for combination in combinations
                ),
                key=lambda value: value["min_max_spread_percent"],
            )
            for implementation in IMPLEMENTATIONS
        }
        for metric in ("throughput_tasks_per_second", "p95_latency_ms", "peak_rss_bytes")
    }
    startup = {
        implementation: {
            metric: metric_summary(
                [float(record[metric]) for record in startup_records if record["implementation"] == implementation]
            )
            for metric in STARTUP_METRICS
        }
        for implementation in IMPLEMENTATIONS
    }
    return {
        "schema_version": 2,
        "experiment_id": manifest["experiment_id"],
        "manifest_sha256": manifest_sha256,
        "runs_sha256": runs_sha256,
        "startup_runs_sha256": startup_runs_sha256,
        "functional_equivalence": True,
        "measurement_runs_per_combination": manifest["formal"]["measurement_runs"],
        "task_count": manifest["formal"]["task_count"],
        "combinations": combinations,
        "comparison_ranges": comparison_ranges,
        "negative_cases": negative_cases,
        "variation": variation,
        "startup": startup,
        "limitations": manifest["limitations"],
    }


def render_report_markdown(report: dict, manifest: dict) -> str:
    lines = [
        "# Python vs Go collector scheduler comparison",
        "",
        f"Experiment: `{report['experiment_id']}`",
        f"Manifest SHA-256: `{report['manifest_sha256']}`",
        f"Runs SHA-256: `{report['runs_sha256']}`",
        f"Startup runs SHA-256: `{report['startup_runs_sha256']}`",
        "",
        "All combinations passed exact completed, failed, retry, duplicate, and unique-result parity.",
        "Medians below use five measured runs; JSON retains min and max for every metric.",
        "",
        "| Scenario | C | Impl | Tasks/s | P50 ms | P95 ms | P99 ms | User CPU s | Sys CPU s | Peak RSS MiB |",
        "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for combination in report["combinations"]:
        for implementation in IMPLEMENTATIONS:
            metrics = combination["metrics"][implementation]
            lines.append(
                f"| {combination['scenario']} | {combination['concurrency']} | {implementation} | "
                f"{metrics['throughput_tasks_per_second']['median']:.2f} | "
                f"{metrics['p50_latency_ms']['median']:.2f} | {metrics['p95_latency_ms']['median']:.2f} | "
                f"{metrics['p99_latency_ms']['median']:.2f} | {metrics['user_cpu_seconds']['median']:.3f} | "
                f"{metrics['system_cpu_seconds']['median']:.3f} | "
                f"{metrics['peak_rss_bytes']['median'] / 1024 / 1024:.2f} |"
            )
    lines.extend(
        [
            "",
            "## Go relative to Python",
            "",
            "| Scenario | C | Throughput change | P50 reduction | P95 reduction | P99 reduction | RSS reduction |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for combination in report["combinations"]:
        comparison = combination["comparison"]
        lines.append(
            f"| {combination['scenario']} | {combination['concurrency']} | "
            f"{comparison['throughput_increase_percent']:.2f}% | "
            f"{comparison['p50_latency_reduction_percent']:.2f}% | "
            f"{comparison['p95_latency_reduction_percent']:.2f}% | "
            f"{comparison['p99_latency_reduction_percent']:.2f}% | "
            f"{comparison['peak_rss_reduction_percent']:.2f}% |"
        )
    lines.extend(
        [
            "",
            "## Independent process startup",
            "",
            "This is a separate five-run runner help-path probe. It includes runtime startup, imports, flag parsing, output, and exit; it is not included in steady-state task latency.",
            "",
            "| Impl | Wall median ms | Wall min ms | Wall max ms | User CPU s | Sys CPU s | Peak RSS MiB |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for implementation in IMPLEMENTATIONS:
        startup = report["startup"][implementation]
        lines.append(
            f"| {implementation} | {startup['wall_seconds']['median'] * 1000:.2f} | "
            f"{startup['wall_seconds']['min'] * 1000:.2f} | "
            f"{startup['wall_seconds']['max'] * 1000:.2f} | "
            f"{startup['user_cpu_seconds']['median']:.3f} | "
            f"{startup['system_cpu_seconds']['median']:.3f} | "
            f"{startup['peak_rss_bytes']['median'] / 1024 / 1024:.2f} |"
        )
    lines.extend(
        [
            "",
            "## Variation and negative cases",
            "",
            "Worst five-run min/max spread relative to the median:",
            "",
            "| Metric | Python | Go |",
            "| --- | ---: | ---: |",
        ]
    )
    for metric in ("throughput_tasks_per_second", "p95_latency_ms", "peak_rss_bytes"):
        python = report["variation"][metric]["python"]
        go = report["variation"][metric]["go"]
        lines.append(
            f"| {metric} | {python['min_max_spread_percent']:.2f}% "
            f"({python['scenario']}, C={python['concurrency']}) | "
            f"{go['min_max_spread_percent']:.2f}% ({go['scenario']}, C={go['concurrency']}) |"
        )
    lines.extend(["", f"Negative primary comparison cases: {len(report['negative_cases'])}."])
    for case in report["negative_cases"]:
        lines.append(f"- {case['scenario']} C={case['concurrency']} {case['metric']}: {case['percent']:.2f}%")
    lines.extend(
        [
            "",
            "## Scope and interpretation",
            "",
            "- Unit: in-process collection task scheduling with deterministic fake I/O, request retry, and task-local fingerprint deduplication.",
            "- Throughput and latency exclude process startup; CPU and peak RSS cover each independently measured process.",
            "- Task latency starts at the shared queue release and therefore includes equivalent queue waiting.",
            "- Positive reduction means Go used less latency or RSS; negative values are regressions.",
            "- Process wall minus internal wall is retained per raw record as startup/import/exit overhead, not task latency.",
            "",
            "## Resume-safe evidence",
            "",
            f"On this frozen local {report['task_count']}-task, 5 ms fake-I/O scheduler slice, Go throughput "
            f"changed by {report['comparison_ranges']['throughput_increase_percent']['min']:.2f}% to "
            f"{report['comparison_ranges']['throughput_increase_percent']['max']:.2f}%, P95 latency changed "
            f"by {report['comparison_ranges']['p95_latency_reduction_percent']['min']:.2f}% to "
            f"{report['comparison_ranges']['p95_latency_reduction_percent']['max']:.2f}%, and process peak "
            f"RSS changed by {report['comparison_ranges']['peak_rss_reduction_percent']['min']:.2f}% to "
            f"{report['comparison_ranges']['peak_rss_reduction_percent']['max']:.2f}% relative to Python. "
            "Any resume claim must keep the local deterministic, task-count, fake-latency, and concurrency qualifiers.",
            "",
            "## Claims not supported",
            "",
            "This experiment does not establish real-platform throughput, production SLA, whole-pipeline speedup, "
            "SQLite/Vault/LLM performance, or long-running service stability.",
            "",
            "## Environment",
            "",
            f"- OS: {manifest['environment']['os']}",
            f"- Architecture: {manifest['environment']['architecture']}",
            f"- CPU: {manifest['environment']['cpu']}",
            f"- Python: {manifest['environment']['python_version']}",
            f"- Go: {manifest['environment']['go_version']}",
            f"- GOMAXPROCS: {manifest['environment']['gomaxprocs']}",
        ]
    )
    return "\n".join(lines) + "\n"
