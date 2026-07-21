# Python vs Go collector scheduler comparison

Experiment: `needradar-collector-scheduler-v3-20260715`
Manifest SHA-256: `5624df4ca5c2f78ecb2c238ecbae25c136bf24422feb42e2c9d6944ba02f9e4f`
Runs SHA-256: `d58cab9d7988fd38736cebc606628b60a248f1a5b58c09e1c1d94b97be8ee1c3`
Startup runs SHA-256: `6f16bdbdc8367409c389aa9374dc45a08c92bd9aa1ee0c61f765683ecdc6c89c`

All combinations passed exact completed, failed, retry, duplicate, and unique-result parity.
Medians below use five measured runs; JSON retains min and max for every metric.

| Scenario | C | Impl | Tasks/s | P50 ms | P95 ms | P99 ms | User CPU s | Sys CPU s | Peak RSS MiB |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| normal | 1 | python | 167.64 | 2960.30 | 5664.13 | 5904.67 | 0.590 | 0.060 | 76.27 |
| normal | 1 | go | 175.99 | 2841.37 | 5395.50 | 5624.98 | 0.100 | 0.030 | 24.33 |
| normal | 4 | python | 617.32 | 787.25 | 1545.18 | 1607.66 | 0.480 | 0.050 | 76.27 |
| normal | 4 | go | 703.14 | 712.82 | 1354.16 | 1410.70 | 0.080 | 0.020 | 24.95 |
| normal | 16 | python | 2266.47 | 222.06 | 422.80 | 435.27 | 0.380 | 0.040 | 76.25 |
| normal | 16 | go | 2802.14 | 181.55 | 339.64 | 351.16 | 0.050 | 0.010 | 25.55 |
| normal | 50 | python | 5657.66 | 88.80 | 167.77 | 175.99 | 0.320 | 0.030 | 76.42 |
| normal | 50 | go | 8865.65 | 56.48 | 107.09 | 112.73 | 0.040 | 0.000 | 26.47 |
| retry_10pct | 1 | python | 149.39 | 3334.11 | 6365.04 | 6628.01 | 0.590 | 0.070 | 76.25 |
| retry_10pct | 1 | go | 157.11 | 3175.17 | 6046.91 | 6301.93 | 0.100 | 0.030 | 24.45 |
| retry_10pct | 4 | python | 579.03 | 850.26 | 1632.87 | 1704.36 | 0.510 | 0.040 | 76.23 |
| retry_10pct | 4 | go | 646.62 | 770.91 | 1467.24 | 1528.14 | 0.080 | 0.020 | 24.91 |
| retry_10pct | 16 | python | 1988.77 | 238.68 | 473.29 | 494.82 | 0.410 | 0.040 | 76.12 |
| retry_10pct | 16 | go | 2574.89 | 193.76 | 364.91 | 381.56 | 0.050 | 0.010 | 25.48 |
| retry_10pct | 50 | python | 5114.70 | 94.40 | 180.43 | 188.99 | 0.330 | 0.030 | 76.34 |
| retry_10pct | 50 | go | 7772.96 | 61.65 | 116.56 | 122.04 | 0.040 | 0.010 | 25.88 |
| duplicate_10pct | 1 | python | 168.18 | 2960.13 | 5646.43 | 5883.65 | 0.580 | 0.060 | 76.23 |
| duplicate_10pct | 1 | go | 175.55 | 2848.93 | 5412.63 | 5640.55 | 0.110 | 0.030 | 23.97 |
| duplicate_10pct | 4 | python | 632.06 | 790.73 | 1508.10 | 1569.79 | 0.440 | 0.040 | 76.16 |
| duplicate_10pct | 4 | go | 706.18 | 705.48 | 1347.87 | 1404.54 | 0.070 | 0.020 | 24.75 |
| duplicate_10pct | 16 | python | 2155.46 | 223.74 | 439.69 | 456.74 | 0.380 | 0.030 | 76.28 |
| duplicate_10pct | 16 | go | 2803.24 | 181.13 | 339.81 | 351.41 | 0.050 | 0.010 | 26.00 |
| duplicate_10pct | 50 | python | 5610.31 | 88.48 | 168.93 | 177.44 | 0.310 | 0.030 | 76.28 |
| duplicate_10pct | 50 | go | 8809.20 | 56.79 | 107.46 | 113.17 | 0.040 | 0.000 | 26.55 |

## Go relative to Python

| Scenario | C | Throughput change | P50 reduction | P95 reduction | P99 reduction | RSS reduction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| normal | 1 | 4.99% | 4.02% | 4.74% | 4.74% | 68.10% |
| normal | 4 | 13.90% | 9.45% | 12.36% | 12.25% | 67.28% |
| normal | 16 | 23.63% | 18.24% | 19.67% | 19.32% | 66.50% |
| normal | 50 | 56.70% | 36.40% | 36.16% | 35.95% | 65.36% |
| retry_10pct | 1 | 5.16% | 4.77% | 5.00% | 4.92% | 67.93% |
| retry_10pct | 4 | 11.67% | 9.33% | 10.14% | 10.34% | 67.33% |
| retry_10pct | 16 | 29.47% | 18.82% | 22.90% | 22.89% | 66.52% |
| retry_10pct | 50 | 51.97% | 34.69% | 35.40% | 35.43% | 66.11% |
| duplicate_10pct | 1 | 4.38% | 3.76% | 4.14% | 4.13% | 68.56% |
| duplicate_10pct | 4 | 11.73% | 10.78% | 10.62% | 10.53% | 67.50% |
| duplicate_10pct | 16 | 30.05% | 19.05% | 22.72% | 23.06% | 65.92% |
| duplicate_10pct | 50 | 57.02% | 35.82% | 36.39% | 36.22% | 65.20% |

## Independent process startup

This is a separate five-run runner help-path probe. It includes runtime startup, imports, flag parsing, output, and exit; it is not included in steady-state task latency.

| Impl | Wall median ms | Wall min ms | Wall max ms | User CPU s | Sys CPU s | Peak RSS MiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| python | 295.55 | 267.23 | 341.39 | 0.250 | 0.030 | 73.92 |
| go | 6.97 | 6.33 | 605.49 | 0.000 | 0.000 | 10.31 |

## Variation and negative cases

Worst five-run min/max spread relative to the median:

| Metric | Python | Go |
| --- | ---: | ---: |
| throughput_tasks_per_second | 43.79% (normal, C=50) | 6.87% (normal, C=50) |
| p95_latency_ms | 53.48% (normal, C=50) | 8.06% (normal, C=50) |
| peak_rss_bytes | 0.82% (retry_10pct, C=16) | 7.03% (retry_10pct, C=1) |

Negative primary comparison cases: 0.

## Scope and interpretation

- Unit: in-process collection task scheduling with deterministic fake I/O, request retry, and task-local fingerprint deduplication.
- Throughput and latency exclude process startup; CPU and peak RSS cover each independently measured process.
- Task latency starts at the shared queue release and therefore includes equivalent queue waiting.
- Positive reduction means Go used less latency or RSS; negative values are regressions.
- Process wall minus internal wall is retained per raw record as startup/import/exit overhead, not task latency.

## Resume-safe evidence

On this frozen local 1000-task, 5 ms fake-I/O scheduler slice, Go throughput changed by 4.38% to 57.02%, P95 latency changed by 4.14% to 36.39%, and process peak RSS changed by 65.20% to 68.56% relative to Python. Any resume claim must keep the local deterministic, task-count, fake-latency, and concurrency qualifiers.

## Claims not supported

This experiment does not establish real-platform throughput, production SLA, whole-pipeline speedup, SQLite/Vault/LLM performance, or long-running service stability.

## Environment

- OS: macOS-26.5.2-arm64-arm-64bit-Mach-O
- Architecture: arm64
- CPU: Apple M4
- Python: 3.14.6
- Go: go version go1.26.5 darwin/arm64
- GOMAXPROCS: 10
