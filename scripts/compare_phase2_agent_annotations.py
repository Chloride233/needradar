"""Compare two independent Phase 2 agent annotation JSONL files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from needradar.services.annotation_comparison import (
    compare_agent_annotations,
    write_requirement_audit_sheet,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("first", type=Path, help="First agent annotation JSONL")
    parser.add_argument("second", type=Path, help="Second agent annotation JSONL")
    parser.add_argument(
        "--conflicts",
        type=Path,
        default=Path("evaluation/phase2/agent-conflicts.jsonl"),
        help="Output JSONL for records requiring adjudication",
    )
    parser.add_argument(
        "--audit-sheet",
        type=Path,
        default=Path("evaluation/phase2/human-audit.csv"),
        help="Output CSV for human review of requirement-presence conflicts",
    )
    args = parser.parse_args()

    report = compare_agent_annotations(args.first, args.second, args.conflicts)
    audit_count = write_requirement_audit_sheet(
        Path("evaluation/phase2/discussions.jsonl"), args.conflicts, args.audit_sheet
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    print(f"Wrote {report['conflict_count']} conflicts to {args.conflicts}")
    print(f"Wrote {audit_count} requirement conflicts to {args.audit_sheet}")


if __name__ == "__main__":
    main()
