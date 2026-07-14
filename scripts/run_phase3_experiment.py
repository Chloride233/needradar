"""Run the paid Phase 3 RAG and HITL extraction experiment."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from needradar.llm.pricing import PRICING
from needradar.llm.provider import llm
from needradar.services.phase3_corpus import Phase3CorpusRetriever
from needradar.services.phase3_experiment import (
    CONFIGURATIONS,
    DEFAULT_MAX_DISCUSSION_CHARS,
    run_phase3_experiment,
    run_phase3_suite,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--configuration",
        choices=(*CONFIGURATIONS, "all"),
        default="all",
    )
    parser.add_argument("--preset", default="deepseek-v4-flash")
    parser.add_argument("--limit", type=int)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("evaluation/phase3/runs/full"),
    )
    args = parser.parse_args()

    llm.activate_preset(args.preset)
    preset = llm.active_preset
    if not preset or not preset.api_key:
        raise SystemExit(f"API key not configured for {args.preset}")

    root = Path(__file__).resolve().parents[1]
    dataset = root / "evaluation" / "phase2" / "discussions.jsonl"
    gold = root / "evaluation" / "phase2" / "annotations_adjudicated.jsonl"
    evidence_root = root / "evaluation" / "phase3"
    output_root = root / args.output_dir
    corpus_path = evidence_root / "rag-corpus.jsonl"
    model_id = f"{preset.id}:{preset.litellm_model}"
    uses_rag = args.configuration in {"rag", "rag_hitl", "all"}
    if uses_rag and not corpus_path.exists():
        raise SystemExit("Frozen RAG corpus not found; run scripts/sample_phase3_rag_corpus.py first")
    retriever = Phase3CorpusRetriever(corpus_path) if uses_rag else None
    model_pricing = PRICING[preset.id]
    provider_params = {
        "preset_id": preset.id,
        "temperature": preset.temperature,
        "max_tokens": preset.max_tokens,
        "cache_prefix": True,
        "fallback_to_default": False,
    }
    pricing = {
        "input_per_million": model_pricing.input_per_million,
        "input_cache_hit_per_million": model_pricing.input_cache_hit_per_million,
        "output_per_million": model_pricing.output_per_million,
    }

    if args.configuration == "all":
        report = asyncio.run(
            run_phase3_suite(
                dataset,
                gold,
                output_root,
                root,
                llm,
                retriever=retriever,
                model_id=model_id,
                limit=args.limit,
                provider_params=provider_params,
                pricing=pricing,
                max_discussion_chars=DEFAULT_MAX_DISCUSSION_CHARS,
            )
        )
    else:
        report = asyncio.run(
            run_phase3_experiment(
                dataset,
                gold,
                output_root / args.configuration,
                root,
                llm,
                configuration=args.configuration,
                retriever=retriever,
                model_id=model_id,
                limit=args.limit,
                provider_params=provider_params,
                pricing=pricing,
                max_discussion_chars=DEFAULT_MAX_DISCUSSION_CHARS,
            )
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
