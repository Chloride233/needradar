#!/usr/bin/env python
"""One-shot migration: convert legacy JSON/string references to EntityLink rows.

Run:
    python scripts/migrate_to_entity_links.py

The script is **idempotent** — re-running it will skip already-migrated links.
Original source data is NOT modified, so a dry-run is safe by design.

Requirements:
    - NeedRadar backend must be importable (run from project root).
    - SQLite database at ``data/needradar.db`` must exist and be accessible.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from needradar.core.config import settings
from needradar.services.link_service import EntityLinkService


async def _main() -> None:
    db_url = settings.database_url
    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        service = EntityLinkService(db)

        print("Migrating legacy references -> EntityLink rows ...")
        counts = await service.migrate_all()
        await db.commit()

    print(f"\nMigration complete:")
    print(f"   Opportunity -> Requirement:  {counts['opportunity_links']} links")
    print(f"   CrawlTask -> PipelineRun:    {counts['pipeline_links']} links")
    print(f"   Verification -> Report:      {counts['verification_links']} links")
    total = sum(counts.values())
    print(f"   -------------------------")
    print(f"   Total:                      {total} links")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(_main())
