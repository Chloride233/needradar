# Python vs Go collector scheduler comparison

Experiment: `needradar-collector-scheduler-v1-20260715`
Manifest SHA-256: `ec61ad74c6382e7d1e952fe975ed1c0a60fc181e362606dc9966b1cea55522ee`
Runs SHA-256: `efe68548b5dd4a78c791164b15f217db19e3b991f9c705a52018e021f61549ca`

All combinations passed exact completed, failed, retry, duplicate, and unique-result parity.
Medians below use five measured runs; JSON retains min and max for every metric.

| Scenario | C | Impl | Tasks/s | P50 ms | P95 ms | P99 ms | User CPU s | Sys CPU s | Peak RSS MiB |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| normal | 1 | python | 151.96 | 3292.73 | 6251.93 | 6512.29 | 0.680 | 0.050 | 76.14 |
| normal | 1 | go | 160.97 | 3109.76 | 5901.23 | 6149.29 | 0.140 | 0.030 | 24.22 |
| normal | 4 | python | 577.76 | 895.54 | 1650.74 | 1716.79 | 0.440 | 0.040 | 76.25 |
| normal | 4 | go | 645.63 | 774.72 | 1474.46 | 1537.17 | 0.080 | 0.020 | 25.17 |
| normal | 16 | python | 2002.55 | 250.27 | 477.21 | 492.16 | 0.350 | 0.030 | 76.17 |
| normal | 16 | go | 2552.25 | 199.90 | 372.88 | 385.47 | 0.060 | 0.010 | 26.06 |
| normal | 50 | python | 5223.92 | 93.54 | 181.59 | 190.59 | 0.300 | 0.030 | 76.19 |
| normal | 50 | go | 8152.45 | 61.70 | 116.03 | 122.50 | 0.040 | 0.000 | 26.39 |
| retry_10pct | 1 | python | 136.17 | 3667.09 | 6980.06 | 7267.69 | 0.720 | 0.050 | 76.08 |
| retry_10pct | 1 | go | 144.11 | 3478.75 | 6594.34 | 6874.25 | 0.150 | 0.040 | 24.08 |
| retry_10pct | 4 | python | 525.52 | 962.09 | 1801.06 | 1879.42 | 0.500 | 0.040 | 76.23 |
| retry_10pct | 4 | go | 593.97 | 842.89 | 1597.04 | 1664.38 | 0.090 | 0.020 | 25.03 |
| retry_10pct | 16 | python | 1849.67 | 270.43 | 507.82 | 531.58 | 0.370 | 0.030 | 76.31 |
| retry_10pct | 16 | go | 2405.03 | 207.91 | 390.31 | 408.26 | 0.050 | 0.010 | 25.39 |
| retry_10pct | 50 | python | 4751.31 | 99.91 | 194.61 | 203.38 | 0.310 | 0.030 | 76.28 |
| retry_10pct | 50 | go | 7220.85 | 66.20 | 125.24 | 131.15 | 0.040 | 0.010 | 26.31 |
| duplicate_10pct | 1 | python | 152.16 | 3258.86 | 6241.04 | 6507.52 | 0.660 | 0.050 | 76.17 |
| duplicate_10pct | 1 | go | 161.29 | 3098.45 | 5888.64 | 6134.65 | 0.110 | 0.030 | 23.59 |
| duplicate_10pct | 4 | python | 575.90 | 859.48 | 1651.31 | 1722.65 | 0.480 | 0.040 | 76.19 |
| duplicate_10pct | 4 | go | 641.56 | 774.51 | 1482.89 | 1545.28 | 0.090 | 0.020 | 25.20 |
| duplicate_10pct | 16 | python | 1994.05 | 239.56 | 473.59 | 493.24 | 0.370 | 0.030 | 76.30 |
| duplicate_10pct | 16 | go | 2557.10 | 199.16 | 371.97 | 384.75 | 0.060 | 0.010 | 25.95 |
| duplicate_10pct | 50 | python | 5261.15 | 93.30 | 180.19 | 189.23 | 0.300 | 0.030 | 76.28 |
| duplicate_10pct | 50 | go | 8123.60 | 61.29 | 116.87 | 123.05 | 0.040 | 0.000 | 25.86 |

## Go relative to Python

| Scenario | C | Throughput change | P50 reduction | P95 reduction | P99 reduction | RSS reduction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| normal | 1 | 5.93% | 5.56% | 5.61% | 5.57% | 68.19% |
| normal | 4 | 11.75% | 13.49% | 10.68% | 10.46% | 66.99% |
| normal | 16 | 27.45% | 20.13% | 21.86% | 21.68% | 65.78% |
| normal | 50 | 56.06% | 34.04% | 36.11% | 35.73% | 65.36% |
| retry_10pct | 1 | 5.83% | 5.14% | 5.53% | 5.41% | 68.35% |
| retry_10pct | 4 | 13.02% | 12.39% | 11.33% | 11.44% | 67.17% |
| retry_10pct | 16 | 30.03% | 23.12% | 23.14% | 23.20% | 66.73% |
| retry_10pct | 50 | 51.98% | 33.74% | 35.64% | 35.52% | 65.51% |
| duplicate_10pct | 1 | 6.00% | 4.92% | 5.65% | 5.73% | 69.03% |
| duplicate_10pct | 4 | 11.40% | 9.89% | 10.20% | 10.30% | 66.92% |
| duplicate_10pct | 16 | 28.24% | 16.86% | 21.46% | 21.99% | 65.98% |
| duplicate_10pct | 50 | 54.41% | 34.31% | 35.14% | 34.97% | 66.10% |

## Scope and interpretation

- Unit: in-process collection task scheduling with deterministic fake I/O, request retry, and task-local fingerprint deduplication.
- Throughput and latency exclude process startup; CPU and peak RSS cover each independently measured process.
- Task latency starts at the shared queue release and therefore includes equivalent queue waiting.
- Positive reduction means Go used less latency or RSS; negative values are regressions.
- Process wall minus internal wall is retained per raw record as startup/import/exit overhead, not task latency.

## Resume-safe evidence

The frozen local result covers 1000 tasks, 5 ms fake I/O, 1 ms retry backoff, and the listed concurrency levels. Any resume claim must keep those qualifiers.

## Claims not supported

This experiment does not establish real-platform throughput, production SLA, whole-pipeline speedup, SQLite/Vault/LLM performance, or long-running service stability.

## Environment

- OS: macOS-26.5.2-arm64-arm-64bit-Mach-O
- Architecture: arm64
- CPU: Apple M4
- Python: 3.14.6
- Go: go version go1.26.5 darwin/arm64
- GOMAXPROCS: 10
