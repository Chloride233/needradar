"""Bounded, payload-minimal collection stability observations for Phase 4."""

from __future__ import annotations

import hashlib
import json
import statistics
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from needradar.crawlers.factory import create_crawler
from needradar.services.crawl_reliability import content_fingerprint


def build_plan(keyword: str, platforms: list[str], runs: int, max_items: int) -> dict:
    if not keyword.strip():
        raise ValueError("keyword is required")
    if not platforms:
        raise ValueError("at least one platform is required")
    if runs < 1 or max_items < 1:
        raise ValueError("runs and max_items must be positive")
    return {
        "schema_version": 1,
        "keyword": keyword,
        "platforms": platforms,
        "runs_per_platform": runs,
        "max_items_per_request": max_items,
        "planned_requests": len(platforms) * runs,
        "stores": [
            "platform",
            "run",
            "status",
            "elapsed_seconds",
            "item_count",
            "unique_item_count",
            "duplicate_item_count",
            "error_type",
        ],
        "does_not_store": ["author", "source_url", "title", "content", "tags"],
    }


async def execute_plan(
    plan: dict,
    crawler_factory: Callable = create_crawler,
    monotonic: Callable[[], float] = time.monotonic,
) -> list[dict]:
    """Execute a plan sequentially and retain aggregate-only observation rows."""
    observations: list[dict] = []
    for run in range(1, plan["runs_per_platform"] + 1):
        for platform in plan["platforms"]:
            crawler = crawler_factory(platform)
            started = monotonic()
            try:
                items = await crawler.crawl(plan["keyword"], max_items=plan["max_items_per_request"])
                fingerprints = {content_fingerprint(item) for item in items}
                observations.append(
                    {
                        "platform": platform,
                        "run": run,
                        "status": "success",
                        "elapsed_seconds": round(monotonic() - started, 3),
                        "item_count": len(items),
                        "unique_item_count": len(fingerprints),
                        "duplicate_item_count": len(items) - len(fingerprints),
                        "error_type": None,
                    }
                )
            except Exception as error:
                observations.append(
                    {
                        "platform": platform,
                        "run": run,
                        "status": "failed",
                        "elapsed_seconds": round(monotonic() - started, 3),
                        "item_count": 0,
                        "unique_item_count": 0,
                        "duplicate_item_count": 0,
                        "error_type": type(error).__name__,
                    }
                )
            finally:
                await crawler.close()
    return observations


def summarize_observations(observations: list[dict]) -> dict:
    by_platform: dict[str, dict] = {}
    for observation in observations:
        platform = observation["platform"]
        bucket = by_platform.setdefault(
            platform,
            {"attempts": 0, "successes": 0, "elapsed_seconds": [], "items": 0, "duplicates": 0, "errors": {}},
        )
        bucket["attempts"] += 1
        bucket["elapsed_seconds"].append(observation["elapsed_seconds"])
        bucket["items"] += observation["item_count"]
        bucket["duplicates"] += observation["duplicate_item_count"]
        if observation["status"] == "success":
            bucket["successes"] += 1
        elif observation["error_type"]:
            error_type = observation["error_type"]
            bucket["errors"][error_type] = bucket["errors"].get(error_type, 0) + 1

    result = {}
    for platform, bucket in sorted(by_platform.items()):
        attempts = bucket["attempts"]
        result[platform] = {
            "attempts": attempts,
            "successes": bucket["successes"],
            "success_rate": round(bucket["successes"] / attempts, 4) if attempts else None,
            "median_elapsed_seconds": round(statistics.median(bucket["elapsed_seconds"]), 3) if attempts else None,
            "items": bucket["items"],
            "duplicate_items": bucket["duplicates"],
            "errors": dict(sorted(bucket["errors"].items())),
        }
    return {"observations": len(observations), "platforms": result}


def write_observations(plan: dict, observations: list[dict], output_path: Path) -> dict:
    record = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "plan": plan,
        "plan_sha256": hashlib.sha256(json.dumps(plan, sort_keys=True).encode("utf-8")).hexdigest(),
        "observations": observations,
        "summary": summarize_observations(observations),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return record
