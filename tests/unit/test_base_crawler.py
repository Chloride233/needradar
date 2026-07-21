"""Tests for BaseCrawler with mocked httpx."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from needradar.crawlers.base import BaseCrawler
from needradar.crawlers.bilibili import parse_wbi_keys
from needradar.schemas.schemas import RawDiscussionItem


class FakeCrawler(BaseCrawler):
    """Concrete implementation for testing BaseCrawler."""

    PLATFORM = "fake"

    async def crawl(self, keyword: str, max_items: int = 100) -> list[RawDiscussionItem]:
        client = await self._get_client()
        resp = await client.get(f"http://fake/api?q={keyword}")
        return [
            RawDiscussionItem(
                platform=self.PLATFORM,
                source_url="http://fake/1",
                title=keyword,
                content=resp.text,
                author="test",
            )
        ]


class TestBaseCrawler:
    @pytest.mark.asyncio
    async def test_get_client_creates_once(self):
        crawler = FakeCrawler()
        client1 = await crawler._get_client()
        client2 = await crawler._get_client()
        assert client1 is client2
        await crawler.close()

    @pytest.mark.asyncio
    async def test_get_client_recreates_after_close(self):
        crawler = FakeCrawler()
        client1 = await crawler._get_client()
        await crawler.close()
        client2 = await crawler._get_client()
        assert client1 is not client2
        await crawler.close()

    @pytest.mark.asyncio
    async def test_close_when_no_client(self):
        crawler = FakeCrawler()
        # Should not raise
        await crawler.close()

    @pytest.mark.asyncio
    async def test_close_already_closed(self):
        crawler = FakeCrawler()
        _ = await crawler._get_client()
        await crawler.close()
        # Second close should be safe
        await crawler.close()


class TestRequestWithRetry:
    @pytest.mark.asyncio
    async def test_rate_limit_waits_between_requests(self):
        crawler = FakeCrawler()
        with (
            patch("needradar.crawlers.base.settings") as mock_settings,
            patch("needradar.crawlers.base.time.monotonic", side_effect=[0.0, 0.0, 1.0]),
            patch("needradar.crawlers.base.asyncio.sleep", new_callable=AsyncMock) as sleep,
        ):
            mock_settings.crawler_min_request_interval_seconds = 1.0
            await crawler._respect_rate_limit()
            await crawler._respect_rate_limit()
            sleep.assert_awaited_once_with(1.0)

    def test_parse_bilibili_wbi_keys(self):
        response = MagicMock()
        response.json.return_value = {
            "data": {
                "wbi_img": {
                    "img_url": "https://i0.hdslb.com/bfs/wbi/image-key.png",
                    "sub_url": "https://i0.hdslb.com/bfs/wbi/sub-key.png",
                }
            }
        }

        assert parse_wbi_keys(response) == ("image-key", "sub-key")

    @pytest.mark.asyncio
    async def test_successful_request(self):
        crawler = FakeCrawler()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.text = "ok"

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            resp = await crawler._request_with_retry("get", "http://test/foo")
            assert resp.status_code == 200
        await crawler.close()

    @pytest.mark.asyncio
    async def test_retry_on_429(self):
        crawler = FakeCrawler()
        rate_limited = MagicMock(spec=httpx.Response)
        rate_limited.status_code = 429
        rate_limited.headers = {"Retry-After": "0.01"}

        success = MagicMock(spec=httpx.Response)
        success.status_code = 200
        success.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = [rate_limited, success]
            resp = await crawler._request_with_retry("get", "http://test/foo", max_retries=3)
            assert resp.status_code == 200
            assert mock_get.call_count == 2
        await crawler.close()

    @pytest.mark.asyncio
    async def test_retry_on_500(self):
        crawler = FakeCrawler()
        error_500 = MagicMock(spec=httpx.Response)
        error_500.status_code = 500

        success = MagicMock(spec=httpx.Response)
        success.status_code = 200
        success.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = [
                httpx.HTTPStatusError("error", request=MagicMock(), response=error_500),
                success,
            ]
            resp = await crawler._request_with_retry("get", "http://test/foo", max_retries=3)
            assert resp.status_code == 200
            assert mock_get.call_count == 2
        await crawler.close()

    @pytest.mark.asyncio
    async def test_no_retry_on_400(self):
        crawler = FakeCrawler()
        error_400 = MagicMock(spec=httpx.Response)
        error_400.status_code = 400

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.HTTPStatusError("error", request=MagicMock(), response=error_400)
            with pytest.raises(httpx.HTTPStatusError):
                await crawler._request_with_retry("get", "http://test/foo")
            assert mock_get.call_count == 1
        await crawler.close()

    @pytest.mark.asyncio
    async def test_retry_on_timeout(self):
        crawler = FakeCrawler()
        success = MagicMock(spec=httpx.Response)
        success.status_code = 200
        success.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = [httpx.ConnectTimeout("timeout"), success]
            resp = await crawler._request_with_retry("get", "http://test/foo", max_retries=3)
            assert resp.status_code == 200
            assert mock_get.call_count == 2
        await crawler.close()

    @pytest.mark.asyncio
    async def test_retry_on_network_error(self):
        crawler = FakeCrawler()
        success = MagicMock(spec=httpx.Response)
        success.status_code = 200
        success.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = [httpx.ConnectError("offline"), success]
            response = await crawler._request_with_retry("get", "http://test/foo", max_retries=3, base_delay=0)

        assert response is success
        assert mock_get.call_count == 2
        await crawler.close()

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        crawler = FakeCrawler()
        error_500 = MagicMock(spec=httpx.Response)
        error_500.status_code = 500

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.HTTPStatusError("error", request=MagicMock(), response=error_500)
            with pytest.raises(httpx.HTTPStatusError):
                await crawler._request_with_retry("get", "http://test/foo", max_retries=1)
        await crawler.close()

    @pytest.mark.asyncio
    async def test_timeout_max_retries_exceeded(self):
        crawler = FakeCrawler()

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.ReadTimeout("timeout")
            with pytest.raises(httpx.ReadTimeout):
                await crawler._request_with_retry("get", "http://test/foo", max_retries=1)
        await crawler.close()

    @pytest.mark.asyncio
    async def test_429_without_retry_after_header(self):
        crawler = FakeCrawler()
        rate_limited = MagicMock(spec=httpx.Response)
        rate_limited.status_code = 429
        rate_limited.headers = {}  # No Retry-After header

        success = MagicMock(spec=httpx.Response)
        success.status_code = 200
        success.raise_for_status = MagicMock()

        with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = [rate_limited, success]
            resp = await crawler._request_with_retry("get", "http://test/foo", max_retries=3, base_delay=0.01)
            assert resp.status_code == 200
        await crawler.close()

    @pytest.mark.asyncio
    async def test_post_method_routing(self):
        crawler = FakeCrawler()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200

        with patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            resp = await crawler._request_with_retry("post", "http://test/foo", json={"key": "val"})
            assert resp.status_code == 200
        await crawler.close()
