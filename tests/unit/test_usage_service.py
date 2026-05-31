"""Tests for UsageService with DB session."""
import pytest

from needradar.services.usage_service import UsageService


@pytest.mark.asyncio
async def test_record_usage(db_session):
    svc = UsageService(db_session)
    row = await svc.record_usage(
        preset_id="deepseek-v4-pro", model="deepseek-v4-pro",
        call_type="extraction", input_tokens=1000, output_tokens=500,
        cached_tokens=200, total_tokens=1700, cost_cny=0.005,
    )
    assert row.id is not None
    assert row.model == "deepseek-v4-pro"


@pytest.mark.asyncio
async def test_get_summary_empty(db_session):
    svc = UsageService(db_session)
    result = await svc.get_summary(days=30)
    assert result["requests"] == 0
    assert result["total_cost_cny"] == 0.0


@pytest.mark.asyncio
async def test_get_summary_with_data(db_session):
    svc = UsageService(db_session)
    await svc.record_usage(
        preset_id="dp", model="deepseek-v4-pro", call_type="extraction",
        input_tokens=1000, output_tokens=500, cached_tokens=0,
        total_tokens=1500, cost_cny=0.005,
    )
    await svc.record_usage(
        preset_id="dp", model="deepseek-v4-pro", call_type="extraction",
        input_tokens=2000, output_tokens=800, cached_tokens=800,
        total_tokens=3600, cost_cny=0.010,
    )
    result = await svc.get_summary(days=30)
    assert result["requests"] == 2
    assert result["input_tokens"] == 3000
    assert result["cached_tokens"] == 800


@pytest.mark.asyncio
async def test_get_daily_trend_empty(db_session):
    svc = UsageService(db_session)
    result = await svc.get_daily_trend(days=30)
    assert result == []


@pytest.mark.asyncio
async def test_get_daily_trend_with_data(db_session):
    svc = UsageService(db_session)
    await svc.record_usage(
        preset_id="dp", model="v4", call_type="extraction",
        input_tokens=100, output_tokens=50, cached_tokens=0,
        total_tokens=150, cost_cny=0.001,
    )
    result = await svc.get_daily_trend(days=30)
    assert len(result) == 1
    assert result[0]["requests"] == 1


@pytest.mark.asyncio
async def test_get_model_stats_empty(db_session):
    svc = UsageService(db_session)
    result = await svc.get_model_stats(days=30)
    assert result == []


@pytest.mark.asyncio
async def test_get_model_stats_with_data(db_session):
    svc = UsageService(db_session)
    await svc.record_usage(
        preset_id="dp", model="deepseek-v4-pro", call_type="extraction",
        input_tokens=1000, output_tokens=500, cached_tokens=0,
        total_tokens=1500, cost_cny=0.005,
    )
    await svc.record_usage(
        preset_id="df", model="deepseek-v4-flash", call_type="extraction",
        input_tokens=2000, output_tokens=800, cached_tokens=0,
        total_tokens=2800, cost_cny=0.003,
    )
    result = await svc.get_model_stats(days=30)
    assert len(result) == 2


@pytest.mark.asyncio
async def test_get_recent_records_empty(db_session):
    svc = UsageService(db_session)
    result = await svc.get_recent_records(limit=10)
    assert result["total"] == 0


@pytest.mark.asyncio
async def test_get_recent_records_with_call_type_filter(db_session):
    svc = UsageService(db_session)
    await svc.record_usage(
        preset_id="dp", model="v4", call_type="extraction",
        input_tokens=100, output_tokens=50, cached_tokens=0,
        total_tokens=150, cost_cny=0.001,
    )
    await svc.record_usage(
        preset_id="df", model="v4f", call_type="embed",
        input_tokens=500, output_tokens=0, cached_tokens=0,
        total_tokens=500, cost_cny=0.0,
    )
    result = await svc.get_recent_records(limit=10, call_type="extraction")
    assert result["total"] == 1


@pytest.mark.asyncio
async def test_get_recent_records_pagination(db_session):
    svc = UsageService(db_session)
    for i in range(5):
        await svc.record_usage(
            preset_id="dp", model="v4", call_type="extraction",
            input_tokens=100, output_tokens=50, cached_tokens=0,
            total_tokens=150, cost_cny=0.001 * (i + 1),
        )
    result = await svc.get_recent_records(limit=2, offset=0)
    assert result["total"] == 5
    assert len(result["items"]) == 2


@pytest.mark.asyncio
async def test_check_budget_no_alerts(db_session):
    svc = UsageService(db_session)
    result = await svc.check_budget()
    assert "alerts" in result
    assert result["alerts"] == []
