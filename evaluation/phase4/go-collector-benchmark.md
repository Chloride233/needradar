# Go collector local benchmark

## Scope

This is a fixed-concurrency scheduler benchmark using a deterministic in-process
fake platform. Each task waits 5 ms and returns one unique item. It does not use
public network access, credentials, SQLite, the Vault, or model providers.

## Reproduce

```bash
cd services/collector-go
go run ./cmd/collector-bench -tasks 200 -concurrency 4 -latency 5ms
```

## Environment

- Date: 2026-07-15 (Asia/Shanghai)
- OS/kernel: Darwin 25.5.0, arm64
- Go: 1.26.5 darwin/arm64
- `GOMAXPROCS`: 10

## Result

| Tasks | Workers | Failures | Throughput | P50 | P95 | Peak sampled heap |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 200 | 4 | 0 | 796.413 tasks/s | 125.542 ms | 240.995 ms | 850,928 bytes |

The latency percentiles include queue wait, so later tasks reflect the bounded
four-worker schedule. The sampled heap and allocation deltas describe this one
local process run, not a production memory limit. There is no equivalent Python
benchmark in this experiment, so the result cannot support a claim that Go is
faster or uses less memory than Python. Public provider latency, quotas, and
long-running stability remain unverified by this benchmark.
