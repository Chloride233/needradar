from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from needradar.crawlers.factory import create_crawler
from needradar.crawlers.github import GitHubCrawler
from needradar.crawlers.juejin import JuejinCrawler
from needradar.crawlers.stackoverflow import StackOverflowCrawler, _strip_html


def test_create_crawler_factory():
    assert isinstance(create_crawler("github"), GitHubCrawler)
    assert isinstance(create_crawler("stackoverflow"), StackOverflowCrawler)
    assert isinstance(create_crawler("juejin"), JuejinCrawler)


def test_create_crawler_unknown():
    with pytest.raises(ValueError, match="Unknown platform"):
        create_crawler("unknown")


def test_strip_html():
    assert _strip_html("<p>Hello <b>world</b></p>") == "Hello world"
    assert _strip_html("plain text") == "plain text"
    assert _strip_html("") == ""


def _make_mock_response(json_data: dict) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.headers = {"X-RateLimit-Remaining": "4000"}
    resp.raise_for_status = MagicMock()
    return resp


@pytest.mark.asyncio
async def test_github_parse():
    mock_data = {
        "total_count": 1,
        "items": [
            {
                "html_url": "https://github.com/test/repo/issues/1",
                "title": "Need AI tool for PPT",
                "body": "I want an AI that makes presentations",
                "user": {"login": "testuser"},
                "labels": [{"name": "feature"}],
            }
        ],
    }

    mock_resp = _make_mock_response(mock_data)
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.is_closed = False

    crawler = GitHubCrawler()
    crawler._client = mock_client

    items = await crawler.crawl("AI PPT")
    assert len(items) == 1
    assert items[0].platform == "github"
    assert items[0].title == "Need AI tool for PPT"
    assert items[0].author == "testuser"
    assert items[0].tags == ["feature"]
    await crawler.close()


@pytest.mark.asyncio
async def test_stackoverflow_parse():
    mock_data = {
        "total": 1,
        "items": [
            {
                "title": "Best AI coding assistant?",
                "body": "<p>I need an AI tool for writing code</p>",
                "question_id": 12345,
                "owner": {"display_name": "coder1"},
                "tags": ["ai", "programming"],
            }
        ],
    }

    mock_resp = _make_mock_response(mock_data)
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.is_closed = False

    crawler = StackOverflowCrawler()
    crawler._client = mock_client

    items = await crawler.crawl("AI coding")
    assert len(items) == 1
    assert items[0].platform == "stackoverflow"
    assert items[0].title == "Best AI coding assistant?"
    assert "AI tool for writing code" in items[0].content
    assert items[0].tags == ["ai", "programming"]
    await crawler.close()


@pytest.mark.asyncio
async def test_juejin_parse_current_result_model():
    mock_data = {
        "data": [
            {
                "result_model": {
                    "article_id": "7177324512008994875",
                    "article_info": {
                        "article_id": "7177324512008994875",
                        "title": "AI tools",
                        "brief_content": "A comparison of AI tools",
                    },
                    "author_user_info": {"user_name": "author"},
                    "tags": [{"tag_name": "AI"}, {"tag_name": "Tools"}],
                }
            }
        ],
        "cursor": "",
    }
    crawler = JuejinCrawler()
    crawler._request_with_retry = AsyncMock(return_value=_make_mock_response(mock_data))

    items = await crawler.crawl("AI tools", max_items=1)

    assert len(items) == 1
    assert items[0].source_url == "https://juejin.cn/post/7177324512008994875"
    assert items[0].title == "AI tools"
    assert items[0].author == "author"
    assert items[0].tags == ["AI", "Tools"]


@pytest.mark.asyncio
async def test_juejin_follows_cursor_when_page_is_below_requested_limit():
    def page(article_id: str, cursor: str, has_more: bool) -> MagicMock:
        return _make_mock_response(
            {
                "data": [
                    {
                        "result_model": {
                            "article_info": {
                                "article_id": article_id,
                                "title": f"Article {article_id}",
                                "brief_content": "Content",
                            }
                        }
                    }
                ],
                "cursor": cursor,
                "has_more": has_more,
            }
        )

    crawler = JuejinCrawler()
    crawler._request_with_retry = AsyncMock(
        side_effect=[page("1", "next", True), page("2", "", False)]
    )

    items = await crawler.crawl("AI", max_items=2)

    assert [item.source_url for item in items] == [
        "https://juejin.cn/post/1",
        "https://juejin.cn/post/2",
    ]
    assert crawler._request_with_retry.await_count == 2
