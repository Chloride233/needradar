from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from needradar.core.database import get_db
from needradar.services.usage_service import UsageService

router = APIRouter(tags=["usage"])


class UsageRecordResponse(BaseModel):
    id: int
    preset_id: str
    model: str
    call_type: str
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    total_tokens: int
    cost_cny: float
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class UsageRecordsResponse(BaseModel):
    items: list[UsageRecordResponse]
    total: int


@router.get("/usage/summary")
async def usage_summary(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    svc = UsageService(db)
    return await svc.get_summary(days)


@router.get("/usage/trend")
async def usage_trend(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    svc = UsageService(db)
    return await svc.get_daily_trend(days)


@router.get("/usage/model-stats")
async def usage_model_stats(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    svc = UsageService(db)
    return await svc.get_model_stats(days)


@router.get("/usage/records", response_model=UsageRecordsResponse)
async def usage_records(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    model: str | None = Query(None),
    call_type: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    svc = UsageService(db)
    return await svc.get_recent_records(limit, offset, model=model, call_type=call_type)


@router.get("/usage/budget")
async def usage_budget(db: AsyncSession = Depends(get_db)):
    svc = UsageService(db)
    return await svc.check_budget()
