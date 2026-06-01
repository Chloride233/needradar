"""Unit tests for TiebaCrawler — HTML parsing, fallback, edge cases."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from needradar.crawlers.tieba import TiebaCrawler

HTML = """
<div class="s_post">
  <span class="p_title"><a href="/p/123456">AI工具开发开源项目</a></span>
  <p class="p_content">大家有没有用AI辅助开发的经历？分享一下</p>
  <span class="p_author_name">贴吧用户A</span>
</div>
<div class="s_post">
  <span class="p_title"><a href="/p/789012">Cursor和Claude对比</a></span>
  <p class="p_content">两款AI编程工具使用感受</p>
</div>
"""


class TestTiebaCrawler:
    def test_platform(self):
        assert TiebaCrawler.PLATFORM == "tieba"

    @pytest.mark.asyncio
    async def test_parses_posts(self):
        c = TiebaCrawler()
        m = MagicMock(); m.text = HTML
        with patch.object(c, "_request_with_retry", AsyncMock(return_value=m)):
            items = await c.crawl("AI")
        assert len(items) == 2
        assert items[0].platform == "tieba"
        assert "AI工具开发" in items[0].title
        assert "p/123456" in items[0].source_url
        assert items[0].author == "贴吧用户A"

    @pytest.mark.asyncio
    async def test_fallback(self):
        c = TiebaCrawler()
        m = MagicMock()
        m.text = '<span class="p_title"><a href="/p/111">标题</a></span>'
        with patch.object(c, "_request_with_retry", AsyncMock(return_value=m)):
            items = await c.crawl("x")
        assert len(items) == 1

    @pytest.mark.asyncio
    async def test_empty(self):
        c = TiebaCrawler()
        m = MagicMock(); m.text = "<html></html>"
        with patch.object(c, "_request_with_retry", AsyncMock(return_value=m)):
            items = await c.crawl("x")
        assert items == []
