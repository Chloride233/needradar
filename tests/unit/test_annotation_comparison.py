import csv
import json

import pytest

from needradar.services.annotation_comparison import (
    apply_human_audit_decisions,
    compare_agent_annotations,
    merge_human_requirement_decisions,
    validate_agent_assisted_review,
    write_requirement_audit_sheet,
)
from needradar.services.annotation_workflow import LABEL_FIELDS


def _record(record_id, **changes):
    record = {
        "id": record_id,
        "requirement_present": "yes",
        "title": "CSV export",
        "description": "Export records as CSV",
        "pain_point": "Manual copying",
        "use_case": "Reporting",
        "sentiment": "moderate",
        "emotion": "neutral",
        "evidence_clarity": "clear",
    }
    record.update(changes)
    return record


def _write_jsonl(path, records):
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def test_compare_reports_field_agreement_and_writes_conflicts(tmp_path):
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    conflicts = tmp_path / "conflicts.jsonl"
    _write_jsonl(first, [_record("one"), _record("two")])
    _write_jsonl(
        second,
        [
            _record("two", title="Spreadsheet export", emotion="negative"),
            _record("one"),
        ],
    )

    report = compare_agent_annotations(first, second, conflicts)

    assert report["record_count"] == 2
    assert report["conflict_count"] == 1
    assert report["field_agreement"]["title"] == {"agreed": 1, "total": 2, "rate": 0.5}
    assert report["field_agreement"]["description"] == {"agreed": 2, "total": 2, "rate": 1.0}
    conflict = json.loads(conflicts.read_text(encoding="utf-8"))
    assert conflict["id"] == "two"
    assert conflict["disagreements"] == {
        "emotion": {"first": "neutral", "second": "negative"},
        "title": {"first": "CSV export", "second": "Spreadsheet export"},
    }
    assert conflict["first"]["title"] == "CSV export"
    assert conflict["second"]["title"] == "Spreadsheet export"


def test_compare_rejects_mismatched_ids_without_writing_output(tmp_path):
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    conflicts = tmp_path / "conflicts.jsonl"
    _write_jsonl(first, [_record("one")])
    _write_jsonl(second, [_record("two")])

    with pytest.raises(ValueError, match="annotation IDs do not match"):
        compare_agent_annotations(first, second, conflicts)

    assert not conflicts.exists()


@pytest.mark.parametrize(
    ("records", "message"),
    [
        ([_record("one"), _record("one")], "duplicate id"),
        ([{"id": "one"}], "missing fields"),
    ],
)
def test_compare_rejects_invalid_annotations(tmp_path, records, message):
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    conflicts = tmp_path / "conflicts.jsonl"
    _write_jsonl(first, records)
    _write_jsonl(second, [_record("one")])

    with pytest.raises(ValueError, match=message):
        compare_agent_annotations(first, second, conflicts)


def test_compare_empty_files_reports_full_agreement(tmp_path):
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    conflicts = tmp_path / "conflicts.jsonl"
    _write_jsonl(first, [])
    _write_jsonl(second, [])

    report = compare_agent_annotations(first, second, conflicts)

    assert report["record_count"] == 0
    assert report["conflict_count"] == 0
    assert set(report["field_agreement"]) == set(LABEL_FIELDS)
    assert all(result["rate"] == 1.0 for result in report["field_agreement"].values())
    assert conflicts.read_text(encoding="utf-8") == ""


def test_write_requirement_audit_sheet_only_includes_core_disagreements(tmp_path):
    dataset = tmp_path / "dataset.jsonl"
    conflicts = tmp_path / "conflicts.jsonl"
    output = tmp_path / "audit.csv"
    _write_jsonl(
        dataset,
        [
            {
                "id": "one",
                "platform": "github",
                "source_url": "https://example.test/one",
                "title": "One",
                "content": "Source one",
            },
            {
                "id": "two",
                "platform": "juejin",
                "source_url": "https://example.test/two",
                "title": "Two",
                "content": "Source two",
            },
        ],
    )
    _write_jsonl(
        conflicts,
        [
            {
                "id": "one",
                "disagreements": {"requirement_present": {"first": "yes", "second": "no"}},
                "first": _record("one", requirement_present="yes"),
                "second": _record("one", requirement_present="no"),
            },
            {
                "id": "two",
                "disagreements": {"title": {"first": "A", "second": "B"}},
                "first": _record("two", title="A"),
                "second": _record("two", title="B"),
            },
        ],
    )

    assert write_requirement_audit_sheet(dataset, conflicts, output) == 1
    with output.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows == [
        {
            "id": "one",
            "platform": "github",
            "source_url": "https://example.test/one",
            "source_title": "One",
            "source_content": "Source one",
            "agent_a": "yes",
            "agent_b": "no",
            "your_decision": "",
            "notes": "",
        }
    ]


def test_apply_and_merge_human_requirement_decisions(tmp_path):
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    audit = tmp_path / "audit.csv"
    output = tmp_path / "merged.jsonl"
    _write_jsonl(first, [_record("one", requirement_present="yes"), _record("two")])
    _write_jsonl(second, [_record("one", requirement_present="no"), _record("two")])
    with audit.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("id", "agent_a", "agent_b", "your_decision", "notes"),
        )
        writer.writeheader()
        writer.writerow(
            {
                "id": "one",
                "agent_a": "yes",
                "agent_b": "no",
                "your_decision": "",
                "notes": "",
            }
        )

    apply_human_audit_decisions(audit, ["no"])
    counts = merge_human_requirement_decisions(first, second, audit, output)
    merged = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]

    assert counts == {"agent_a": 1, "agent_b": 1, "human_override": 0}
    assert merged[0]["requirement_present"] == "no"
    assert merged[0]["human_requirement_reviewed"] is True
    assert merged[0]["adjudication_source"] == "agent_b"
    assert merged[1]["human_requirement_reviewed"] is False


def test_merge_allows_human_decision_that_matches_neither_agent(tmp_path):
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    audit = tmp_path / "audit.csv"
    output = tmp_path / "merged.jsonl"
    _write_jsonl(first, [_record("one", requirement_present="yes")])
    _write_jsonl(second, [_record("one", requirement_present="unclear")])
    with audit.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("id", "your_decision"))
        writer.writeheader()
        writer.writerow({"id": "one", "your_decision": "no"})

    counts = merge_human_requirement_decisions(first, second, audit, output)
    record = json.loads(output.read_text(encoding="utf-8"))

    assert counts == {"agent_a": 0, "agent_b": 0, "human_override": 1}
    assert record["requirement_present"] == "no"
    assert record["title"] == ""
    assert record["sentiment"] == "mild"
    assert record["adjudication_source"] == "human_override"


def test_validate_agent_assisted_review_reports_human_coverage(tmp_path):
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    audit = tmp_path / "audit.csv"
    merged = tmp_path / "merged.jsonl"
    first_records = [_record(str(index)) for index in range(100)]
    second_records = [dict(record) for record in first_records]
    second_records[0]["requirement_present"] = "no"
    _write_jsonl(first, first_records)
    _write_jsonl(second, second_records)
    with audit.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("id", "your_decision"))
        writer.writeheader()
        writer.writerow({"id": "0", "your_decision": "yes"})
    merged_records = [
        {
            **record,
            "human_requirement_reviewed": record["id"] == "0",
            "adjudication_source": "agent_a",
        }
        for record in first_records
    ]
    _write_jsonl(merged, merged_records)

    report = validate_agent_assisted_review(first, second, audit, merged)

    assert report == {
        "record_count": 100,
        "agent_annotation_count": 200,
        "requirement_conflicts": 1,
        "human_reviewed": 1,
        "human_coverage_rate": 0.01,
    }
