"""Score Phase 2 extraction predictions against the adjudicated proxy gold."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from needradar.services.extraction_metrics import score_extractions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("predictions", type=Path, help="Prediction JSONL with all 100 IDs")
    parser.add_argument("--output", type=Path, help="Optional JSON report path")
    args = parser.parse_args()
    report = score_extractions(
        Path("evaluation/phase2/annotations_adjudicated.jsonl"),
        args.predictions,
        Path("evaluation/phase2/discussions.jsonl"),
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"Wrote metrics to {args.output}")
    print(rendered, end="")


if __name__ == "__main__":
    main()
