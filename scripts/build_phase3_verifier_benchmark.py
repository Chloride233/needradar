"""Build the offline Phase 3 verifier benchmark from the frozen public corpus."""

from __future__ import annotations

import argparse
from pathlib import Path

from needradar.services.phase3_verifier_benchmark import (
    apply_naturalistic_adjudication,
    build_verifier_benchmark,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path("evaluation/phase3/rag-corpus.jsonl"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("evaluation/phase3"),
    )
    parser.add_argument(
        "--adjudication",
        type=Path,
        default=Path("evaluation/phase3/verifier-naturalistic-adjudication.jsonl"),
    )
    args = parser.parse_args()
    input_path, gold_path, manifest_path = build_verifier_benchmark(args.corpus, args.output_dir)
    if args.adjudication.exists():
        apply_naturalistic_adjudication(input_path, gold_path, manifest_path, args.adjudication)
    print(f"Wrote {input_path}")
    print(f"Wrote {gold_path}")
    print(f"Wrote {manifest_path}")


if __name__ == "__main__":
    main()
