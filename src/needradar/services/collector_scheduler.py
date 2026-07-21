from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from typing import TypeVar

InputT = TypeVar("InputT")
ResultT = TypeVar("ResultT")


async def run_bounded(
    items: Sequence[InputT],
    worker: Callable[[InputT], Awaitable[ResultT]],
    concurrency: int,
) -> list[ResultT]:
    if concurrency < 1:
        raise ValueError("concurrency must be positive")
    semaphore = asyncio.Semaphore(concurrency)

    async def run_one(item: InputT) -> ResultT:
        async with semaphore:
            return await worker(item)

    return await asyncio.gather(*(run_one(item) for item in items))
