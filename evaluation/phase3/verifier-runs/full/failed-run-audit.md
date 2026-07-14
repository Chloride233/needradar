# Phase 3 verifier failed-run audit

## Decision

This run is rejected as component-ablation evidence. It is retained as reproducible failure evidence.

## Stage coverage

| Stage | Success | Failed |
| --- | ---: | ---: |
| `claim_extraction` | 2 | 28 |
| `fact_check` | 26 | 4 |
| `consistency` | 25 | 5 |

## Extraction failure

- LLM-only claims: 0 across 30 reports.
- Valid non-empty LLM records: 0.
- Failure kinds: `{"empty_or_malformed_json": 24, "provider_error": 1, "quote_offset_mismatch": 3}`.
- Naturalistic coverage: 0 hybrid claims across 12 reports.

## Diagnostic only

The non-empty rule-fallback subset contains 15 reports; AUROC is 0.482143 and average precision is 0.553236. These values are not hybrid verifier results.

## Cost correction

- Provider attempts: 114.
- Responses with usage: 113.
- Structural artifact reuse: 450 calls.
- Calls skipped because claims were empty: 36.
- Recorded provider cost lower bound: CNY 0.203212.

## Frozen artifacts

- `predictions.jsonl`: `08750c890c36836e3d6899bb1117ed6a458c7a5ffd259d43f5a9490e0155a098`
- `metrics.json`: `0276ff9552b506bb9711adf901248ed0a735260b46a805fd9c30a94d5ca58a61`
- `run.json`: `7587ac417a3917a9d52cf14e488d0e2237a8fa00001208a9cdf59815f941f4bf`

## Recovery

- disable provider thinking for structured verifier calls.
- derive quote offsets locally and cap hybrid claims at 12.
- exclude failed dependencies from downstream scores and report valid denominators.
- write a new schema-v2 run instead of resuming this directory.
