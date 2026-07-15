# NeedRadar Go Collector

This service owns concurrent collection, bounded task scheduling, per-platform
rate limiting, bounded HTTP retries, task-local deduplication, task state, SSE
progress, health, and runtime metrics for GitHub, Stack Overflow, and Juejin.
Python remains responsible for the SQLite task record, incremental fingerprint
history, Vault writes, LLM extraction, RAG, reports, and verification.

The service uses only the Go standard library. Its task store is process-local:
restarting the service loses Go task history, while the canonical Python
`CrawlTask` rows remain in SQLite and can be retried through the existing API.

## Start

```bash
cd services/collector-go
go run ./cmd/collector
curl http://127.0.0.1:8910/health
```

Useful environment variables:

```text
COLLECTOR_ADDR=127.0.0.1:8910
COLLECTOR_CONCURRENCY=4
COLLECTOR_QUEUE_SIZE=100
COLLECTOR_RATE_LIMIT=500ms
COLLECTOR_REQUEST_TIMEOUT=30s
COLLECTOR_GITHUB_URL=<override for fake provider>
COLLECTOR_STACKOVERFLOW_URL=<override for fake provider>
COLLECTOR_JUEJIN_URL=<override for fake provider>
```

## API

```bash
curl -X POST http://127.0.0.1:8910/v1/tasks \
  -H 'Content-Type: application/json' \
  -d '{"keyword":"context","platforms":["github"],"max_items":10,"task_ids":{"github":123}}'
curl http://127.0.0.1:8910/v1/tasks/123
curl -N http://127.0.0.1:8910/v1/tasks/123/events
curl -X POST http://127.0.0.1:8910/v1/tasks/123/retry
curl -X POST http://127.0.0.1:8910/v1/tasks/123/cancel
curl http://127.0.0.1:8910/metrics
```

Only failed tasks can be retried. A retry reuses the same task ID. Cancellation
uses the existing `failed` task status with `error_message="cancelled"` because
the Python task contract has no separate cancelled status.

## Python Integration

Python collection remains the default. Opt in locally with:

```bash
NR_COLLECTOR_BACKEND=go \
NR_COLLECTOR_GO_URL=http://127.0.0.1:8910 \
.venv/bin/python -m needradar.cli run "context"
```

`NR_COLLECTOR_GO_FALLBACK_TO_PYTHON=true` is the default. Set it to `false` to
surface Go collector failures instead of running the existing Python crawler.

## Verify

```bash
cd services/collector-go
gofmt -w .
go test ./...
go test -race ./...
go vet ./...
go test -run TestFakeProviderEndToEnd -v ./internal/collector

cd ../..
PYTHONPATH=src .venv/bin/python -m pytest -q \
  tests/unit/test_go_collector.py \
  tests/unit/test_analysis_service.py \
  tests/integration/test_tasks_api.py
```

The fake-provider integration test starts local HTTP upstreams for all three
platform adapters and a local collector HTTP server. It does not use public
network access, credentials, SQLite, the Vault, or a model provider.

## Benchmark

```bash
cd ../..
PYTHONPATH=src .venv/bin/python scripts/run_collector_comparison.py --report-only
```

`--report-only` verifies and exactly rebuilds the checked-in artifacts without
rerunning measurements. To repeat the experiment, use a disposable copy after
preserving the existing `evaluation/phase4/collector-comparison*` artifacts,
then run:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_collector_comparison.py --prepare
PYTHONPATH=src .venv/bin/python scripts/run_collector_comparison.py --quick
PYTHONPATH=src .venv/bin/python scripts/run_collector_comparison.py --formal
```

The formal command intentionally refuses to overwrite an existing experiment.

The comparison freezes one shared workload and runs the production Python and
Go scheduling, request-retry, and task-local fingerprint-deduplication
primitives against equivalent 5 ms fake I/O. Formal runs use prebuilt Go code,
fixed-seed language interleaving, and `/usr/bin/time -l` for both independent
processes. Reports are written under `evaluation/phase4/` only after exact
completed, failed, retry, duplicate, and unique-result parity is verified.
Runner startup is measured separately through five interleaved help-path
processes per language and is not mixed into steady-state task latency.

This measures a local collection scheduling slice. It does not compare the
Python SQLite, Vault, LLM, RAG, report, or verification pipeline, and it does
not establish real-platform throughput or a production SLA.
