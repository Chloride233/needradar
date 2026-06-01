"""Unit tests for ZhihuCrawler — API response parsing, dedup, edge cases."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from needradar.crawlers.zhihu import ZhihuCrawler


@pytest.fixture
def crawler():
    return ZhihuCrawler()


@pytest.fixture
def mock_response():
    return {
        "data": [
            {"type": "search_result", "object": {
                "type": "answer", "id": 1001, "excerpt": "AI工具回答摘要",
                "question": {"id": 2001, "title": "有哪些好用的AI开发工具？"},
                "author": {"name": "张三"},
                "topics": [{"name": "人工智能"}, {"name": "开发工具"}],
            }},
            {"type": "search_result", "object": {
                "type": "article", "id": 1002, "title": "2025年AI工具评测",
                "excerpt": "盘点主流AI编码工具",
                "url": "https://zhuanlan.zhihu.com/p/1002",
                "author": {"name": "李四"},
            }},
            {"type": "search_result", "object": {
                "type": "question", "id": 2002, "title": "Claude Code vs Cursor 怎么选？",
                "excerpt": "想入坑AI编程工具",
            }},
        ],
        "paging": {"is_end": True},
    }


class TestZhihuCrawler:
    @pytest.mark.asyncio
    async def test_platform(self, crawler):
        assert crawler.PLATFORM == "zhihu"

    @pytest.mark.asyncio
    async def test_parses_answer(self, crawler, mock_response):
        m = MagicMock(); m.json.return_value = mock_response
        with patch.object(crawler, "_request_with_retry", AsyncMock(return_value=m)):
            items = await crawler.crawl("AI工具")
        assert items[0].platform == "zhihu"
        assert items[0].title == "有哪些好用的AI开发工具？"
        assert items[0].author == "张三"
        assert "2001/answer/1001" in items[0].source_url

    @pytest.mark.asyncio
    async def test_parses_article(self, crawler, mock_response):
        m = MagicMock(); m.json.return_value = mock_response
        with patch.object(crawler, "_request_with_retry", AsyncMock(return_value=m)):
            items = await crawler.crawl("AI工具")
        arts = [i for i in items if "zhuanlan" in i.source_url]
        assert len(arts) == 1
        assert arts[0].title == "2025年AI工具评测"

    @pytest.mark.asyncio
    async def test_dedup_by_id(self, crawler):
        dup = {"data": [
            {"type": "search_result", "object": {
                "type": "answer", "id": 1001, "excerpt": "A",
                "question": {"id": 1, "title": "T"}, "author": {}}},
            {"type": "search_result", "object": {
                "type": "answer", "id": 1001, "excerpt": "B",
                "question": {"id": 1, "title": "T"}, "author": {}}},
        ], "paging": {"is_end": True}}
        m = MagicMock(); m.json.return_value = dup
        with patch.object(crawler, "_request_with_retry", AsyncMock(return_value=m)):
            items = await crawler.crawl("x")
        assert len(items) == 1

    @pytest.mark.asyncio
    async def test_empty(self, crawler):
        m = MagicMock(); m.json.return_value = {"data": [], "paging": {"is_end": True}}
        with patch.object(crawler, "_request_with_retry", AsyncMock(return_value=m)):
            items = await crawler.crawl("nonexistent_xyz")
        assert len(items) == 0

    @pytest.mark.asyncio
    async def test_max_items(self, crawler):
        many = {"data": [], "paging": {"is_end": True}}
        many["data"] = [
            {"type": "search_result", "object": {
                "type": "answer", "id": i, "excerpt": "x",
                "question": {"id": i + 1000, "title": f"Q{i}"}, "author": {}}}
            for i in range(10)
        ]
        m = MagicMock(); m.json.return_value = many
        with patch.object(crawler, "_request_with_retry", AsyncMock(return_value=m)):
            items = await crawler.crawl("x", max_items=5)
        assert len(items) == 5
