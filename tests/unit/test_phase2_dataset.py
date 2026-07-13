import hashlib
import json
from collections import Counter
from pathlib import Path

from needradar.services.extraction_metrics import score_extractions


def test_phase2_sample_matches_manifest_and_strata():
    dataset_path = Path("evaluation/phase2/discussions.jsonl")
    manifest = json.loads(Path("evaluation/phase2/manifest.json").read_text(encoding="utf-8"))
    dataset_bytes = dataset_path.read_bytes()
    records = [json.loads(line) for line in dataset_bytes.splitlines()]

    assert len(records) == manifest["sample_size"] == 100
    assert Counter(record["platform"] for record in records) == manifest["platform_counts"]
    assert manifest["platform_counts"] == {"github": 34, "stackoverflow": 33, "juejin": 33}
    assert len({record["id"] for record in records}) == 100
    assert len({record["source_url"] for record in records}) == 100
    assert all("author" not in record for record in records)
    assert hashlib.sha256(dataset_bytes).hexdigest() == manifest["dataset_sha256"]


def test_phase2_frozen_predictions_reproduce_committed_metrics():
    phase2 = Path("evaluation/phase2")
    expected = json.loads((phase2 / "needradar_metrics.json").read_text(encoding="utf-8"))

    actual = score_extractions(
        phase2 / "annotations_adjudicated.jsonl",
        phase2 / "needradar_predictions.jsonl",
        phase2 / "discussions.jsonl",
    )

    assert actual == expected
