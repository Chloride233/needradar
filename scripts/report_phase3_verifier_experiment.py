"""Build the formal schema-v2 Phase 3 verifier report without provider calls."""

from pathlib import Path

from needradar.services.phase3_verifier_reporting import build_verifier_report, write_verifier_report


def main() -> None:
    run_dir = Path("evaluation/phase3/verifier-runs/full-v2")
    report = build_verifier_report(
        run_dir,
        Path("evaluation/phase3/verifier-benchmark.jsonl"),
        Path("evaluation/phase3/verifier-gold.jsonl"),
    )
    write_verifier_report(report, run_dir / "report.json", run_dir / "report.md")
    print(f"Wrote {run_dir / 'report.json'}")
    print(f"Wrote {run_dir / 'report.md'}")


if __name__ == "__main__":
    main()
