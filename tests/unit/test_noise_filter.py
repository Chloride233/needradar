"""Tests for NoiseFilter — rule filter, batch, LLM fallback."""

from unittest.mock import AsyncMock, patch
import pytest
from needradar.schemas.schemas import NoiseVerdict, RawDiscussionItem
from needradar.services.noise_filter import NoiseFilter, _rule_filter


LONG = "AI powered development tools and code review assistants " * 3
SHORT = "hi"

def _item(title="T", content=LONG):
    return RawDiscussionItem(platform="github", source_url="http://x.com/1",
                             title=title, content=content)


class TestRuleFilter:
    def test_short_rejected(self):
        r = _rule_filter(_item(content=SHORT))
        assert r and r.verdict == NoiseVerdict.NOISE

    def test_long_passes(self):
        r = _rule_filter(_item(content=LONG))
        assert r is None

    def test_nontech_rejected(self):
        r = _rule_filter(_item(content="股票理财基金" + "x" * 60))
        assert r and r.verdict == NoiseVerdict.NOISE

    def test_spam_rejected(self):
        r = _rule_filter(_item(content="Buy now!\n" * 20 + "x" * 60))
        assert r and r.verdict == NoiseVerdict.NOISE


class TestNoiseFilter:
    @pytest.mark.asyncio
    async def test_passes_clean(self):
        nf = NoiseFilter()
        r = await nf.filter_item(_item())
        assert r.verdict == NoiseVerdict.RELEVANT

    @pytest.mark.asyncio
    async def test_batch_mixed(self):
        nf = NoiseFilter()
        items = [_item(), _item(content=SHORT), _item()]
        results = await nf.filter_batch(items)
        assert [r.verdict for r in results] == [NoiseVerdict.RELEVANT, NoiseVerdict.NOISE, NoiseVerdict.RELEVANT]

    @pytest.mark.asyncio
    async def test_llm_fallback_no_prompt(self):
        nf = NoiseFilter(use_llm=True)
        with patch.object(nf, "_load_llm_prompt", return_value=""):
            r = await nf._llm_filter(_item())
        assert r.verdict == NoiseVerdict.RELEVANT
