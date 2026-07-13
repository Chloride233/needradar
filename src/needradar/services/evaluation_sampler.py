from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path

from needradar.crawlers.factory import create_crawler

PHASE2_SAMPLE_PLAN = {"github": 34, "stackoverflow": 33, "juejin": 33}
PHASE2_KEYWORDS = {
    "github": "AI tool",
    "stackoverflow": "AI tool",
    "juejin": "AI 工具",
}


async def collect_stratified_sample(
    plan: Mapping[str, int] = PHASE2_SAMPLE_PLAN,
    keywords: Mapping[str, str] = PHASE2_KEYWORDS,
) -> list[dict]:
    records: list[dict] = []
    sampled_at = datetime.now(timezone.utc).isoformat()

    for platform, quota in plan.items():
        crawler = create_crawler(platform)
        try:
            items = await crawler.crawl(keywords[platform], max_items=quota)
        finally:
            await crawler.close()

        unique_items = {item.source_url: item for item in items if item.source_url}
        if len(unique_items) < quota:
            raise RuntimeError(f"{platform} returned {len(unique_items)} unique items; required {quota}")

        for item in list(unique_items.values())[:quota]:
            record_id = hashlib.sha256(f"{platform}:{item.source_url}".encode()).hexdigest()[:16]
            records.append(
                {
                    "id": record_id,
                    "platform": platform,
                    "query": keywords[platform],
                    "source_url": item.source_url,
                    "title": item.title,
                    "content": item.content,
                    "tags": item.tags,
                    "sampled_at": sampled_at,
                }
            )

    return records


def write_sample(records: list[dict], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset_path = output_dir / "discussions.jsonl"
    manifest_path = output_dir / "manifest.json"
    dataset_text = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)
    counts: dict[str, int] = {}
    keywords: dict[str, str] = {}
    for record in records:
        platform = record["platform"]
        counts[platform] = counts.get(platform, 0) + 1
        keywords[platform] = record["query"]

    dataset_path.write_text(dataset_text, encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "sample_size": len(records),
                "platform_counts": counts,
                "sample_plan": counts,
                "keywords": keywords,
                "dataset_sha256": hashlib.sha256(dataset_text.encode()).hexdigest(),
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "author_fields_stored": False,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return dataset_path, manifest_path
