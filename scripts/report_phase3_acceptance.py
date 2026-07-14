"""Build the offline Phase 3 Issue #4 acceptance report."""

from pathlib import Path

from needradar.services.phase3_acceptance import build_phase3_acceptance, write_phase3_acceptance


def main() -> None:
    output_dir = Path("evaluation/phase3")
    report = build_phase3_acceptance(
        output_dir / "full-report.json",
        output_dir / "verifier-runs/full-v2/report.json",
    )
    write_phase3_acceptance(
        report,
        output_dir / "acceptance.json",
        output_dir / "acceptance.md",
    )
    print(f"Wrote {output_dir / 'acceptance.json'}")
    print(f"Wrote {output_dir / 'acceptance.md'}")


if __name__ == "__main__":
    main()
