# Phase 4 Stability Observation Protocol

Date: 2026-07-14

## Purpose and Boundary

This protocol measures collection availability and response shape without
running extraction, report generation, verification, or any LLM call. The
runner is dry-run by default. A real execution requires both `--execute` and
`--external-approved`, plus a separate user approval for the exact request
scope.

## Proposed Dry-Run Scope

```bash
PYTHONPATH=src .venv/bin/python scripts/run_phase4_stability.py "AI tools" \
  --platforms github,stackoverflow,juejin --runs 3 --max-items 20
```

The dry-run above plans nine public requests and prints the declared data
boundary. It does not instantiate a crawler or make a network request.

## Real Execution Gate

Before adding `--execute --external-approved`, record the approved keyword,
platforms, number of runs, maximum items, time window, and whether any API key
is involved. The executor runs sequentially so the shared crawler rate limit
remains in force.

The JSON output stores only platform, run number, success/failure, elapsed
seconds, item counts, duplicate counts, and error type. It deliberately omits
URLs, titles, discussion content, authors, and tags.

## Metrics

For each platform, report attempts, successes, success rate, median elapsed
seconds, item count, duplicate count, and error-type counts. These are
observational metrics for the approved window, not a general uptime claim.
