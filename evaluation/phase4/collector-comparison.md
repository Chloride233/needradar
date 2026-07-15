# Python vs Go collector scheduler comparison

Experiment: `needradar-collector-scheduler-v2-20260715`
Manifest SHA-256: `9b7b0472d1b9580b2d98d3fd5e51ca4f1b71b9fdd08590d99466ba18ba303f8a`
Runs SHA-256: `a676458721c8b6665ec336778841f1abf14edea3c84eee9b869b9125161d75d3`
Startup runs SHA-256: `f020ffb861982bee88d621e253529b6a3a237255941f99e604ef264bfb0465c6`

All combinations passed exact completed, failed, retry, duplicate, and unique-result parity.
Medians below use five measured runs; JSON retains min and max for every metric.

| Scenario | C | Impl | Tasks/s | P50 ms | P95 ms | P99 ms | User CPU s | Sys CPU s | Peak RSS MiB |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| normal | 1 | python | 164.79 | 3017.49 | 5761.27 | 6006.55 | 0.680 | 0.050 | 76.23 |
| normal | 1 | go | 175.58 | 2848.46 | 5411.98 | 5638.65 | 0.130 | 0.030 | 24.20 |
| normal | 4 | python | 614.89 | 789.53 | 1530.80 | 1595.56 | 0.440 | 0.040 | 76.27 |
| normal | 4 | go | 704.29 | 710.83 | 1351.88 | 1408.48 | 0.080 | 0.020 | 24.89 |
| normal | 16 | python | 2158.89 | 223.96 | 442.56 | 456.67 | 0.380 | 0.040 | 76.34 |
| normal | 16 | go | 2822.09 | 180.43 | 337.40 | 348.73 | 0.050 | 0.010 | 25.83 |
| normal | 50 | python | 5534.36 | 92.51 | 171.56 | 179.89 | 0.370 | 0.040 | 76.31 |
| normal | 50 | go | 8838.35 | 56.92 | 107.43 | 113.08 | 0.040 | 0.000 | 26.34 |
| retry_10pct | 1 | python | 148.07 | 3379.52 | 6425.47 | 6686.19 | 0.660 | 0.050 | 76.25 |
| retry_10pct | 1 | go | 156.98 | 3186.98 | 6052.03 | 6306.60 | 0.120 | 0.040 | 24.44 |
| retry_10pct | 4 | python | 575.74 | 858.21 | 1644.77 | 1716.95 | 0.480 | 0.050 | 76.03 |
| retry_10pct | 4 | go | 647.56 | 770.93 | 1463.04 | 1526.37 | 0.080 | 0.020 | 25.23 |
| retry_10pct | 16 | python | 1987.44 | 242.91 | 473.83 | 495.15 | 0.370 | 0.030 | 76.34 |
| retry_10pct | 16 | go | 2571.67 | 194.17 | 365.58 | 382.10 | 0.050 | 0.010 | 26.08 |
| retry_10pct | 50 | python | 5261.13 | 93.92 | 175.52 | 183.56 | 0.320 | 0.030 | 76.41 |
| retry_10pct | 50 | go | 7818.79 | 61.81 | 115.89 | 121.37 | 0.040 | 0.010 | 26.23 |
| duplicate_10pct | 1 | python | 165.43 | 2995.05 | 5734.14 | 5982.07 | 0.640 | 0.060 | 76.33 |
| duplicate_10pct | 1 | go | 175.60 | 2848.57 | 5409.03 | 5636.98 | 0.130 | 0.030 | 24.38 |
| duplicate_10pct | 4 | python | 605.46 | 815.21 | 1573.81 | 1637.64 | 0.500 | 0.040 | 76.28 |
| duplicate_10pct | 4 | go | 701.33 | 711.62 | 1357.81 | 1414.38 | 0.080 | 0.020 | 24.94 |
| duplicate_10pct | 16 | python | 2239.01 | 217.63 | 422.08 | 439.19 | 0.380 | 0.030 | 76.23 |
| duplicate_10pct | 16 | go | 2785.82 | 181.15 | 341.83 | 353.28 | 0.060 | 0.010 | 25.98 |
| duplicate_10pct | 50 | python | 5732.26 | 86.33 | 165.23 | 173.68 | 0.320 | 0.030 | 76.27 |
| duplicate_10pct | 50 | go | 8911.08 | 56.74 | 106.70 | 112.17 | 0.040 | 0.000 | 25.83 |

## Go relative to Python

| Scenario | C | Throughput change | P50 reduction | P95 reduction | P99 reduction | RSS reduction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| normal | 1 | 6.55% | 5.60% | 6.06% | 6.13% | 68.25% |
| normal | 4 | 14.54% | 9.97% | 11.69% | 11.73% | 67.36% |
| normal | 16 | 30.72% | 19.44% | 23.76% | 23.64% | 66.17% |
| normal | 50 | 59.70% | 38.47% | 37.38% | 37.14% | 65.48% |
| retry_10pct | 1 | 6.02% | 5.70% | 5.81% | 5.68% | 67.95% |
| retry_10pct | 4 | 12.47% | 10.17% | 11.05% | 11.10% | 66.81% |
| retry_10pct | 16 | 29.40% | 20.07% | 22.85% | 22.83% | 65.84% |
| retry_10pct | 50 | 48.61% | 34.19% | 33.97% | 33.88% | 65.66% |
| duplicate_10pct | 1 | 6.15% | 4.89% | 5.67% | 5.77% | 68.07% |
| duplicate_10pct | 4 | 15.83% | 12.71% | 13.72% | 13.63% | 67.31% |
| duplicate_10pct | 16 | 24.42% | 16.76% | 19.01% | 19.56% | 65.92% |
| duplicate_10pct | 50 | 55.45% | 34.27% | 35.42% | 35.42% | 66.13% |

## Independent process startup

This is a separate five-run runner help-path probe. It includes runtime startup, imports, flag parsing, output, and exit; it is not included in steady-state task latency.

| Impl | Wall median ms | Wall min ms | Wall max ms | User CPU s | Sys CPU s | Peak RSS MiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| python | 291.02 | 270.43 | 540.73 | 0.240 | 0.030 | 74.09 |
| go | 7.96 | 6.25 | 11.12 | 0.000 | 0.000 | 10.23 |

## Variation and negative cases

Worst five-run min/max spread relative to the median:

| Metric | Python | Go |
| --- | ---: | ---: |
| throughput_tasks_per_second | 27.96% (duplicate_10pct, C=50) | 2.63% (duplicate_10pct, C=16) |
| p95_latency_ms | 27.34% (normal, C=50) | 2.68% (duplicate_10pct, C=16) |
| peak_rss_bytes | 1.00% (normal, C=50) | 5.78% (retry_10pct, C=50) |

Negative primary comparison cases: 0.

## Scope and interpretation

- Unit: in-process collection task scheduling with deterministic fake I/O, request retry, and task-local fingerprint deduplication.
- Throughput and latency exclude process startup; CPU and peak RSS cover each independently measured process.
- Task latency starts at the shared queue release and therefore includes equivalent queue waiting.
- Positive reduction means Go used less latency or RSS; negative values are regressions.
- Process wall minus internal wall is retained per raw record as startup/import/exit overhead, not task latency.

## Resume-safe evidence

On this frozen local 1000-task, 5 ms fake-I/O scheduler slice, Go throughput changed by 6.02% to 59.70%, P95 latency changed by 5.67% to 37.38%, and process peak RSS changed by 65.48% to 68.25% relative to Python. Any resume claim must keep the local deterministic, task-count, fake-latency, and concurrency qualifiers.

## Claims not supported

This experiment does not establish real-platform throughput, production SLA, whole-pipeline speedup, SQLite/Vault/LLM performance, or long-running service stability.

## Environment

- OS: macOS-26.5.2-arm64-arm-64bit-Mach-O
- Architecture: arm64
- CPU: Apple M4
- Python: 3.14.6
- Go: go version go1.26.5 darwin/arm64
- GOMAXPROCS: 10
