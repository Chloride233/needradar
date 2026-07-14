from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from needradar.services.phase3_verifier_benchmark import (
    apply_naturalistic_adjudication,
    build_verifier_benchmark,
    validate_verifier_benchmark,
)


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_builds_balanced_gold_separated_benchmark_with_valid_offsets(tmp_path):
    input_path, gold_path, manifest_path = build_verifier_benchmark(
        Path("evaluation/phase3/rag-corpus.jsonl"),
        tmp_path,
    )
    inputs = _read_jsonl(input_path)
    gold = _read_jsonl(gold_path)
    gold_by_id = {record["id"]: record for record in gold}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert len(inputs) == len(gold) == 30
    assert Counter(record["platform"] for record in inputs) == {
        "github": 10,
        "stackoverflow": 10,
        "juejin": 10,
    }
    assert Counter(record["stratum"] for record in inputs) == {"controlled": 18, "naturalistic": 12}
    assert Counter(record["length_bucket"] for record in inputs) == {"short": 10, "medium": 10, "long": 10}
    assert sum(record["flagged"] for record in gold) == 15
    assert all("claims" not in record and "annotation_status" not in record for record in inputs)
    assert all(
        record["report_body"][claim["start"] : claim["end"]] == claim["quote"]
        for record in inputs
        for claim in gold_by_id[record["id"]]["claims"]
    )
    assert any(
        claim["start"] > 4000
        for record in inputs
        if record["length_bucket"] == "long"
        for claim in gold_by_id[record["id"]]["claims"]
    )
    assert manifest["pending_annotations"] == 12
    assert manifest["complete"] is False
    assert manifest["gold_fields_in_inputs"] is False
    assert manifest["author_fields_stored"] is False


def test_formal_validation_rejects_pending_naturalistic_annotations(tmp_path):
    input_path, gold_path, manifest_path = build_verifier_benchmark(
        Path("evaluation/phase3/rag-corpus.jsonl"),
        tmp_path,
    )

    with pytest.raises(ValueError, match="12 pending independent annotations"):
        validate_verifier_benchmark(input_path, gold_path, manifest_path, require_complete=True)


def test_applies_dual_agent_adjudication_and_completes_manifest(tmp_path):
    input_path, gold_path, manifest_path = build_verifier_benchmark(
        Path("evaluation/phase3/rag-corpus.jsonl"),
        tmp_path,
    )

    manifest = apply_naturalistic_adjudication(
        input_path,
        gold_path,
        manifest_path,
        Path("evaluation/phase3/verifier-naturalistic-adjudication.jsonl"),
    )
    gold = _read_jsonl(gold_path)

    assert manifest["complete"] is True
    assert manifest["pending_annotations"] == 0
    assert len(manifest["adjudication_sha256"]) == 64
    assert all(
        record["annotation_method"] == "dual_agent_blind_with_root_adjudication"
        for record in gold
        if record["stratum"] == "naturalistic"
    )


def test_validation_rejects_changed_input_hash(tmp_path):
    input_path, gold_path, manifest_path = build_verifier_benchmark(
        Path("evaluation/phase3/rag-corpus.jsonl"),
        tmp_path,
    )
    input_path.write_text(input_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="manifest hashes"):
        validate_verifier_benchmark(input_path, gold_path, manifest_path, require_complete=False)


def test_frozen_adjudicated_benchmark_hashes_remain_exact():
    manifest = validate_verifier_benchmark(
        Path("evaluation/phase3/verifier-benchmark.jsonl"),
        Path("evaluation/phase3/verifier-gold.jsonl"),
        Path("evaluation/phase3/verifier-benchmark-manifest.json"),
        require_complete=True,
    )

    assert manifest["source_corpus_sha256"] == "aae92eead080126322d41926faddbdfa94f19ceb36681b03b28f5171353026fb"
    assert manifest["input_sha256"] == "a7125166ccbe3f505f96feca289eb8a1ed4ae6abbcaaf7ee119dff2662d6eca9"
    assert manifest["gold_sha256"] == "acc1ce2066341c2ecf9ca0f7fa6b78afd078034fdd4cf635a327183a2b6bad92"
    assert manifest["adjudication_sha256"] == "dea66d8c491b140e2c6401b67c92e8aefad179b21e808337978be221d8569398"
    assert manifest["pending_annotations"] == 0
    assert manifest["complete"] is True
