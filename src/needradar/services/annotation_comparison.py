from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from needradar.services.annotation_workflow import LABEL_FIELDS


def compare_agent_annotations(
    first_path: Path,
    second_path: Path,
    conflicts_path: Path,
) -> dict[str, Any]:
    first = _load_annotations(first_path)
    second = _load_annotations(second_path)

    first_ids = set(first)
    second_ids = set(second)
    if first_ids != second_ids:
        missing_from_first = sorted(second_ids - first_ids)
        missing_from_second = sorted(first_ids - second_ids)
        raise ValueError(
            "annotation IDs do not match: "
            f"missing from first={missing_from_first}, missing from second={missing_from_second}"
        )

    agreements = {field: 0 for field in LABEL_FIELDS}
    conflicts: list[dict[str, Any]] = []
    for record_id in sorted(first):
        first_record = first[record_id]
        second_record = second[record_id]
        disagreements: dict[str, dict[str, Any]] = {}
        for field in LABEL_FIELDS:
            if first_record[field] == second_record[field]:
                agreements[field] += 1
            else:
                disagreements[field] = {
                    "first": first_record[field],
                    "second": second_record[field],
                }
        if disagreements:
            conflicts.append(
                {
                    "id": record_id,
                    "disagreements": disagreements,
                    "first": first_record,
                    "second": second_record,
                }
            )

    conflicts_path.parent.mkdir(parents=True, exist_ok=True)
    with conflicts_path.open("w", encoding="utf-8") as handle:
        for conflict in conflicts:
            handle.write(json.dumps(conflict, ensure_ascii=False, sort_keys=True) + "\n")

    record_count = len(first)
    return {
        "record_count": record_count,
        "conflict_count": len(conflicts),
        "field_agreement": {
            field: {
                "agreed": agreements[field],
                "total": record_count,
                "rate": agreements[field] / record_count if record_count else 1.0,
            }
            for field in LABEL_FIELDS
        },
    }


def _load_annotations(path: Path) -> dict[str, dict[str, Any]]:
    annotations: dict[str, dict[str, Any]] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"{path}:{line_number}: invalid JSON: {error.msg}") from error
        if not isinstance(record, dict):
            raise ValueError(f"{path}:{line_number}: annotation must be a JSON object")
        record_id = record.get("id")
        if not isinstance(record_id, str) or not record_id:
            raise ValueError(f"{path}:{line_number}: id must be a non-empty string")
        if record_id in annotations:
            raise ValueError(f"{path}:{line_number}: duplicate id {record_id!r}")
        missing_fields = [field for field in LABEL_FIELDS if field not in record]
        if missing_fields:
            raise ValueError(f"{path}:{line_number}: missing fields {missing_fields}")
        annotations[record_id] = record
    return annotations


def write_requirement_audit_sheet(
    dataset_path: Path,
    conflicts_path: Path,
    output_path: Path,
) -> int:
    sources = {
        record["id"]: record
        for line in dataset_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
        for record in [json.loads(line)]
    }
    conflicts = [
        json.loads(line)
        for line in conflicts_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    requirement_conflicts = [
        conflict for conflict in conflicts if "requirement_present" in conflict["disagreements"]
    ]
    fieldnames = (
        "id",
        "platform",
        "source_url",
        "source_title",
        "source_content",
        "agent_a",
        "agent_b",
        "your_decision",
        "notes",
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for conflict in requirement_conflicts:
            source = sources[conflict["id"]]
            writer.writerow(
                {
                    "id": conflict["id"],
                    "platform": source["platform"],
                    "source_url": source["source_url"],
                    "source_title": source["title"],
                    "source_content": source["content"],
                    "agent_a": conflict["first"]["requirement_present"],
                    "agent_b": conflict["second"]["requirement_present"],
                }
            )
    return len(requirement_conflicts)


def apply_human_audit_decisions(path: Path, decisions: list[str]) -> None:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != len(decisions):
        raise ValueError(f"expected {len(rows)} decisions, received {len(decisions)}")
    allowed = {"yes", "no", "unclear"}
    normalized = [decision.strip().lower() for decision in decisions]
    invalid = [decision for decision in normalized if decision not in allowed]
    if invalid:
        raise ValueError(f"invalid decisions: {invalid}")

    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        for row, decision in zip(rows, normalized, strict=True):
            row["your_decision"] = decision
            writer.writerow(row)


def merge_human_requirement_decisions(
    first_path: Path,
    second_path: Path,
    audit_path: Path,
    output_path: Path,
) -> dict[str, int]:
    first = _load_annotations(first_path)
    second = _load_annotations(second_path)
    if set(first) != set(second):
        raise ValueError("annotation IDs do not match")
    with audit_path.open(encoding="utf-8-sig", newline="") as handle:
        audit_rows = list(csv.DictReader(handle))
    decisions = {row["id"]: row["your_decision"].strip().lower() for row in audit_rows}
    if any(decision not in {"yes", "no", "unclear"} for decision in decisions.values()):
        raise ValueError("all human audit decisions must be yes, no, or unclear")

    counts = {"agent_a": 0, "agent_b": 0, "human_override": 0}
    merged: list[dict[str, Any]] = []
    for record_id in sorted(first):
        selected = first[record_id]
        source = "agent_a"
        if record_id in decisions:
            decision = decisions[record_id]
            matches = [
                ("agent_a", first[record_id]),
                ("agent_b", second[record_id]),
            ]
            selected_matches = [item for item in matches if item[1]["requirement_present"] == decision]
            if selected_matches:
                source, selected = selected_matches[0]
            else:
                source = "human_override"
                selected = dict(first[record_id])
                selected["requirement_present"] = decision
                if decision == "no":
                    for field in ("title", "description", "pain_point", "use_case"):
                        selected[field] = ""
                    selected["sentiment"] = "mild"
                    selected["emotion"] = "neutral"
        record = dict(selected)
        record["adjudication_source"] = source
        record["human_requirement_reviewed"] = record_id in decisions
        counts[source] += 1
        merged.append(record)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for record in merged:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return counts


def validate_agent_assisted_review(
    first_path: Path,
    second_path: Path,
    audit_path: Path,
    merged_path: Path,
) -> dict[str, Any]:
    first = _load_annotations(first_path)
    second = _load_annotations(second_path)
    merged = _load_annotations(merged_path)
    if set(first) != set(second) or set(first) != set(merged):
        raise ValueError("agent and merged annotation IDs must match")
    if len(first) != 100:
        raise ValueError(f"expected 100 annotations, found {len(first)}")

    requirement_conflicts = {
        record_id
        for record_id in first
        if first[record_id]["requirement_present"] != second[record_id]["requirement_present"]
    }
    with audit_path.open(encoding="utf-8-sig", newline="") as handle:
        audit_rows = list(csv.DictReader(handle))
    audit_decisions = {row["id"]: row["your_decision"].strip().lower() for row in audit_rows}
    if set(audit_decisions) != requirement_conflicts:
        raise ValueError("audit rows must match all requirement-presence conflicts")
    if any(value not in {"yes", "no", "unclear"} for value in audit_decisions.values()):
        raise ValueError("all audit decisions must be yes, no, or unclear")
    reviewed = sum(bool(record.get("human_requirement_reviewed")) for record in merged.values())
    if reviewed != len(requirement_conflicts):
        raise ValueError("merged human-review markers do not match audited conflicts")

    return {
        "record_count": len(first),
        "agent_annotation_count": len(first) * 2,
        "requirement_conflicts": len(requirement_conflicts),
        "human_reviewed": reviewed,
        "human_coverage_rate": reviewed / len(first),
    }
