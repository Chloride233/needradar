"""Unit tests for DoubanCrawler — HTML parsing, rating extraction."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from needradar.crawlers.douban import DoubanCrawler

HTML = """
<div class="result">
  <div class="content">
    <h3><a href="https://www.douban.com/group/topic/123456/">独立开发者如何用AI做产品</a></h3>
    <span class="subject-cast">一个人用AI做全栈的体验分享</span>
    <span class="rating_nums">8.5</span>
  </div>
</div>
<div class="result">
  <div class="content">
    <h3><a href="https://www.douban.com/group/topic/789012/">Vibe Coding 真的靠谱吗</a></h3>
    <p>vibe coding做项目的实际效果讨论</p>
  </div>
</div>
"""


class TestDoubanCrawler:
    def test_platform(self):
        assert DoubanCrawler.PLATFORM == "douban"

    @pytest.mark.asyncio
    async def test_parses_topics(self):
        c = DoubanCrawler()
        m = MagicMock(); m.text = HTML
        with patch.object(c, "_request_with_retry", AsyncMock(return_value=m)):
            items = await c.crawl("AI")
        assert len(items) == 2
        assert items[0].platform == "douban"
        assert "独立开发者" in items[0].title
        assert "group/topic/123456" in items[0].source_url
        assert "8.5" in items[0].tags[0]

    @pytest.mark.asyncio
    async def test_no_rating(self):
        c = DoubanCrawler()
        m = MagicMock()
        m.text = '<div class="result"><h3><a href="https://www.douban.com/group/topic/1/">无评分</a></h3></div>'
        with patch.object(c, "_request_with_retry", AsyncMock(return_value=m)):
            items = await c.crawl("x")
        assert items[0].tags == []

    @pytest.mark.asyncio
    async def test_empty(self):
        c = DoubanCrawler()
        m = MagicMock(); m.text = "<html></html>"
        with patch.object(c, "_request_with_retry", AsyncMock(return_value=m)):
            items = await c.crawl("x")
        assert items == []
