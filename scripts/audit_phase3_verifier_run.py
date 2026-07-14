"""Audit and freeze a failed Phase 3 verifier run without provider calls."""

from pathlib import Path

from needradar.services.phase3_verifier_reporting import build_failed_verifier_audit, write_failed_verifier_audit


def main() -> None:
    run_dir = Path("evaluation/phase3/verifier-runs/full")
    report = build_failed_verifier_audit(
        run_dir,
        Path("evaluation/phase3/verifier-benchmark.jsonl"),
        Path("evaluation/phase3/verifier-gold.jsonl"),
    )
    write_failed_verifier_audit(
        report,
        run_dir / "failed-run-audit.json",
        run_dir / "failed-run-audit.md",
    )
    print(f"Wrote {run_dir / 'failed-run-audit.json'}")
    print(f"Wrote {run_dir / 'failed-run-audit.md'}")


if __name__ == "__main__":
    main()
