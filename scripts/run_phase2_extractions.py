"""Run the paid NeedRadar extraction benchmark with resumable JSONL output."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from needradar.llm.provider import llm
from needradar.services.extraction_benchmark import run_extraction_benchmark


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preset", default="deepseek-v4-flash")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    llm.activate_preset(args.preset)
    if not llm.active_preset or not llm.active_preset.api_key:
        raise SystemExit(f"API key not configured for {args.preset}")
    root = Path(__file__).resolve().parents[1]
    output = root / "evaluation" / "phase2" / "needradar_predictions.jsonl"
    report = asyncio.run(
        run_extraction_benchmark(
            root / "evaluation" / "phase2" / "discussions.jsonl",
            output,
            root,
            llm,
            limit=args.limit,
        )
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
