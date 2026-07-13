"""Apply human decisions to the Phase 2 agent disagreement audit."""

from __future__ import annotations

import argparse
from pathlib import Path

from needradar.services.annotation_comparison import (
    apply_human_audit_decisions,
    merge_human_requirement_decisions,
    validate_agent_assisted_review,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("decisions", nargs="+", help="One yes/no/unclear decision per audit row")
    args = parser.parse_args()
    base = Path("evaluation/phase2")
    audit_path = base / "human-audit.csv"
    apply_human_audit_decisions(audit_path, args.decisions)
    counts = merge_human_requirement_decisions(
        base / "annotations_agent_a.jsonl",
        base / "annotations_agent_b.jsonl",
        audit_path,
        base / "annotations_adjudicated.jsonl",
    )
    print(f"Applied {len(args.decisions)} human decisions")
    print(f"Merged labels: {counts}")
    report = validate_agent_assisted_review(
        base / "annotations_agent_a.jsonl",
        base / "annotations_agent_b.jsonl",
        audit_path,
        base / "annotations_adjudicated.jsonl",
    )
    print(f"Agent-assisted review complete: {report}")


if __name__ == "__main__":
    main()
