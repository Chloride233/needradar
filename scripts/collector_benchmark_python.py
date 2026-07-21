#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import platform
import sys
import time
from pathlib import Path

import httpx
from loguru import logger

from needradar.core.config import settings
from needradar.crawlers.base import BaseCrawler
from needradar.schemas.schemas import RawDiscussionItem
from needradar.services.collector_comparison import SCENARIOS, render_items, validate_result, validate_workload
from needradar.services.collector_scheduler import run_bounded
from needradar.services.crawl_reliability import deduplicate_items


class FakeClient:
    def __init__(self, tasks: dict[int, dict], scenario: str, delay_seconds: float) -> None:
        self.is_closed = False
        self._tasks = tasks
        self._scenario = scenario
        self._delay_seconds = delay_seconds
        self._attempts: dict[int, int] = {}
        self.retry_attempts = 0

    async def get(self, url: str, **_kwargs) -> httpx.Response:
        task_id = int(url.rsplit("/", 1)[-1])
        await asyncio.sleep(self._delay_seconds)
        attempt = self._attempts.get(task_id, 0) + 1
        self._attempts[task_id] = attempt
        retry = self._scenario == "retry_10pct" and self._tasks[task_id]["retry_first"] and attempt == 1
        if retry:
            self.retry_attempts += 1
        request = httpx.Request("GET", url)
        return httpx.Response(503 if retry else 200, request=request)


class BenchmarkCrawler(BaseCrawler):
    def __init__(self, client: FakeClient, workload: dict, task: dict, scenario: str) -> None:
        super().__init__()
        self._client = client  # type: ignore[assignment]
        self._workload = workload
        self._task = task
        self._scenario = scenario

    async def crawl(self, keyword: str, max_items: int = 100) -> list[RawDiscussionItem]:
        del keyword, max_items
        await self._request_with_retry(
            "get",
            f"https://fake.test/request/{self._task['id']}",
            max_retries=3,
            base_delay=0.001,
        )
        return render_items(self._workload, self._task, self._scenario)


def percentile(sorted_values: list[float], quantile: float) -> float:
    if not sorted_values:
        return 0.0
    return sorted_values[int((len(sorted_values) - 1) * quantile)]


async def run_benchmark(
    workload: dict,
    *,
    scenario: str,
    task_count: int,
    concurrency: int,
    delay_seconds: float = 0.005,
) -> dict:
    validate_workload(workload)
    if scenario not in SCENARIOS:
        raise ValueError(f"unsupported scenario: {scenario}")
    if not 1 <= task_count <= workload["task_count"]:
        raise ValueError("task_count is outside the workload")
    if concurrency < 1:
        raise ValueError("concurrency must be positive")
    settings.crawler_min_request_interval_seconds = 0

    tasks = workload["tasks"][:task_count]
    task_by_id = {task["id"]: task for task in tasks}
    client = FakeClient(task_by_id, scenario, delay_seconds)
    crawlers = {task["id"]: BenchmarkCrawler(client, workload, task, scenario) for task in tasks}
    release = asyncio.Event()
    ready = asyncio.Event()
    ready_count = 0
    ready_target = min(task_count, concurrency)
    release_time = 0.0

    async def collect(task: dict) -> tuple[bool, int, int, float]:
        nonlocal ready_count
        ready_count += 1
        if ready_count == ready_target:
            ready.set()
        await release.wait()
        try:
            items = await crawlers[task["id"]].crawl("benchmark", workload["items_per_task"])
            unique, duplicates = deduplicate_items(items)
            return True, duplicates, len(unique), time.perf_counter()
        except Exception:
            return False, 0, 0, time.perf_counter()

    pending = asyncio.create_task(run_bounded(tasks, collect, concurrency))
    await ready.wait()
    release_time = time.perf_counter()
    release.set()
    results = await pending
    wall_seconds = time.perf_counter() - release_time
    latencies = sorted((finished - release_time) * 1000 for _, _, _, finished in results)
    completed = sum(success for success, _, _, _ in results)
    failed = task_count - completed
    result = {
        "implementation": "python",
        "scenario": scenario,
        "task_count": task_count,
        "concurrency": concurrency,
        "fake_latency_ms": delay_seconds * 1000,
        "retry_backoff_ms": 1,
        "max_attempts": 3,
        "items_per_task": workload["items_per_task"],
        "wall_seconds": wall_seconds,
        "throughput_tasks_per_second": task_count / wall_seconds,
        "p50_latency_ms": percentile(latencies, 0.50),
        "p95_latency_ms": percentile(latencies, 0.95),
        "p99_latency_ms": percentile(latencies, 0.99),
        "completed_tasks": completed,
        "failed_tasks": failed,
        "retry_attempts": client.retry_attempts,
        "duplicate_count": sum(duplicates for _, duplicates, _, _ in results),
        "unique_result_count": sum(unique for _, _, unique, _ in results),
        "python_version": platform.python_version(),
        "architecture": platform.machine(),
    }
    validate_result(workload, result, task_count=task_count)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the deterministic Python collector scheduler benchmark")
    parser.add_argument("--workload", type=Path, required=True)
    parser.add_argument("--scenario", choices=SCENARIOS, required=True)
    parser.add_argument("--tasks", type=int, required=True)
    parser.add_argument("--concurrency", type=int, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logger.remove()
    workload = json.loads(args.workload.read_text(encoding="utf-8"))
    try:
        result = asyncio.run(
            run_benchmark(
                workload,
                scenario=args.scenario,
                task_count=args.tasks,
                concurrency=args.concurrency,
            )
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
