# Rerank relevance annotation protocol

## Purpose

Create human relevance judgments for the frozen query-candidate snapshot before model-quality comparison or gate calibration is treated as evidence.

## Common blinding rules

Reviewers receive only the query, blind document ID, platform, title, and text excerpt. The review surface exposes neither recall rank, recall score, reranker identity, reranker score, reranked position, data split, nor aggregate model results.

Judge only whether the shown document would help answer or substantiate the expressed query. Do not infer relevance from platform, writing quality, keyword overlap alone, assumed product intent, or a guessed retrieval source.

## Grades

- `0`: irrelevant; the document adds no useful evidence for the query.
- `1`: partially relevant; it addresses an adjacent need or supplies limited supporting context.
- `2`: highly relevant; it directly addresses the need or supplies strong, actionable supporting evidence.

Uncertainty or missing context belongs in `notes`; every completed row still requires a grade.

## Accepted path A: independent reviewers

1. Reviewer A and Reviewer B grade separate shuffled copies without seeing each other's work.
2. Validate one grade from `{0, 1, 2}` for every blind document ID in each copy.
3. Calculate exact agreement and weighted Cohen's kappa.
4. A third reviewer resolves disagreements using the same rubric.
5. Record `review_method: dual_independent_blind`, reviewer count, hashes, agreement statistics, adjudication, and completion time.

This path may be described as independently reviewed human labels after every disagreement is adjudicated.

## Accepted path B: single expert with hidden test-retest

1. One domain-informed reviewer completes all 2,000 judgments in the local review tool without inspecting model outputs.
2. The tool freezes the first pass and deterministically selects 10% of candidates from the frozen template hash.
3. After a recommended delay of at least 48 hours, the reviewer grades the hidden sample again without seeing first-pass decisions.
4. The tool computes exact agreement and quadratic-weighted Cohen's kappa from the two raw review files.
5. The reviewer explicitly adjudicates every self-disagreement and records a reason.
6. The runner independently verifies both raw file hashes, deterministic sample membership, metrics, adjudications, and final label hash.

The pre-registered project thresholds are exact agreement `>= 0.85` and weighted kappa `>= 0.80`. These are project acceptance criteria, not universal standards. Missing files, altered samples, failed thresholds, unresolved disagreements, or uncomputable kappa leave model selection blocked.

This path must be described as `single-expert, test-retest-validated qrels`. It is not independent dual review, inter-rater agreement, or human consensus.

## Output and freezing

The final package contains `reviewer-single.csv`, `reviewer-retest.csv`, `labels-adjudicated.csv`, and `labels-adjudicated.manifest.json`. Preserve the blank hashed template. Freeze all output files before calibrating model-specific gates on the `dev` split, then evaluate frozen thresholds once on `test` without tuning against test results.

Agent-generated grades, reranker scores, recall scores, platform heuristics, extraction labels, and direct LLM-as-judge output are not human relevance gold.
