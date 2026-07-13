import csv
import json

from needradar.services.annotation_workflow import prepare_annotation_sheet, validate_annotation_sheet


def test_prepare_annotation_sheet_keeps_sources_and_blank_labels(tmp_path):
    dataset = tmp_path / "discussions.jsonl"
    dataset.write_text(
        json.dumps(
            {
                "id": "sample-1",
                "platform": "github",
                "source_url": "https://example.test/1",
                "title": "Need export",
                "content": "Please add CSV export",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "annotations.csv"

    assert prepare_annotation_sheet(dataset, output) == 1
    with output.open(encoding="utf-8", newline="") as handle:
        row = next(csv.DictReader(handle))
    assert row["source_title"] == "Need export"
    assert row["primary_requirement_present"] == ""
    assert row["review_status"] == ""


def test_validate_accepts_complete_two_reviewer_sheet(tmp_path):
    path = tmp_path / "annotations.csv"
    rows = []
    for index in range(100):
        row = {
            "id": str(index),
            "primary_reviewer_id": "reviewer_a",
            "reviewer_id": "reviewer_b",
            "review_status": "agree",
            "review_fields_changed": "",
        }
        for prefix in ("primary_", "final_"):
            row.update(
                {
                    prefix + "requirement_present": "yes",
                    prefix + "title": "CSV export",
                    prefix + "description": "Export records as CSV",
                    prefix + "pain_point": "Manual copying",
                    prefix + "use_case": "Reporting",
                    prefix + "sentiment": "moderate",
                    prefix + "emotion": "neutral",
                    prefix + "evidence_clarity": "clear",
                }
            )
        rows.append(row)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)

    assert validate_annotation_sheet(path) == []


def test_validate_rejects_same_reviewer_and_pending_rows(tmp_path):
    path = tmp_path / "annotations.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("id", "primary_reviewer_id", "reviewer_id", "review_status"))
        writer.writeheader()
        writer.writerow(
            {
                "id": "one",
                "primary_reviewer_id": "reviewer_a",
                "reviewer_id": "reviewer_a",
                "review_status": "pending",
            }
        )

    errors = validate_annotation_sheet(path)

    assert any("expected 100 rows" in error for error in errors)
    assert any("reviewer IDs must differ" in error for error in errors)
    assert any("review_status" in error for error in errors)
