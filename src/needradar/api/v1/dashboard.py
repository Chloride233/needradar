from __future__ import annotations

import time

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from needradar.core.database import get_db
from needradar.models.crawl_task import CrawlTask
from needradar.schemas.schemas import DashboardStats
from needradar.services.vault_store import vault

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_cache: dict = {"data": None, "ts": 0.0}
_CACHE_TTL = 30  # seconds


@router.get("", response_model=DashboardStats)
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    now = time.monotonic()
    if _cache["data"] and now - _cache["ts"] < _CACHE_TTL:
        return _cache["data"]

    total_tasks = (await db.execute(select(func.count()).select_from(CrawlTask))).scalar() or 0

    all_reqs = vault.list_files("需求")
    total_reqs = len(all_reqs)

    platform_dist: dict[str, int] = {}
    sentiment_dist: dict[str, int] = {}
    for _, meta, _ in all_reqs:
        p = meta.get("来源平台", "unknown")
        platform_dist[p] = platform_dist.get(p, 0) + 1
        s = meta.get("情感倾向") or "moderate"
        sentiment_dist[s] = sentiment_dist.get(s, 0) + 1

    top_keywords = vault.top_keywords("需求", limit=10)

    result = DashboardStats(
        total_requirements=total_reqs,
        total_tasks=total_tasks,
        platform_distribution=platform_dist,
        sentiment_distribution=sentiment_dist,
        top_keywords=top_keywords,
    )
    _cache["data"] = result
    _cache["ts"] = now
    return result
