# Phase 4 Deterministic Collection Baseline

Date: 2026-07-14

## Scope

This is the first Phase 4 implementation slice for Issue #3. It establishes
deterministic collection behavior using fake HTTP responses, fake crawlers,
and the test SQLite database. It makes no claim about external platform
availability, paid-model cost, or real-user adoption.

## Covered behavior

| Capability | Deterministic evidence |
| --- | --- |
| Failure recovery | Request-level retries in `BaseCrawler` are bounded to three attempts and apply only to 429, 5xx, network errors, and timeouts; the pipeline does not multiply that budget. A failed task can be resumed atomically through `POST /api/v1/tasks/{task_id}/retry` without creating a second task row or duplicate execution. |
| Rate limiting | Every shared HTTP request observes `NR_CRAWLER_MIN_REQUEST_INTERVAL_SECONDS` (default 0.5) before dispatch, including retried requests. |
| Incremental update | Previously stored source URLs are skipped for the same keyword and platform. |
| Fingerprint deduplication | SHA-256 of normalized title and content prevents duplicate processing when the same discussion is returned at another URL, including within one crawl batch. |
| Usage and budget report | `/api/v1/usage/budget` returns daily/monthly input, output, cached and total tokens, spent CNY, percentage used, and warning/exceeded alerts at `NR_BUDGET_ALERT_THRESHOLD_PERCENT` (default 80). Existing summary and model-stat endpoints remain the model-fee breakdown. |
| User-study ledger | A de-identified CSV template and local validator report elapsed time, edits, considered/adopted insights, and failure points without recording a participant identity or report content. |
| Stability runner | A dry-run public-platform observation plan fixes request count and aggregate-only result fields; real execution requires explicit double opt-in. |
| Python/Go scheduler comparison | A shared 1,000-task fake workload freezes 5 ms I/O, retry, payload, fingerprint, queue-release latency, and concurrency semantics. The 192-run formal matrix and OS-level CPU/RSS samples are recorded in `collector-comparison-runs.jsonl`; 10 separate runner help-path startup measurements are recorded in `collector-comparison-startup-runs.jsonl`. `collector-comparison.md` reports only combinations with exact logical parity and an unpolluted user-workload gate. |

## Reproduce

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q \
  tests/unit/test_crawl_reliability.py \
  tests/unit/test_base_crawler.py \
  tests/unit/test_analysis_service.py \
  tests/unit/test_usage_service.py \
  tests/integration/test_tasks_api.py
```

The command performs no network request, paid model call, or user-data
collection. It tests the recovery and non-retry branches, rate-limit wait,
URL/content/batch deduplication, task requeue, and warning/exceeded budget
thresholds.

To verify the frozen Python/Go comparison without rerunning measurements:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_collector_comparison.py --report-only
```

To validate an empty study ledger without recruiting anyone:

```bash
PYTHONPATH=src .venv/bin/python scripts/report_phase4_user_study.py \
  evaluation/phase4/user-study-template.csv \
  /tmp/needradar-phase4-empty-summary.json
```

## Boundaries for Later Phase 4 Work

The remaining Issue #3 acceptance items require separately approved work:
real platform stability evidence, real model-cost data, consented user task
timing, human edits, adoption outcomes, and a feedback-driven iteration.
