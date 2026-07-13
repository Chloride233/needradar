"""Collect the Phase 2 stratified discussion sample without LLM calls."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from needradar.services.evaluation_sampler import collect_stratified_sample, write_sample


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("evaluation/phase2"),
        help="Dataset directory (default: evaluation/phase2)",
    )
    args = parser.parse_args()

    records = asyncio.run(collect_stratified_sample())
    dataset_path, manifest_path = write_sample(records, args.output_dir)
    print(f"Wrote {len(records)} discussions to {dataset_path}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
