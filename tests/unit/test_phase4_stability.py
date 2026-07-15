import json
from unittest.mock import AsyncMock

import pytest

from needradar.schemas.schemas import RawDiscussionItem
from needradar.services.phase4_stability import build_plan, execute_plan, summarize_observations, write_observations


def _item(url: str, content: str = "Need exports") -> RawDiscussionItem:
    return RawDiscussionItem(platform="github", source_url=url, title="Export", content=content)


def test_build_plan_declares_bounded_payload_minimal_scope():
    plan = build_plan("AI tools", ["github", "stackoverflow"], runs=2, max_items=5)

    assert plan["planned_requests"] == 4
    assert "content" in plan["does_not_store"]
    assert plan["max_items_per_request"] == 5


@pytest.mark.asyncio
async def test_execute_plan_records_success_failure_and_closes_crawlers():
    success = AsyncMock()
    success.crawl.return_value = [_item("https://example.test/1"), _item("https://example.test/2")]
    failure = AsyncMock()
    failure.crawl.side_effect = TimeoutError("offline")
    crawlers = iter([success, failure])
    times = iter([1.0, 1.25, 2.0, 2.5])

    observations = await execute_plan(
        build_plan("AI", ["github", "stackoverflow"], runs=1, max_items=5),
        crawler_factory=lambda _: next(crawlers),
        monotonic=lambda: next(times),
    )

    assert observations == [
        {
            "platform": "github",
            "run": 1,
            "status": "success",
            "elapsed_seconds": 0.25,
            "item_count": 2,
            "unique_item_count": 1,
            "duplicate_item_count": 1,
            "error_type": None,
        },
        {
            "platform": "stackoverflow",
            "run": 1,
            "status": "failed",
            "elapsed_seconds": 0.5,
            "item_count": 0,
            "unique_item_count": 0,
            "duplicate_item_count": 0,
            "error_type": "TimeoutError",
        },
    ]
    success.close.assert_awaited_once()
    failure.close.assert_awaited_once()


def test_summary_and_written_record_are_aggregate_only(tmp_path):
    observations = [
        {
            "platform": "github",
            "run": 1,
            "status": "success",
            "elapsed_seconds": 1.2,
            "item_count": 3,
            "unique_item_count": 2,
            "duplicate_item_count": 1,
            "error_type": None,
        }
    ]
    plan = build_plan("AI", ["github"], runs=1, max_items=5)
    output = tmp_path / "observations.json"

    record = write_observations(plan, observations, output)

    assert summarize_observations(observations)["platforms"]["github"]["success_rate"] == 1.0
    assert record["plan_sha256"]
    persisted = json.loads(output.read_text(encoding="utf-8"))
    assert set(persisted["observations"][0]) == {
        "platform",
        "run",
        "status",
        "elapsed_seconds",
        "item_count",
        "unique_item_count",
        "duplicate_item_count",
        "error_type",
    }
