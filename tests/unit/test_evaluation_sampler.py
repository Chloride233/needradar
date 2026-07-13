import json
from unittest.mock import AsyncMock, patch

import pytest

from needradar.schemas.schemas import RawDiscussionItem
from needradar.services.evaluation_sampler import collect_stratified_sample, write_sample


def _item(platform: str, index: int) -> RawDiscussionItem:
    return RawDiscussionItem(
        platform=platform,
        source_url=f"https://example.test/{platform}/{index}",
        title=f"Title {index}",
        content=f"Content {index}",
        author="not persisted",
        tags=["ai"],
    )


@pytest.mark.asyncio
async def test_collect_stratified_sample_respects_quotas_and_removes_authors():
    crawlers = {}

    def make_crawler(platform):
        crawler = AsyncMock()
        crawler.crawl.return_value = [_item(platform, index) for index in range(3)]
        crawlers[platform] = crawler
        return crawler

    with patch("needradar.services.evaluation_sampler.create_crawler", side_effect=make_crawler):
        records = await collect_stratified_sample(
            plan={"github": 2, "juejin": 1},
            keywords={"github": "AI", "juejin": "AI 工具"},
        )

    assert [record["platform"] for record in records] == ["github", "github", "juejin"]
    assert all("author" not in record for record in records)
    crawlers["github"].crawl.assert_awaited_once_with("AI", max_items=2)
    crawlers["juejin"].close.assert_awaited_once()


@pytest.mark.asyncio
async def test_collect_rejects_incomplete_stratum():
    crawler = AsyncMock()
    crawler.crawl.return_value = [_item("github", 1)]

    with patch("needradar.services.evaluation_sampler.create_crawler", return_value=crawler):
        with pytest.raises(RuntimeError, match="required 2"):
            await collect_stratified_sample(plan={"github": 2}, keywords={"github": "AI"})


def test_write_sample_creates_verifiable_manifest(tmp_path):
    records = [
        {
            "id": "one",
            "platform": "github",
            "query": "AI",
            "source_url": "https://example.test/1",
            "title": "Title",
            "content": "Content",
            "tags": [],
            "sampled_at": "2026-07-13T00:00:00+00:00",
        }
    ]

    dataset_path, manifest_path = write_sample(records, tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert json.loads(dataset_path.read_text(encoding="utf-8")) == records[0]
    assert manifest["sample_size"] == 1
    assert manifest["platform_counts"] == {"github": 1}
    assert len(manifest["dataset_sha256"]) == 64
    assert manifest["author_fields_stored"] is False
