# NeedRadar Top-3 Pilot Review Design

## Goal

Replace the 2,000-candidate comprehensive qrels workload with a sequential, decision-focused pilot that measures the actual production surface: which three contexts enter RAG.

The first batch reviews 30 frozen test queries. For each query, the blind pool is the deduplicated union of the no-rerank, BGE, and Qwen3 Top 3 results. The pool therefore contains at most nine candidates per query and is expected to contain roughly 210 to 240 candidates in total. A deterministic 10% hidden test-retest sample remains required.

This pilot may support a qualified internal model-selection decision. It does not support claims about complete Top-20 qrels, MRR@10, nDCG@10, or full candidate recall.

## Query Sample

Only the frozen `test` split is eligible. The current eligible population contains 65 queries: 21 GitHub, 22 StackOverflow, and 22 Juejin queries.

Batch 1 contains 30 queries. Sampling is deterministic and proportional across the cross-product of:

- platform;
- query language (`non_cjk`, `mixed`, `cjk`).

Each non-empty stratum receives its largest-remainder proportional quota. Queries inside a stratum are ordered by SHA-256 of `(candidate_snapshot_sha256, batch_number, query_id)`. Remaining quota ties are resolved by the stable stratum name. The selected IDs and selection SHA-256 are written before any provider call.

If Batch 1 is inconclusive, Batch 2 adds 20 previously unselected test queries. Its quotas are calculated from the remaining eligible population, so Batch 1 never changes and the cumulative sample is exactly 50 queries. No third automatic batch is in scope.

## Paid Execution Boundary

Batch 1 makes at most 60 provider requests: the same 30 frozen queries sent once to each exact model.

- `BAAI/bge-reranker-v2-m3`
- `Qwen/Qwen3-Reranker-0.6B`

Existing successful cache entries with matching query, candidate set, and request options are resumed rather than repeated. The runner performs a pilot-specific dry-run and refuses execution if its conservative cost ceiling exceeds the explicitly approved hard budget.

Batch 1 authorization does not authorize Batch 2 or the full 100-query experiment. Every additional paid batch requires a new report of request count, payload scope, and hard budget.

## Blind Candidate Pool

After both exact models have valid cached responses for every selected query, the runner builds `evaluation/rerank/pilot/annotation-template.csv`.

For each selected query it takes:

1. baseline Recall ranks 1 to 3;
2. BGE reranked ranks 1 to 3;
3. Qwen3 reranked ranks 1 to 3;
4. the stable deduplicated union by frozen document ID.

The exported review rows expose query, blind document ID, platform, title, and text excerpt. They omit system membership, baseline rank, reranked rank, scores, model identity, and whether multiple systems selected the same candidate. Query and candidate order are independently hash-shuffled.

The pilot manifest records the selected query IDs, candidate membership, source snapshot hash, exact cache keys, per-system Top-3 hashes, pool size, overlap counts, and annotation-template hash. Any missing response, model mismatch, or candidate snapshot drift blocks pool creation.

## Human Review

The existing local review tool accepts the pilot template through an explicit `--template` path. Its workflow remains:

- complete first-pass grading with `0/1/2` relevance;
- freeze the first pass;
- repeat a deterministic hidden 10% sample after a recommended 48-hour delay;
- calculate exact agreement and quadratic-weighted kappa;
- adjudicate every self-disagreement with a reason;
- export raw first-pass, raw retest, final labels, and provenance manifest.

The same project thresholds apply: exact agreement at least 0.85 and weighted kappa at least 0.80. Evidence remains `single-expert, test-retest-validated`, not multi-reviewer consensus.

## Pilot Metrics

Metrics are calculated only for the selected frozen test queries and the judged Top-3 union:

- MRR@3;
- nDCG@3;
- Precision@3;
- irrelevant-context rate in Top 3;
- pooled Recall@3, whose denominator is relevant documents in the judged three-system Top-3 union;
- per-query win, tie, and loss counts versus baseline;
- platform and query-language slices when a slice contains enough selected queries to report its denominator.

The report must call the recall metric `pooled Recall@3`; it must not imply recall against the full Top-20 candidate set.

Paired query-level metric deltas use a deterministic percentile bootstrap with 10,000 resamples and a recorded seed. Confidence intervals are descriptive pilot uncertainty, not a substitute for the pre-registered decision rules.

## Decision And Sequential Stop Rules

Batch 1 stops without additional annotation when one of these outcomes is supported:

1. A reranker has a positive mean nDCG@3 delta over baseline and the paired 95% bootstrap interval is entirely above zero; the alternative does not create a contradictory quality/system tradeoff.
2. Both rerankers have non-positive mean nDCG@3 deltas; reranking remains disabled.
3. Both rerankers clearly improve quality and one dominates or is quality-close while also no worse on latency, cost, and failures under the existing system rules.

Batch 1 is inconclusive when a promising reranker has a confidence interval crossing zero, the two rerankers form an unresolved quality/system tradeoff, or key supported slices regress without enough examples to interpret. Only then may the user authorize Batch 2.

After Batch 2, remaining uncertainty is reported as uncertainty. The system does not request more labels automatically.

The optional relevance gate is excluded from this pilot because the reduced Top-3 pool does not provide the full development-set score distribution needed for defensible threshold calibration. Production reranking remains disabled by default until the pilot decision is complete.

## Outputs

- `evaluation/rerank/pilot/selection.json`
- `evaluation/rerank/pilot/manifest.json`
- `evaluation/rerank/pilot/annotation-template.csv`
- `evaluation/rerank/pilot/reviewer-single.csv`
- `evaluation/rerank/pilot/reviewer-retest.csv`
- `evaluation/rerank/pilot/labels-adjudicated.csv`
- `evaluation/rerank/pilot/labels-adjudicated.manifest.json`
- `evaluation/rerank/pilot/report.json`
- `evaluation/rerank/pilot/report.md`
- `evaluation/rerank/pilot/artifact-hashes.json`

The existing comprehensive 2,000-row annotation template is preserved as historical full-qrels infrastructure but is no longer the required personal-review path.

## Validation

Tests cover deterministic stratified sampling, nested Batch 2 selection, request and budget counts, cache completeness, Top-3 union deduplication, blind-field exclusion, reduced-template server loading, provenance verification, @3 metrics, bootstrap reproducibility, sequential decision rules, artifact hashes, and rejection of incomplete or drifted inputs.

Playwright verifies the reduced candidate count, first-pass persistence, hidden retest, adjudication, exports, mobile layout, zero external requests, and zero console errors. The full backend suite, Ruff, formatting, JavaScript syntax, `git diff --check`, artifact validation, and secret scan remain required.

## Non-Goals

- No full 100-query paid execution without separate authorization.
- No annotation of all Recall Top 20 candidates.
- No MRR@10, nDCG@10, full Recall@3, gate calibration, or production SLA claim from the pilot.
- No LLM-generated relevance gold.
- No automatic Batch 2 execution or review expansion.
