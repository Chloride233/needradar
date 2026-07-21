import asyncio

import pytest

from needradar.services.collector_scheduler import run_bounded


@pytest.mark.asyncio
async def test_run_bounded_preserves_order_and_limits_concurrency():
    current = 0
    maximum = 0
    lock = asyncio.Lock()

    async def worker(value: int) -> int:
        nonlocal current, maximum
        async with lock:
            current += 1
            maximum = max(maximum, current)
        await asyncio.sleep(0.001)
        async with lock:
            current -= 1
        return value * 2

    results = await run_bounded(list(range(12)), worker, concurrency=3)

    assert results == [value * 2 for value in range(12)]
    assert maximum == 3


@pytest.mark.asyncio
async def test_run_bounded_rejects_non_positive_concurrency():
    with pytest.raises(ValueError, match="positive"):
        await run_bounded([], lambda value: value, concurrency=0)
