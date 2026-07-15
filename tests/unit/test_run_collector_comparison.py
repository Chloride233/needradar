from __future__ import annotations

import pytest

import scripts.run_collector_comparison as comparison
from scripts.run_collector_comparison import interleaved_specs, parse_time_output, startup_specs


def test_parse_time_output_uses_macos_process_metrics():
    result = parse_time_output(
        "        1.23 real         0.45 user         0.06 sys\n             1234567  maximum resident set size\n"
    )
    assert result == {
        "process_wall_seconds": 1.23,
        "user_cpu_seconds": 0.45,
        "system_cpu_seconds": 0.06,
        "peak_rss_bytes": 1234567,
    }


def test_formal_order_is_seeded_pairwise_and_not_always_python_first():
    manifest = {
        "seed": 20260715,
        "scenarios": ["normal", "retry_10pct", "duplicate_10pct"],
        "formal": {"concurrency": [1, 4], "warmup_runs": 1, "measurement_runs": 1},
    }
    first = interleaved_specs(manifest, formal=True)
    second = interleaved_specs(manifest, formal=True)
    assert first == second
    pairs = [first[index : index + 2] for index in range(0, len(first), 2)]
    assert all({pair[0][0], pair[1][0]} == {"python", "go"} for pair in pairs)
    assert {pair[0][0] for pair in pairs} == {"python", "go"}
    assert all(pair[0][1:] == pair[1][1:] for pair in pairs)


def test_startup_order_is_seeded_and_pairwise():
    manifest = {"seed": 20260715, "startup": {"measurement_runs": 5}}
    specs = startup_specs(manifest)
    assert specs == startup_specs(manifest)
    pairs = [specs[index : index + 2] for index in range(0, len(specs), 2)]
    assert all({pair[0][0], pair[1][0]} == {"python", "go"} for pair in pairs)
    assert all(pair[0][1] == pair[1][1] for pair in pairs)


def test_prepare_captures_git_state_before_writing_artifacts(monkeypatch, tmp_path):
    workload_path = tmp_path / "workload.json"
    manifest_path = tmp_path / "manifest.json"
    go_binary = tmp_path / "collector-bench"
    clean_state = {"commit": "abc123", "dirty": False, "status_sha256": "status", "status": []}

    def capture_git_state():
        assert not workload_path.exists()
        return clean_state

    monkeypatch.setattr(comparison, "ROOT", tmp_path)
    monkeypatch.setattr(comparison, "EVALUATION", tmp_path)
    monkeypatch.setattr(comparison, "WORKLOAD_PATH", workload_path)
    monkeypatch.setattr(comparison, "MANIFEST_PATH", manifest_path)
    monkeypatch.setattr(comparison, "GO_BINARY", go_binary)
    monkeypatch.setattr(comparison, "SOURCE_PATHS", {})
    monkeypatch.setattr(comparison, "git_state", capture_git_state)
    monkeypatch.setattr(comparison, "build_workload", lambda **_kwargs: {"tasks": []})
    monkeypatch.setattr(comparison, "build_go_binary", lambda: go_binary.write_bytes(b"go"))
    monkeypatch.setattr(comparison, "environment", lambda: {})
    monkeypatch.setattr(comparison, "load_snapshot", lambda: {"known_high_load": False})

    manifest = comparison.prepare()

    assert manifest["experiment_id"] == "needradar-collector-scheduler-v3-20260715"
    assert manifest["runner_git"] == clean_state


def test_load_snapshot_rejects_unavailable_and_generic_high_load(monkeypatch):
    monkeypatch.setattr(comparison, "command_output", lambda *_args, **_kwargs: "")
    with pytest.raises(RuntimeError, match="load check unavailable"):
        comparison.load_snapshot()

    monkeypatch.setattr(
        comparison,
        "command_output",
        lambda *_args, **_kwargs: "123 45.0 1.0 /Applications/unrelated-heavy-process",
    )
    snapshot = comparison.load_snapshot()
    assert snapshot["known_high_load"] is True
    assert snapshot["suspicious"][0]["pid"] == 123

    monkeypatch.setattr(
        comparison,
        "command_output",
        lambda *_args, **_kwargs: "467 90.0 1.0 /System/Library/PrivateFrameworks/SkyLight/WindowServer",
    )
    snapshot = comparison.load_snapshot()
    assert snapshot["known_high_load"] is False
    assert snapshot["top_processes"][0]["system_process"] is True
