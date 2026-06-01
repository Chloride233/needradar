"""Unit tests for XiaohongshuCrawler — SSR parsing, recursive note finding."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from needradar.crawlers.xiaohongshu import XiaohongshuCrawler

SSR = """<script>window.__INITIAL_STATE__={"search":{"notes":[
  {"id":"a1","title":"AI编程工具推荐","desc":"用Cursor开发一个月","author":{"name":"用户A"},"tags":[{"name":"AI工具"}]},
  {"id":"b2","title":"独立开发者技术栈","desc":"vibe coding半年总结","user":{"nickname":"开发者"},"tags":[]}
]}}</script>"""


class TestXiaohongshuCrawler:
    def test_platform(self):
        assert XiaohongshuCrawler.PLATFORM == "xiaohongshu"

    @pytest.mark.asyncio
    async def test_ssr_parsing(self):
        c = XiaohongshuCrawler()
        m = MagicMock(); m.text = SSR
        with patch.object(c, "_request_with_retry", AsyncMock(return_value=m)):
            items = await c.crawl("AI")
        assert len(items) == 2
        assert items[0].platform == "xiaohongshu"
        assert items[0].title == "AI编程工具推荐"
        assert items[0].author == "用户A"
        assert items[0].tags == ["AI工具"]

    def test_find_notes_recursive(self):
        c = XiaohongshuCrawler()
        r = c._find_notes({"a": {"b": {"notes": [{"id": "x", "title": "深层"}]}}})
        assert r[0]["title"] == "深层"

    @pytest.mark.asyncio
    async def test_no_ssr_no_cookie(self):
        c = XiaohongshuCrawler()
        m = MagicMock(); m.text = "<html></html>"
        with patch.object(c, "_request_with_retry", AsyncMock(return_value=m)):
            assert await c.crawl("x") == []
