"""Unit tests for CsdnCrawler — API response parsing, em-tag stripping, errors."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from needradar.crawlers.csdn import CsdnCrawler


@pytest.fixture
def crawler():
    return CsdnCrawler()


@pytest.fixture
def mock_response():
    return {
        "code": 200,
        "data": {
            "result_vos": [
                {"title": "2025年<em>AI</em>编码工具对比",
                 "description": "主流<em>AI</em>编码工具对比",
                 "url": "https://blog.csdn.net/u1/article/123",
                 "nickname": "技术博主A", "tags": "AI,编码"},
                {"title": "<em>AI</em>辅助开发实践",
                 "description": "使用<em>AI</em>工具开发体验",
                 "url": "https://blog.csdn.net/u2/article/456",
                 "nickname": "码农B", "tags": ""},
            ],
            "total": 2, "total_page": 1,
        },
    }


class TestCsdnCrawler:
    @pytest.mark.asyncio
    async def test_platform(self, crawler):
        assert crawler.PLATFORM == "csdn"

    @pytest.mark.asyncio
    async def test_parses_results(self, crawler, mock_response):
        m = MagicMock(); m.json.return_value = mock_response
        with patch.object(crawler, "_request_with_retry", AsyncMock(return_value=m)):
            items = await crawler.crawl("AI")
        assert len(items) == 2
        assert items[0].platform == "csdn"
        assert items[0].title == "2025年AI编码工具对比"
        assert items[0].author == "技术博主A"
        assert items[0].tags == ["AI", "编码"]

    @pytest.mark.asyncio
    async def test_strips_em_tags(self, crawler):
        resp = {"code": 200, "data": {"result_vos": [{
            "title": "<em>Python</em>入门<em>教程</em>",
            "description": "<em>Python</em>基础",
            "url": "http://csdn.net/t/1", "nickname": "x", "tags": "Python",
        }], "total": 1, "total_page": 1}}
        m = MagicMock(); m.json.return_value = resp
        with patch.object(crawler, "_request_with_retry", AsyncMock(return_value=m)):
            items = await crawler.crawl("Python")
        assert items[0].title == "Python入门教程"
        assert items[0].content == "Python基础"

    @pytest.mark.asyncio
    async def test_api_error_empty(self, crawler):
        m = MagicMock(); m.json.return_value = {"code": 500, "data": {}}
        with patch.object(crawler, "_request_with_retry", AsyncMock(return_value=m)):
            items = await crawler.crawl("x")
        assert len(items) == 0

    @pytest.mark.asyncio
    async def test_empty_results(self, crawler):
        m = MagicMock()
        m.json.return_value = {"code": 200, "data": {"result_vos": [], "total": 0, "total_page": 0}}
        with patch.object(crawler, "_request_with_retry", AsyncMock(return_value=m)):
            items = await crawler.crawl("nonexistent")
        assert len(items) == 0
