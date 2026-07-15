import pytest
from sqlalchemy import select

from needradar.models.fingerprint import CrawlFingerprint
from needradar.schemas.schemas import RawDiscussionItem
from needradar.services.crawl_reliability import (
    content_fingerprint,
    deduplicate_items,
    filter_new_items,
    save_fingerprints,
)


def _item(url: str, title: str = "Need a feature", content: str = "Users need export") -> RawDiscussionItem:
    return RawDiscussionItem(platform="github", source_url=url, title=title, content=content)


def test_content_fingerprint_normalizes_case_and_whitespace():
    assert content_fingerprint(_item("https://a", " Need  A ", "Users\nneed export")) == content_fingerprint(
        _item("https://b", "need a", "users need   export")
    )


def test_deduplicate_items_matches_batch_url_and_fingerprint_semantics():
    items = [
        _item("https://one"),
        _item("https://one", content="different"),
        _item("https://mirror"),
        _item("https://unique", content="different"),
    ]

    unique, skipped = deduplicate_items(items)

    assert [item.source_url for item in unique] == ["https://one", "https://unique"]
    assert skipped == 2


@pytest.mark.asyncio
async def test_filter_new_items_deduplicates_known_content_and_batch_items(db_session):
    known = _item("https://known")
    save_fingerprints(db_session, "python", "github", [known])
    await db_session.flush()

    new_items, skipped = await filter_new_items(
        db_session,
        "python",
        "github",
        [_item("https://mirror"), _item("https://new", content="A different need"), _item("https://new")],
    )

    assert [item.source_url for item in new_items] == ["https://new"]
    assert skipped == 2


@pytest.mark.asyncio
async def test_save_fingerprints_persists_content_hash(db_session):
    item = _item("https://item")
    save_fingerprints(db_session, "python", "github", [item])
    await db_session.flush()
    row = (await db_session.execute(select(CrawlFingerprint))).scalar_one()
    assert row.content_hash == content_fingerprint(item)
