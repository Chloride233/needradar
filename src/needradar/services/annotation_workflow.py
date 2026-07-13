from __future__ import annotations

import csv
import json
from pathlib import Path

LABEL_FIELDS = (
    "requirement_present",
    "title",
    "description",
    "pain_point",
    "use_case",
    "sentiment",
    "emotion",
    "evidence_clarity",
)
SOURCE_FIELDS = ("id", "platform", "source_url", "source_title", "source_content")
WORKFLOW_FIELDS = (
    "primary_reviewer_id",
    *(f"primary_{field}" for field in LABEL_FIELDS),
    "primary_notes",
    "reviewer_id",
    "review_status",
    "review_fields_changed",
    *(f"final_{field}" for field in LABEL_FIELDS),
    "review_notes",
)
ANNOTATION_FIELDS = SOURCE_FIELDS + WORKFLOW_FIELDS


def prepare_annotation_sheet(dataset_path: Path, output_path: Path) -> int:
    records = [json.loads(line) for line in dataset_path.read_text(encoding="utf-8").splitlines()]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ANNOTATION_FIELDS)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "id": record["id"],
                    "platform": record["platform"],
                    "source_url": record["source_url"],
                    "source_title": record["title"],
                    "source_content": record["content"],
                }
            )
    return len(records)


def validate_annotation_sheet(path: Path) -> list[str]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    errors: list[str] = []
    if len(rows) != 100:
        errors.append(f"expected 100 rows, found {len(rows)}")
    if len({row["id"] for row in rows}) != len(rows):
        errors.append("record IDs must be unique")

    allowed = {
        "requirement_present": {"yes", "no", "unclear"},
        "sentiment": {"strong", "moderate", "mild"},
        "emotion": {"positive", "negative", "neutral"},
        "evidence_clarity": {"clear", "partial", "ambiguous"},
    }
    for row_number, row in enumerate(rows, start=2):
        primary_id = row.get("primary_reviewer_id", "").strip()
        reviewer_id = row.get("reviewer_id", "").strip()
        if not primary_id or not reviewer_id:
            errors.append(f"row {row_number}: both reviewer IDs are required")
        elif primary_id == reviewer_id:
            errors.append(f"row {row_number}: reviewer IDs must differ")
        review_status = row.get("review_status", "")
        if review_status not in {"agree", "revised"}:
            errors.append(f"row {row_number}: review_status must be agree or revised")

        for prefix in ("primary_", "final_"):
            for field, values in allowed.items():
                if row.get(prefix + field, "") not in values:
                    errors.append(f"row {row_number}: invalid {prefix}{field}")
            if row.get(prefix + "requirement_present", "") != "no":
                for field in ("title", "description"):
                    if not row.get(prefix + field, "").strip():
                        errors.append(f"row {row_number}: {prefix}{field} is required")
        if review_status == "revised" and not row.get("review_fields_changed", "").strip():
            errors.append(f"row {row_number}: revised rows must list changed fields")

    return errors
