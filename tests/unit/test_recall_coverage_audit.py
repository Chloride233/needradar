from __future__ import annotations

import csv
import io

import pytest

from scripts.run_recall_coverage_audit import (
    NOISE_DUPLICATE_RATE_THRESHOLD,
    annotation_bytes,
    build_audit_pool,
    build_report,
    classify_query,
    content_sha256,
    deduplicate_record,
    normalize_content,
)


def _candidate(document_id: str, rank: int, text: str) -> dict:
    return {
        "blind_document_id": f"source-{document_id}",
        "document_id": document_id,
        "original_rank": rank,
        "original_score": 1 / rank,
        "source_metadata": {"platform": "github", "title": f"Title {document_id}"},
        "text": text,
    }


def _record(query_id: str, candidates: list[dict]) -> dict:
    return {
        "query_id": query_id,
        "query": f"Query {query_id}",
        "split": "test",
        "query_metadata": {"platform": "github"},
        "candidates": candidates,
    }


def test_normalize_content_is_stable_for_exact_display_variants():
    assert normalize_content("ＡI  Tool\n") == normalize_content("ai tool")
    assert content_sha256("Tom &amp; Jerry") == content_sha256("tom & jerry")


def test_deduplicate_record_retains_duplicate_identity_and_top3_membership():
    record = _record(
        "q1",
        [
            _candidate("a", 1, "Same text"),
            _candidate("b", 2, " same  TEXT "),
            _candidate("c", 3, "Different"),
            _candidate("d", 4, "Another"),
            _candidate("e", 5, "Last"),
        ],
    )

    result = deduplicate_record(record, {"b"})

    assert result["source_candidate_count"] == 5
    assert result["deduplicated_candidate_count"] == 4
    assert result["duplicate_positions"] == 1
    assert result["duplicate_rate"] == pytest.approx(NOISE_DUPLICATE_RATE_THRESHOLD)
    assert result["noise_contributor"] is True
    duplicate = result["candidates"][0]
    assert duplicate["duplicate_document_ids"] == ["a", "b"]
    assert duplicate["duplicate_original_ranks"] == [1, 2]
    assert duplicate["in_original_top3_union"] is True


def test_build_audit_pool_requires_exact_frozen_cohort():
    with pytest.raises(ValueError, match="exactly 12"):
        build_audit_pool([], ["q1"], [])


def test_build_audit_pool_is_sorted_and_has_unique_blind_ids():
    query_ids = [f"q{index:02d}" for index in range(12)]
    snapshot = [_record(query_id, [_candidate(f"{query_id}-a", 1, query_id)]) for query_id in reversed(query_ids)]
    pilot = [_record(query_id, [_candidate(f"{query_id}-a", 1, query_id)]) for query_id in query_ids]

    result = build_audit_pool(snapshot, query_ids, pilot)

    assert [record["query_id"] for record in result] == sorted(query_ids)
    blind_ids = [candidate["blind_document_id"] for record in result for candidate in record["candidates"]]
    assert len(blind_ids) == len(set(blind_ids)) == 12


def test_annotation_bytes_uses_review_contract_and_hides_ranks():
    pool = [deduplicate_record(_record("q1", [_candidate("a", 1, "Text")]), {"a"})]

    raw = annotation_bytes(pool)
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))

    assert b"\r\n" not in raw
    assert len(rows) == 1
    assert rows[0]["relevance_grade"] == ""
    assert rows[0]["notes"] == ""
    assert "original_rank" not in rows[0]
    assert "original_score" not in rows[0]


def test_classify_query_distinguishes_rank_coverage_noise_and_conflict():
    record = deduplicate_record(
        _record(
            "q1",
            [
                _candidate("a", 1, "Duplicate"),
                _candidate("b", 2, "duplicate"),
                _candidate("c", 3, "Relevant"),
                _candidate("d", 4, "Other"),
                _candidate("e", 5, "Last"),
            ],
        ),
        {"a", "b"},
    )
    labels = {candidate["blind_document_id"]: 0 for candidate in record["candidates"]}
    relevant_id = next(candidate["blind_document_id"] for candidate in record["candidates"] if candidate["document_id"] == "c")
    labels[relevant_id] = 2

    ranked = classify_query(record, labels)
    assert ranked["category"] == "rank_failure"
    assert ranked["noise_contributor"] is True

    labels[relevant_id] = 0
    assert classify_query(record, labels)["category"] == "coverage_failure"

    top3_id = next(candidate["blind_document_id"] for candidate in record["candidates"] if candidate["document_id"] == "a")
    labels[top3_id] = 1
    assert classify_query(record, labels)["category"] == "unresolved"


def test_build_report_requires_exact_labels_and_aggregates_categories():
    rank_record = deduplicate_record(_record("q1", [_candidate("a", 1, "A"), _candidate("b", 2, "B")]), {"a"})
    coverage_record = deduplicate_record(_record("q2", [_candidate("c", 1, "C")]), {"c"})
    labels = {
        rank_record["candidates"][0]["blind_document_id"]: 0,
        rank_record["candidates"][1]["blind_document_id"]: 2,
        coverage_record["candidates"][0]["blind_document_id"]: 0,
    }

    report = build_report([rank_record, coverage_record], labels, {"review_method": "single_expert_blind_test_retest"})

    assert report["summary"]["classification_counts"] == {"coverage_failure": 1, "rank_failure": 1}
    assert report["summary"]["query_count"] == 2

    with pytest.raises(ValueError, match="exactly cover"):
        build_report([rank_record, coverage_record], {"unexpected": 0}, {})
