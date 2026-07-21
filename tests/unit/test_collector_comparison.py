from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from needradar.services.collector_comparison import (
    SCENARIOS,
    build_report,
    build_workload,
    expected_counts,
    load_jsonl,
    pretty_json,
    render_items,
    render_report_markdown,
    sha256_file,
    validate_records,
    validate_report_provenance,
    validate_startup_records,
    validate_workload,
)


def make_manifest() -> dict:
    return {
        "experiment_id": "test",
        "scenarios": list(SCENARIOS),
        "formal": {"task_count": 20, "concurrency": [1], "warmup_runs": 1, "measurement_runs": 2},
        "startup": {"probe": "runner_help_path", "measurement_runs": 2},
        "rules": {"fake_io_ms_per_attempt": 5, "retry_backoff_ms": 1, "max_attempts": 3},
        "artifacts": {"workload_sha256": "workload"},
        "environment": {
            "os": "test-os",
            "architecture": "test-arch",
            "cpu": "test-cpu",
            "logical_cpus": 4,
            "python_version": "3.test",
            "go_version": "go-test",
            "gomaxprocs": 4,
        },
        "runner_git": {"commit": "commit", "status_sha256": "status"},
        "limitations": ["test only"],
    }


def make_records(manifest: dict, workload: dict, manifest_sha256: str = "manifest") -> list[dict]:
    records = []
    for scenario in manifest["scenarios"]:
        counts = expected_counts(workload, scenario, manifest["formal"]["task_count"])
        for implementation in ("python", "go"):
            for phase, runs in (
                ("warmup", manifest["formal"]["warmup_runs"]),
                ("measured", manifest["formal"]["measurement_runs"]),
            ):
                for iteration in range(1, runs + 1):
                    records.append(
                        {
                            "order": len(records) + 1,
                            "implementation": implementation,
                            "scenario": scenario,
                            "task_count": manifest["formal"]["task_count"],
                            "concurrency": 1,
                            "phase": phase,
                            "iteration": iteration,
                            "manifest_sha256": manifest_sha256,
                            "workload_sha256": "workload",
                            "environment": manifest["environment"],
                            "runner_commit": "commit",
                            "workspace_status_sha256": "status",
                            "formal_load_check": {"known_high_load": False},
                            "fake_latency_ms": 5,
                            "retry_backoff_ms": 1,
                            "max_attempts": 3,
                            "items_per_task": workload["items_per_task"],
                            "wall_seconds": 1.0,
                            "process_wall_seconds": 1.1,
                            "startup_overhead_seconds": 0.1,
                            "throughput_tasks_per_second": 20.0 if implementation == "python" else 25.0,
                            "p50_latency_ms": 10.0,
                            "p95_latency_ms": 20.0,
                            "p99_latency_ms": 25.0,
                            "user_cpu_seconds": 0.2,
                            "system_cpu_seconds": 0.1,
                            "peak_rss_bytes": 1000 if implementation == "python" else 800,
                            **counts,
                        }
                    )
    return records


def make_startup_records(manifest: dict, manifest_sha256: str = "manifest") -> list[dict]:
    records = []
    for iteration in range(1, manifest["startup"]["measurement_runs"] + 1):
        for implementation in ("python", "go"):
            records.append(
                {
                    "order": len(records) + 1,
                    "implementation": implementation,
                    "iteration": iteration,
                    "probe": "runner_help_path",
                    "manifest_sha256": manifest_sha256,
                    "environment": manifest["environment"],
                    "runner_commit": "commit",
                    "workspace_status_sha256": "status",
                    "formal_load_check": {"known_high_load": False},
                    "wall_seconds": 0.2 if implementation == "python" else 0.01,
                    "process_wall_seconds": 0.2 if implementation == "python" else 0.01,
                    "user_cpu_seconds": 0.1,
                    "system_cpu_seconds": 0.01,
                    "peak_rss_bytes": 1000 if implementation == "python" else 500,
                }
            )
    return records


def test_workload_freezes_order_retry_distribution_and_duplicate_payload():
    workload = build_workload()
    validate_workload(workload)
    assert [task["id"] for task in workload["tasks"][:3]] == [1, 2, 3]
    assert sum(task["retry_first"] for task in workload["tasks"]) == 100

    items = render_items(workload, workload["tasks"][0], "duplicate_10pct")
    assert items[0].source_url != items[-1].source_url
    assert (items[0].title, items[0].content) == (items[-1].title, items[-1].content)
    assert items[0].model_dump() == {
        "platform": "benchmark",
        "source_url": "https://fake.test/task-000001/item-00",
        "title": "NeedRadar task 000001 item 00",
        "content": "deterministic collector payload task 000001 item 00",
        "author": "benchmark",
        "tags": ["collector-comparison"],
    }
    assert items[-1].source_url == "https://fake.test/task-000001/item-09"
    assert expected_counts(workload, "duplicate_10pct", 200)["unique_result_count"] == 1800


def test_validate_records_rejects_missing_duplicate_and_functional_mismatch():
    manifest = make_manifest()
    workload = build_workload(task_count=20)
    records = make_records(manifest, workload)
    validate_records(manifest, "manifest", workload, records)

    with pytest.raises(ValueError, match="run matrix mismatch"):
        validate_records(manifest, "manifest", workload, records[:-1])
    with pytest.raises(ValueError, match="duplicate run record"):
        duplicate = copy.deepcopy(records[0])
        duplicate["order"] = len(records) + 1
        validate_records(manifest, "manifest", workload, records + [duplicate])
    changed = copy.deepcopy(records)
    changed[0]["retry_attempts"] += 1
    with pytest.raises(ValueError, match="functional result mismatch"):
        validate_records(manifest, "manifest", workload, changed)


def test_validate_records_rejects_changed_semantics_environment_and_load():
    manifest = make_manifest()
    workload = build_workload(task_count=20)
    records = make_records(manifest, workload)
    changed = copy.deepcopy(records)
    changed[0]["fake_latency_ms"] = 6
    with pytest.raises(ValueError, match="frozen semantic mismatch"):
        validate_records(manifest, "manifest", workload, changed)
    changed = copy.deepcopy(records)
    changed[0]["environment"]["go_version"] = "changed"
    with pytest.raises(ValueError, match="environment mismatch"):
        validate_records(manifest, "manifest", workload, changed)
    changed = copy.deepcopy(records)
    changed[0]["formal_load_check"]["known_high_load"] = True
    with pytest.raises(ValueError, match="polluted load check"):
        validate_records(manifest, "manifest", workload, changed)


def test_validate_records_and_report_provenance_reject_hash_tampering():
    manifest = make_manifest()
    workload = build_workload(task_count=20)
    records = make_records(manifest, workload)
    with pytest.raises(ValueError, match="manifest hash mismatch"):
        validate_records(manifest, "changed", workload, records)
    with pytest.raises(ValueError, match="runs hash mismatch"):
        validate_report_provenance(
            {
                "manifest_sha256": "manifest",
                "runs_sha256": "original",
                "startup_runs_sha256": "startup",
            },
            "manifest",
            "changed",
            "startup",
        )
    with pytest.raises(ValueError, match="startup runs hash mismatch"):
        validate_report_provenance(
            {
                "manifest_sha256": "manifest",
                "runs_sha256": "runs",
                "startup_runs_sha256": "original",
            },
            "manifest",
            "runs",
            "changed",
        )


def test_validate_startup_records_rejects_missing_duplicate_and_polluted_runs():
    manifest = make_manifest()
    records = make_startup_records(manifest)
    validate_startup_records(manifest, "manifest", records)
    with pytest.raises(ValueError, match="startup run matrix mismatch"):
        validate_startup_records(manifest, "manifest", records[:-1])
    duplicate = copy.deepcopy(records[0])
    duplicate["order"] = len(records) + 1
    with pytest.raises(ValueError, match="duplicate startup record"):
        validate_startup_records(manifest, "manifest", records + [duplicate])
    changed = copy.deepcopy(records)
    changed[0]["formal_load_check"]["known_high_load"] = True
    with pytest.raises(ValueError, match="polluted load check"):
        validate_startup_records(manifest, "manifest", changed)


def test_report_uses_measured_medians_and_directional_percentages():
    manifest = make_manifest()
    workload = build_workload(task_count=20)
    report = build_report(
        manifest,
        "manifest",
        workload,
        make_records(manifest, workload),
        "runs",
        make_startup_records(manifest),
        "startup-runs",
    )
    assert report["functional_equivalence"] is True
    assert len(report["combinations"]) == 3
    comparison = report["combinations"][0]["comparison"]
    assert comparison["throughput_increase_percent"] == pytest.approx(25.0)
    assert comparison["peak_rss_reduction_percent"] == pytest.approx(20.0)
    assert report["startup"]["python"]["wall_seconds"]["median"] == pytest.approx(0.2)
    assert report["negative_cases"] == []


def test_checked_in_collector_comparison_artifacts_exactly_rebuild():
    root = Path(__file__).resolve().parents[2]
    phase4 = root / "evaluation" / "phase4"
    manifest_path = phase4 / "collector-comparison-manifest.json"
    workload_path = phase4 / "collector-comparison-workload.json"
    runs_path = phase4 / "collector-comparison-runs.jsonl"
    startup_runs_path = phase4 / "collector-comparison-startup-runs.jsonl"
    report_path = phase4 / "collector-comparison.json"
    markdown_path = phase4 / "collector-comparison.md"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    workload = json.loads(workload_path.read_text(encoding="utf-8"))
    records = load_jsonl(runs_path)
    startup_records = load_jsonl(startup_runs_path)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    manifest_sha256 = sha256_file(manifest_path)
    runs_sha256 = sha256_file(runs_path)
    startup_runs_sha256 = sha256_file(startup_runs_path)

    validate_report_provenance(report, manifest_sha256, runs_sha256, startup_runs_sha256)
    rebuilt = build_report(
        manifest,
        manifest_sha256,
        workload,
        records,
        runs_sha256,
        startup_records,
        startup_runs_sha256,
    )
    assert pretty_json(rebuilt) == report_path.read_text(encoding="utf-8")
    assert render_report_markdown(rebuilt, manifest) == markdown_path.read_text(encoding="utf-8")
