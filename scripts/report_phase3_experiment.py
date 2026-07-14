"""Build the reproducible Phase 3 RAG and HITL experiment report."""

from __future__ import annotations

import argparse
from pathlib import Path

from needradar.services.phase3_reporting import build_phase3_report, write_phase3_report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=Path("evaluation/phase3/runs/full-final"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("evaluation/phase3"),
    )
    args = parser.parse_args()

    report = build_phase3_report(
        args.run_dir,
        Path("evaluation/phase2/discussions.jsonl"),
        Path("evaluation/phase2/annotations_adjudicated.jsonl"),
    )
    json_path = args.output_dir / "full-report.json"
    markdown_path = args.output_dir / "full-report.md"
    write_phase3_report(report, json_path, markdown_path)
    print(f"Wrote {json_path}")
    print(f"Wrote {markdown_path}")


if __name__ == "__main__":
    main()
