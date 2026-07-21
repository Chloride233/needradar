"""Run one consented, bounded Phase 4 keyword-to-report user session."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from needradar.llm.pricing import PRICING, ModelPricing
from needradar.llm.provider import SHARED_SYSTEM_PREFIX


def maximum_call_cost(messages: list[dict[str, str]], max_tokens: int, pricing: ModelPricing) -> float:
    payload = SHARED_SYSTEM_PREFIX + json.dumps(messages, ensure_ascii=False, separators=(",", ":"))
    maximum_input_tokens = len(payload.encode("utf-8"))
    return (maximum_input_tokens * pricing.input_per_million + max_tokens * pricing.output_per_million) / 1_000_000


def require_call_budget(
    spent: float,
    max_cost_cny: float,
    messages: list[dict[str, str]],
    max_tokens: int,
    pricing: ModelPricing,
) -> float:
    estimated_cost = maximum_call_cost(messages, max_tokens, pricing)
    if spent + estimated_cost > max_cost_cny:
        raise RuntimeError(
            f"insufficient session budget: ¥{max_cost_cny - spent:.6f} remaining, "
            f"¥{estimated_cost:.6f} maximum call cost"
        )
    return estimated_cost


async def run_session(
    keyword: str,
    platform: str,
    max_items: int,
    max_cost_cny: float,
    model_max_tokens: int,
    output: Path,
) -> dict:
    from needradar.core.database import async_session_factory, engine
    from needradar.crawlers.factory import create_crawler
    from needradar.llm.provider import llm
    from needradar.models import Base
    from needradar.models.llm_usage import LLMUsage
    from needradar.services.analysis_service import AnalysisService
    from needradar.services.crawl_reliability import filter_new_items, save_fingerprints
    from needradar.services.noise_filter import NoiseFilter
    from needradar.services.report_service import ReportService
    from needradar.services.vault_store import vault

    preset = llm.active_preset
    if not preset or not preset.api_key:
        raise RuntimeError("No configured LLM preset")
    original_max_tokens = preset.max_tokens
    original_complete = llm.complete
    started_at = datetime.now(timezone.utc)
    started_clock = time.monotonic()
    spent = 0.0
    session_usage: list[dict] = []
    pricing = PRICING.get(preset.id)
    if pricing is None:
        raise RuntimeError(f"No pricing configured for preset {preset.id}")

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async def bounded_complete(messages, **kwargs):
        nonlocal spent
        kwargs["fallback_to_default"] = False
        effective_max_tokens = kwargs.get("max_tokens") or preset.max_tokens
        require_call_budget(spent, max_cost_cny, messages, effective_max_tokens, pricing)
        result = await original_complete(messages, **kwargs)
        usage = llm._last_usage or {}
        session_usage.append(usage.copy())
        spent += float(usage.get("cost_cny", 0.0))
        if spent > max_cost_cny:
            raise RuntimeError(f"session cost exceeded ¥{max_cost_cny:.4f}")
        return result

    preset.max_tokens = min(original_max_tokens, model_max_tokens)
    llm.complete = bounded_complete
    raw_items = []
    new_items = []
    skipped = 0
    clean_items = []
    report_path = None
    current_stage = "crawl"
    try:
        crawler = create_crawler(platform)
        try:
            raw_items = await crawler.crawl(keyword, max_items=max_items)
        finally:
            await crawler.close()

        async with async_session_factory() as db:
            current_stage = "extraction"
            service = AnalysisService(db)
            new_items, skipped = await filter_new_items(db, keyword, platform, raw_items)
            save_fingerprints(db, keyword, platform, new_items)
            filtered = await NoiseFilter(use_llm=False).filter_batch(new_items)
            clean_items = [entry.item for entry in filtered if entry.verdict.value != "noise"]
            for item in clean_items:
                vault.archive_raw(item.platform, keyword, item.title, item.source_url, item.content, item.tags)
                await service.extract_and_store(keyword, item)
                await db.flush()
                if spent > max_cost_cny:
                    raise RuntimeError(f"session cost exceeded ¥{max_cost_cny:.4f}")

            current_stage = "report"
            report_path = await ReportService().generate_report(keyword)
            report_usage = llm.pop_last_usage()
            if report_usage:
                db.add(LLMUsage(**report_usage))
            if spent > max_cost_cny:
                raise RuntimeError(f"session cost exceeded ¥{max_cost_cny:.4f}")
            _, report_body = vault.read(report_path)
            if "AI 分析生成失败" in report_body:
                raise RuntimeError("report analysis failed")
            await db.commit()
        completed_at = datetime.now(timezone.utc)
        record = {
            "session_id": "phase4-owner-001",
            "consent_confirmed": True,
            "keyword": keyword,
            "platform": platform,
            "max_items": max_items,
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "duration_seconds": round(time.monotonic() - started_clock, 3),
            "raw_items": len(raw_items),
            "new_items": len(new_items),
            "skipped_items": skipped,
            "clean_items": len(clean_items),
            "report_path": str(report_path),
            "actual_cost_cny": round(spent, 6),
            "usage_records": len(session_usage),
            "feedback_pending": True,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return record
    except Exception as error:
        record = {
            "session_id": "phase4-owner-001",
            "consent_confirmed": True,
            "keyword": keyword,
            "platform": platform,
            "max_items": max_items,
            "started_at": started_at.isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "duration_seconds": round(time.monotonic() - started_clock, 3),
            "raw_items": len(raw_items),
            "new_items": len(new_items),
            "skipped_items": skipped,
            "clean_items": len(clean_items),
            "outcome": "failed",
            "failure_stage": current_stage,
            "failure_type": type(error).__name__,
            "actual_cost_cny": round(spent, 6),
            "usage_records": len(session_usage),
            "feedback_pending": False,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return record
    finally:
        llm.complete = original_complete
        preset.max_tokens = original_max_tokens


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("keyword")
    parser.add_argument("--platform", default="github")
    parser.add_argument("--max-items", type=int, default=3)
    parser.add_argument("--max-cost-cny", type=float, default=1.0)
    parser.add_argument("--model-max-tokens", type=int, default=2048)
    parser.add_argument("--output", type=Path, default=Path("evaluation/phase4/user-session-001.json"))
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--participant-consent", action="store_true")
    args = parser.parse_args()
    if not args.execute or not args.participant_consent:
        raise SystemExit("requires --execute and --participant-consent")
    print(
        json.dumps(
            asyncio.run(
                run_session(
                    args.keyword,
                    args.platform,
                    args.max_items,
                    args.max_cost_cny,
                    args.model_max_tokens,
                    args.output,
                )
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
