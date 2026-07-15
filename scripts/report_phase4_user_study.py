"""Validate a de-identified Phase 4 study ledger and write aggregate JSON."""

from __future__ import annotations

import argparse
from pathlib import Path

from needradar.services.phase4_user_study import load_sessions, write_summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="CSV ledger using evaluation/phase4/user-study-template.csv headers")
    parser.add_argument("output", type=Path, help="Aggregate JSON output path")
    args = parser.parse_args()

    sessions = load_sessions(args.input)
    summary = write_summary(sessions, args.output)
    print(f"Validated {summary['sessions']} sessions; wrote {args.output}")


if __name__ == "__main__":
    main()
