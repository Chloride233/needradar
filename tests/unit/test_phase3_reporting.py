from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from needradar.services.phase3_reporting import build_phase3_report

ARTIFACT_SHA256 = {
    "no_rag/metrics.json": "0cce6f6925d50a07bd0174e54f630e998468c9309ddb4a7da7fe5b21499c3051",
    "no_rag/predictions.jsonl": "ae510a5ee2eac01504d3e33da2914232ea96cf95412bb97f9371c6ce1da04677",
    "no_rag/run.json": "43432c9e10423666072a7f315946b6b3cb322e0fa611e734aac23ad1ac102701",
    "rag/metrics.json": "831da3a59c138a0d5daac1f717ed2f198259f46be27b94b7328ad704def4719e",
    "rag/predictions.jsonl": "ad52d457069462fd30dd91cd92033867c26306d6d3fe457cfe030e968512931a",
    "rag/run.json": "252cd6937568801248c5368071b10777895ff4e0686ca061b7fcff9a446d2905",
    "rag_hitl/metrics.json": "107de3831d9c5c8ee8c66802d3c4bd998fa059baa84d0ce3cde516f95b52fc3d",
    "rag_hitl/predictions.jsonl": "27cc20250a45c4880ba08cfebe1b9344c7443676457fa0a5cec214a236dac7e5",
    "rag_hitl/run.json": "50d320210d1f6e16148097c732e198603199d6af4cc5e617952e9d705a83da14",
}


def _copy_full_run(tmp_path: Path) -> Path:
    run_root = tmp_path / "full-final"
    shutil.copytree(Path("evaluation/phase3/runs/full-final"), run_root)
    return run_root


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _build_report(run_root: Path):
    return build_phase3_report(
        run_root,
        Path("evaluation/phase2/discussions.jsonl"),
        Path("evaluation/phase2/annotations_adjudicated.jsonl"),
    )


def test_full_phase3_report_reproduces_quality_cost_and_cache_evidence():
    report = build_phase3_report(
        Path("evaluation/phase3/runs/full-final"),
        Path("evaluation/phase2/discussions.jsonl"),
        Path("evaluation/phase2/annotations_adjudicated.jsonl"),
    )

    assert report["records"] == 100
    assert report["configurations"]["no_rag"]["requirement_presence_accuracy"] == 0.49
    assert report["configurations"]["rag"]["requirement_presence_accuracy"] == 0.49
    assert report["rag_vs_no_rag"]["emotion_accuracy"]["absolute_change"] == pytest.approx(0.08510638297872347)
    assert report["rag_vs_no_rag"]["duplicate_rate"]["absolute_change"] == pytest.approx(0.01020408163265306)
    assert report["rag_vs_no_rag"]["cost_cny"]["relative_change"] == pytest.approx(0.2010454633456511)
    assert report["requirement_presence_transitions"] == {
        "improved": 0,
        "worsened": 0,
        "unchanged": 100,
    }
    assert report["hitl"]["edited_records"] == 97
    assert report["hitl"]["record_edit_rate"] == 0.97
    assert report["cache"]["actual_cost_cny"] == pytest.approx(0.393868)
    assert report["cache"]["cost_without_cache_cny"] == pytest.approx(1.106998496)
    assert report["cache"]["savings_rate"] == pytest.approx(0.6442018652932299)
    assert len(report["rag_cases"]["largest_gains"]) == 5
    assert len(report["rag_cases"]["largest_regressions"]) == 5


def test_full_phase3_artifacts_remain_byte_exact():
    root = Path("evaluation/phase3/runs/full-final")

    for relative_path, expected_hash in ARTIFACT_SHA256.items():
        assert hashlib.sha256((root / relative_path).read_bytes()).hexdigest() == expected_hash


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("schema_version", 999),
        ("model_id", "different-model"),
        ("provider_params", {"temperature": 0.9}),
        ("pricing", {"input_per_million": 999.0}),
        ("max_discussion_chars", 1234),
    ],
)
def test_report_rejects_mixed_cross_configuration_provenance(tmp_path, field, replacement):
    run_root = _copy_full_run(tmp_path)
    run_path = run_root / "rag" / "run.json"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    run[field] = replacement
    _write_json(run_path, run)

    with pytest.raises(ValueError, match="shared experiment provenance"):
        _build_report(run_root)


def test_report_rejects_mixed_rag_retriever_provenance(tmp_path):
    run_root = _copy_full_run(tmp_path)
    run_path = run_root / "rag_hitl" / "run.json"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    run["retriever_provenance"]["table_name"] = "different-table"
    _write_json(run_path, run)

    with pytest.raises(ValueError, match="RAG provenance"):
        _build_report(run_root)


def test_report_rejects_prediction_id_mismatch(tmp_path):
    run_root = _copy_full_run(tmp_path)
    prediction_path = run_root / "rag" / "predictions.jsonl"
    predictions = [json.loads(line) for line in prediction_path.read_text(encoding="utf-8").splitlines()]
    predictions[0]["id"] = "unexpected-id"
    prediction_path.write_text(
        "".join(json.dumps(prediction, ensure_ascii=False) + "\n" for prediction in predictions),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="prediction IDs"):
        _build_report(run_root)
