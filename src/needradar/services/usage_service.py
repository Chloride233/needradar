from __future__ import annotations

import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from needradar.core.config import settings
from needradar.models.llm_usage import LLMUsage


class UsageService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def record_usage(self, **kwargs) -> LLMUsage:
        row = LLMUsage(**kwargs)
        self._db.add(row)
        await self._db.flush()
        return row

    async def get_summary(self, days: int = 30) -> dict:
        since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
        stmt = select(
            func.count().label("requests"),
            func.coalesce(func.sum(LLMUsage.input_tokens), 0).label("input_tokens"),
            func.coalesce(func.sum(LLMUsage.output_tokens), 0).label("output_tokens"),
            func.coalesce(func.sum(LLMUsage.cached_tokens), 0).label("cached_tokens"),
            func.coalesce(func.sum(LLMUsage.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(LLMUsage.cost_cny), 0).label("total_cost"),
        ).where(LLMUsage.created_at >= since)
        result = (await self._db.execute(stmt)).one()

        cached = int(result.cached_tokens)
        inp = int(result.input_tokens)
        hit_rate = round(cached / inp * 100, 1) if inp else 0
        # DeepSeek cache costs ~50% less than normal input tokens
        saved_cny = round(cached * 0.000001, 4)  # approximate savings

        return {
            "days": days,
            "requests": result.requests,
            "input_tokens": inp,
            "output_tokens": int(result.output_tokens),
            "cached_tokens": cached,
            "cache_hit_rate": hit_rate,
            "cache_saved_cny": saved_cny,
            "total_tokens": int(result.total_tokens),
            "total_cost_cny": round(float(result.total_cost), 4),
        }

    async def get_daily_trend(self, days: int = 30) -> list[dict]:
        since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
        stmt = (
            select(
                func.date(LLMUsage.created_at).label("date"),
                func.count().label("requests"),
                func.coalesce(func.sum(LLMUsage.total_tokens), 0).label("tokens"),
                func.coalesce(func.sum(LLMUsage.cost_cny), 0).label("cost"),
            )
            .where(LLMUsage.created_at >= since)
            .group_by(func.date(LLMUsage.created_at))
            .order_by(func.date(LLMUsage.created_at))
        )
        rows = (await self._db.execute(stmt)).all()
        return [
            {"date": str(r.date), "requests": r.requests,
             "tokens": int(r.tokens), "cost_cny": round(float(r.cost), 4)}
            for r in rows
        ]

    async def get_model_stats(self, days: int = 30) -> list[dict]:
        since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
        stmt = (
            select(
                LLMUsage.model,
                LLMUsage.call_type,
                func.count().label("requests"),
                func.coalesce(func.sum(LLMUsage.input_tokens), 0).label("input_tokens"),
                func.coalesce(func.sum(LLMUsage.output_tokens), 0).label("output_tokens"),
                func.coalesce(func.sum(LLMUsage.cached_tokens), 0).label("cached_tokens"),
                func.coalesce(func.sum(LLMUsage.total_tokens), 0).label("total_tokens"),
                func.coalesce(func.sum(LLMUsage.cost_cny), 0).label("total_cost"),
                func.coalesce(func.avg(LLMUsage.cost_cny), 0).label("avg_cost"),
            )
            .where(LLMUsage.created_at >= since)
            .group_by(LLMUsage.model, LLMUsage.call_type)
            .order_by(func.sum(LLMUsage.cost_cny).desc())
        )
        rows = (await self._db.execute(stmt)).all()
        return [
            {
                "model": r.model,
                "call_type": r.call_type,
                "requests": r.requests,
                "input_tokens": int(r.input_tokens),
                "output_tokens": int(r.output_tokens),
                "cached_tokens": int(r.cached_tokens),
                "total_tokens": int(r.total_tokens),
                "total_cost_cny": round(float(r.total_cost), 4),
                "avg_cost_cny": round(float(r.avg_cost), 6),
            }
            for r in rows
        ]

    async def get_recent_records(
        self, limit: int = 50, offset: int = 0,
        model: str | None = None, call_type: str | None = None,
    ) -> dict:
        from sqlalchemy import and_
        conditions: list = []
        if model:
            conditions.append(LLMUsage.model.ilike(f"%{model}%"))
        if call_type:
            conditions.append(LLMUsage.call_type == call_type)
        where_clause = and_(*conditions) if conditions else True

        total_stmt = select(func.count()).select_from(LLMUsage).where(where_clause)
        total = (await self._db.execute(total_stmt)).scalar() or 0

        stmt = (
            select(LLMUsage)
            .where(where_clause)
            .order_by(LLMUsage.created_at.desc())
            .limit(limit).offset(offset)
        )
        rows = (await self._db.execute(stmt)).scalars().all()
        return {
            "items": rows,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def check_budget(self) -> dict:
        alerts: list[dict] = []
        now = datetime.datetime.now(datetime.timezone.utc)

        if settings.budget_daily_limit > 0:
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            stmt = select(func.coalesce(func.sum(LLMUsage.cost_cny), 0)).where(
                LLMUsage.created_at >= today_start,
            )
            spent = float((await self._db.execute(stmt)).scalar() or 0)
            if spent >= settings.budget_daily_limit:
                alerts.append({
                    "level": "daily",
                    "limit": settings.budget_daily_limit,
                    "spent": round(spent, 4),
                    "message": f"日预算已超限：¥{spent:.4f} / ¥{settings.budget_daily_limit}",
                })

        if settings.budget_monthly_limit > 0:
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            stmt = select(func.coalesce(func.sum(LLMUsage.cost_cny), 0)).where(
                LLMUsage.created_at >= month_start,
            )
            spent = float((await self._db.execute(stmt)).scalar() or 0)
            if spent >= settings.budget_monthly_limit:
                alerts.append({
                    "level": "monthly",
                    "limit": settings.budget_monthly_limit,
                    "spent": round(spent, 4),
                    "message": f"月预算已超限：¥{spent:.4f} / ¥{settings.budget_monthly_limit}",
                })

        return {"alerts": alerts, "daily_limit": settings.budget_daily_limit,
                "monthly_limit": settings.budget_monthly_limit}
