from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path


def test_phase3_corpus_is_frozen_held_out_and_gold_free():
    phase2_path = Path("evaluation/phase2/discussions.jsonl")
    corpus_path = Path("evaluation/phase3/rag-corpus.jsonl")
    manifest = json.loads(Path("evaluation/phase3/rag-corpus-manifest.json").read_text(encoding="utf-8"))
    phase2 = [json.loads(line) for line in phase2_path.read_text(encoding="utf-8").splitlines()]
    corpus = [json.loads(line) for line in corpus_path.read_text(encoding="utf-8").splitlines()]

    phase2_urls = {record["source_url"] for record in phase2}
    corpus_urls = {record["source_url"] for record in corpus}
    corpus_ids = {record["id"] for record in corpus}
    counts = Counter(record["platform"] for record in corpus)

    assert len(corpus) == len(corpus_urls) == len(corpus_ids) == 150
    assert counts == {"github": 50, "stackoverflow": 50, "juejin": 50}
    assert phase2_urls.isdisjoint(corpus_urls)
    assert all(record["title"].strip() and record["content"].strip() for record in corpus)
    assert all("author" not in record for record in corpus)
    assert all("requirement_present" not in record for record in corpus)
    assert manifest["phase2_url_overlap"] == 0
    assert manifest["gold_fields_stored"] is False
    assert manifest["source_dataset_sha256"] == hashlib.sha256(phase2_path.read_bytes()).hexdigest()
    assert manifest["dataset_sha256"] == hashlib.sha256(corpus_path.read_bytes()).hexdigest()
