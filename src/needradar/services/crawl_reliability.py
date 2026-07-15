"""Deterministic reliability primitives shared by crawl entry points."""

from __future__ import annotations

import hashlib
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from needradar.models.fingerprint import CrawlFingerprint
from needradar.schemas.schemas import RawDiscussionItem


def content_fingerprint(item: RawDiscussionItem) -> str:
    """Return a stable fingerprint for duplicate discussions with different URLs."""
    text = "\n".join((item.title, item.content)).casefold()
    normalized = re.sub(r"\s+", " ", text).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def deduplicate_items(
    items: list[RawDiscussionItem],
    *,
    known_urls: set[str] | None = None,
    known_hashes: set[str] | None = None,
) -> tuple[list[RawDiscussionItem], int]:
    urls = set(known_urls or ())
    hashes = set(known_hashes or ())
    new_items: list[RawDiscussionItem] = []
    for item in items:
        fingerprint = content_fingerprint(item)
        if item.source_url in urls or fingerprint in hashes:
            continue
        new_items.append(item)
        urls.add(item.source_url)
        hashes.add(fingerprint)
    return new_items, len(items) - len(new_items)


async def filter_new_items(
    db: AsyncSession,
    keyword: str,
    platform: str,
    items: list[RawDiscussionItem],
) -> tuple[list[RawDiscussionItem], int]:
    """Skip known URLs and content fingerprints, including duplicates in one batch."""
    urls = await db.execute(
        select(CrawlFingerprint.source_url).where(
            CrawlFingerprint.keyword == keyword,
            CrawlFingerprint.platform == platform,
        )
    )
    known_urls = {row[0] for row in urls.all()}
    hashes = await db.execute(select(CrawlFingerprint.content_hash).where(CrawlFingerprint.content_hash.is_not(None)))
    known_hashes = {row[0] for row in hashes.all()}

    return deduplicate_items(items, known_urls=known_urls, known_hashes=known_hashes)


def save_fingerprints(
    db: AsyncSession,
    keyword: str,
    platform: str,
    items: list[RawDiscussionItem],
) -> None:
    for item in items:
        db.add(
            CrawlFingerprint(
                keyword=keyword,
                platform=platform,
                source_url=item.source_url,
                content_hash=content_fingerprint(item),
            )
        )
