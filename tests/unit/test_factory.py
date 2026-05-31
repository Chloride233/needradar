"""Tests for crawler factory auto-discovery."""
import pytest

from needradar.crawlers.base import BaseCrawler
from needradar.crawlers.factory import (
    _auto_discover,
    _registry,
    available_platforms,
    create_crawler,
    register_crawler,
)
from needradar.schemas.schemas import RawDiscussionItem


class MockCrawler(BaseCrawler):
    PLATFORM = "mock_platform"

    async def crawl(self, keyword: str, max_items: int = 100) -> list[RawDiscussionItem]:
        return []


@pytest.fixture(autouse=True)
def clean_registry():
    """Save and restore _registry between tests."""
    original = dict(_registry)
    _registry.clear()
    yield
    _registry.clear()
    _registry.update(original)


class TestAutoDiscover:
    def test_discovers_real_crawlers(self):
        _auto_discover()
        platforms = sorted(_registry.keys())
        assert "github" in platforms
        assert "stackoverflow" in platforms
        assert "juejin" in platforms
        assert "bilibili" in platforms

    def test_idempotent(self):
        _auto_discover()
        count1 = len(_registry)
        _auto_discover()
        count2 = len(_registry)
        assert count1 == count2


class TestRegisterCrawler:
    def test_register_new_platform(self):
        register_crawler("test_platform", MockCrawler)
        assert "test_platform" in _registry
        assert _registry["test_platform"] is MockCrawler

    def test_register_overwrites_existing(self):
        register_crawler("test_platform", MockCrawler)

        class AnotherCrawler(BaseCrawler):
            PLATFORM = "test_platform"

            async def crawl(self, keyword, max_items=100):
                return []

        register_crawler("test_platform", AnotherCrawler)
        assert _registry["test_platform"] is AnotherCrawler


class TestCreateCrawler:
    def test_creates_registered_crawler(self):
        register_crawler("mock", MockCrawler)
        crawler = create_crawler("mock")
        assert isinstance(crawler, MockCrawler)
        assert crawler.PLATFORM == "mock_platform"

    def test_unknown_platform_raises(self):
        with pytest.raises(ValueError, match="Unknown platform"):
            create_crawler("nonexistent_platform_xyz")


class TestAvailablePlatforms:
    def test_returns_sorted_list(self):
        register_crawler("c", MockCrawler)
        register_crawler("a", MockCrawler)
        register_crawler("b", MockCrawler)
        result = available_platforms()
        assert result == ["a", "b", "c"]
