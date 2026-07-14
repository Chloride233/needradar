"""Collect the held-out Phase 3 RAG corpus without LLM calls."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from needradar.services.phase3_corpus import collect_held_out_corpus, write_corpus


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phase2-dataset",
        type=Path,
        default=Path("evaluation/phase2/discussions.jsonl"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("evaluation/phase3"),
    )
    args = parser.parse_args()

    records = asyncio.run(collect_held_out_corpus(args.phase2_dataset))
    dataset_path, manifest_path = write_corpus(records, args.output_dir, args.phase2_dataset)
    print(f"Wrote {len(records)} held-out discussions to {dataset_path}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
