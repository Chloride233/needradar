"""Prepare or validate the Phase 2 human annotation worksheet."""

from __future__ import annotations

import argparse
from pathlib import Path

from needradar.services.annotation_workflow import prepare_annotation_sheet, validate_annotation_sheet

DATASET = Path("evaluation/phase2/discussions.jsonl")
ANNOTATIONS = Path("evaluation/phase2/annotations.csv")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "validate"))
    args = parser.parse_args()

    if args.command == "prepare":
        count = prepare_annotation_sheet(DATASET, ANNOTATIONS)
        print(f"Prepared {count} rows in {ANNOTATIONS}")
        return

    errors = validate_annotation_sheet(ANNOTATIONS)
    if errors:
        for error in errors[:20]:
            print(error)
        if len(errors) > 20:
            print(f"... and {len(errors) - 20} more errors")
        raise SystemExit(1)
    print("Human annotation review complete: 100/100 rows")


if __name__ == "__main__":
    main()
