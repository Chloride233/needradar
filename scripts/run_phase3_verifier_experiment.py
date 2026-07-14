"""Dry-run or execute the paid Phase 3 verifier component experiment."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from needradar.llm.pricing import PRICING


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preset", default="deepseek-v4-flash")
    parser.add_argument("--execute", action="store_true", help="Perform real provider calls")
    parser.add_argument("--retry-failed", action="store_true", help="Retry only records with failed stages")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("evaluation/phase3/verifier-runs/full-v2"),
    )
    args = parser.parse_args()
    estimate = {
        "records": 30,
        "actual_calls": 150,
        "naive_independent_calls": 600,
        "artifact_reuse_calls_saved": 450,
        "preset": args.preset,
        "output_dir": str(args.output_dir),
        "external_payload": "de-authored public report text and embedded public source snippets",
        "gold_sent_externally": False,
        "maximum_input_tokens": 900_000,
        "maximum_output_tokens": 255_000,
    }
    pricing = PRICING[args.preset]
    estimate["maximum_no_cache_cost_cny"] = (
        estimate["maximum_input_tokens"] * pricing.input_per_million
        + estimate["maximum_output_tokens"] * pricing.output_per_million
    ) / 1_000_000
    if not args.execute:
        print(json.dumps(estimate, ensure_ascii=False, indent=2))
        return

    from needradar.llm.provider import llm
    from needradar.services.phase3_verifier_experiment import run_verifier_experiment

    llm.activate_preset(args.preset)
    preset = llm.active_preset
    if not preset or not preset.api_key:
        raise SystemExit(f"API key not configured for {args.preset}")
    root = Path(__file__).resolve().parents[1]
    provider_params = {
        "preset_id": preset.id,
        "temperature": preset.temperature,
        "max_tokens": preset.max_tokens,
        "cache_prefix": True,
        "fallback_to_default": False,
        "extra_body": {"thinking": {"type": "disabled"}},
    }
    pricing_values = {
        "input_per_million": pricing.input_per_million,
        "input_cache_hit_per_million": pricing.input_cache_hit_per_million,
        "output_per_million": pricing.output_per_million,
    }
    result = asyncio.run(
        run_verifier_experiment(
            root / "evaluation/phase3/verifier-benchmark.jsonl",
            root / "evaluation/phase3/verifier-gold.jsonl",
            root / "evaluation/phase3/verifier-benchmark-manifest.json",
            root / args.output_dir,
            llm,
            model_id=f"{preset.id}:{preset.litellm_model}",
            provider_params=provider_params,
            pricing=pricing_values,
            retry_failed=args.retry_failed,
        )
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
