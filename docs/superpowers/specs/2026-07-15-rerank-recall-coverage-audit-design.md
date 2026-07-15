# Rerank Recall Coverage Audit Design

Status: Approved for implementation planning
Date: 2026-07-15

## Goal

Explain why the 12 frozen test queries with no relevant document in the judged
Top-3 union did not produce useful results, without changing retrieval weights,
adding corpus data, or making paid API calls.

## Scope

The audit uses only the existing frozen candidate snapshot and the existing
single-reviewer blind-review protocol. It examines the current Hybrid Recall
Top-20 for the 12 all-zero queries from the completed Rerank pilot.

For each query, the audit:

1. loads the frozen Top-20 candidates;
2. collapses exact content duplicates while retaining duplicate counts and IDs;
3. hides retrieval rank, score, model, and system identity from review;
4. records relevance grades using the existing 0/1/2 rubric; and
5. classifies the failure using the first applicable category.

## Failure Categories

- `rank_failure`: at least one relevant candidate exists in Top-20, but none is
  present in the original Top-3 union.
- `coverage_failure`: no relevant candidate is found in the deduplicated Top-20.
- `corpus_noise_failure`: duplicate or near-identical content occupies a material
  share of Top-20 and reduces candidate diversity. The report records this as an
  overlapping contributing factor, not an exclusive cause.
- `unresolved`: the review is incomplete or the evidence cannot distinguish the
  categories.

The audit must not claim that `coverage_failure` proves the entire corpus lacks a
relevant document. It only establishes that the frozen Top-20 did not expose one.

## Outputs

Write a versioned audit package under `evaluation/rerank/recall-audit/`:

- immutable manifest with source hashes, query IDs, deduplication rule, rubric,
  and reviewer protocol;
- blinded review template and completed labels;
- JSON and Markdown reports with per-query classifications, duplicate rates,
  grade counts, and aggregate totals;
- artifact hash manifest allowing offline report reconstruction.

The package must preserve the original Rerank pilot artifacts and must never
overwrite them.

## Components

- A preparation command selects the frozen 12-query cohort and emits the blinded
  deduplicated review package.
- The existing review tool serves the package locally; no new web application is
  added.
- A report command validates labels, hashes, query coverage, and category rules,
  then writes the JSON/Markdown report.

## Validation And Boundaries

- The same query/candidate snapshot must produce the same package and hashes.
- Every selected query must be present exactly once; duplicate candidate IDs are
  rejected unless they are exact content duplicates explicitly represented in the
  duplicate map.
- Missing or invalid grades stop report generation.
- No Rerank API, LLM, external network, new corpus document, or retrieval-weight
  change is allowed in this phase.
- Existing pilot results remain the source of model-quality claims; this audit
  can only explain Top-20 coverage and noise.

## Completion Bar

1. The frozen 12-query cohort is reproducibly prepared.
2. The blinded review package is usable with the existing local review tool.
3. The report validates hashes and classifies every query or explicitly marks it
   unresolved.
4. The report distinguishes rank, coverage, and noise evidence without claiming
   full-corpus absence.
5. Focused preparation/report tests, existing Rerank tests, and `git diff --check`
   pass.
