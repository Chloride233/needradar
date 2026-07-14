# Phase 3 Verifier Component Ablation and Eight-Stage Audit Design

## Goal

Produce reproducible evidence for the report verifier without pretending that its eight sequential stages are eight independent hallucination detectors.

The experiment has three outputs:

1. A component ablation for choices that can be changed while preserving a comparable output.
2. An eight-stage audit that reports the metric appropriate to each stage.
3. Robustness tests for missing evidence, long reports, conflicting sources, and malformed model output.

The experiment must report negative and null results. It must not describe a downstream score or suggestion stage as a gain in hallucination-detection accuracy.

## Claim Boundary

The current README calls the verifier "8-step hallucination detection." The code is more accurately an eight-stage verification pipeline:

1. Load report input.
2. Extract claims.
3. Resolve referenced sources.
4. Classify claims against evidence.
5. Check internal consistency.
6. Apply a source-reliability heuristic.
7. Aggregate component scores.
8. Generate review suggestions.

Stages 1 and 3 are data gates. Stage 7 is score composition. Stage 8 is review assistance. Only stages 2 and 4 directly extract or classify hallucinations.

Until the experiment is complete, public documentation should use "eight-stage verification pipeline" rather than imply that all eight stages independently detect hallucinations.

## Approaches Considered

### Rejected: cumulative prefixes

Running `step_1`, `step_1_2`, through `step_1_..._8` produces no common target before fact checking and confounds every later result with all prior stages. It cannot estimate a stage's causal contribution.

### Rejected: eight literal leave-one-stage-out runs

Removing report loading, claim extraction, source resolution, or fact checking breaks downstream inputs. These are dependency failures, not comparable single-factor ablations. Filling missing outputs with a neutral score would introduce an arbitrary bias.

### Selected: component ablation plus stage audit

Only interchangeable or optional components are ablated. All eight stages are still audited, but each receives an appropriate metric and may be marked structural or not applicable for detection quality.

## Prerequisites

Before any paid verifier run:

1. Extend the existing Phase 3 report gate to reject cross-configuration differences in schema version, model ID, provider parameters, pricing, and discussion-length limits. Validate exact prediction ID sets as well as completion counts.
2. Make verifier model calls provider-injected and disable cross-model fallback for experiments.
3. Represent every stage as `success`, `failed`, or `skipped` with an explicit reason. Parsing failures and incomplete batch responses must not become empty claims, `unverifiable`, or a 100 consistency score.
4. Record per-stage prompt hash, model parameters, input/output/cached tokens, actual cost, and no-cache counterfactual cost.
5. Extend extracted claims with an exact source quote and stable claim ID. Free-form paraphrases alone are not sufficient for reproducible claim matching.

Production API behavior may reuse these stricter primitives, but the experiment runner remains separate from the database-backed pipeline and never creates production verification records.

## Frozen Benchmark

Create these frozen files:

- `evaluation/phase3/verifier-benchmark.jsonl`: report inputs and embedded sources, without gold fields;
- `evaluation/phase3/verifier-gold.jsonl`: claim and report labels keyed by bundle ID;
- `evaluation/phase3/verifier-benchmark-manifest.json`: record counts plus byte-level and canonical JSON SHA-256 values for both files.

The benchmark contains 30 report bundles drawn from the frozen public Phase 3 corpus:

- 10 GitHub bundles;
- 10 Stack Overflow bundles;
- 10 Juejin bundles.

Each input bundle embeds its report body, metadata, and referenced source documents. Gold annotations remain in the separate gold file and are never passed to a model call. No author identifiers are stored.

The set contains two strata:

- 18 controlled reports whose supported and corrupted claims are known by construction;
- 12 naturalistic report-style documents independently annotated after drafting.

Each stratum is balanced between clean and flagged reports, producing 15 reports with no `contradicted` or `hallucination` claim and 15 reports with at least one such claim. This balance makes threshold-free report ranking metrics meaningful.

Across the complete set, include short, medium, and long reports. Long reports must place some gold claims after character 4,000 so the current truncation behavior is measurable rather than hidden.

Gold annotations contain:

- exact claim quote and stable ID;
- section and character offsets;
- verdict: `supported`, `partially`, `unverifiable`, `contradicted`, or `hallucination`;
- source IDs supporting or contradicting the claim;
- whether the report contains an internal contradiction;
- whether the claim needs a correction suggestion.

Controlled corruptions cover unsupported numbers, exaggerated scope, wrong attribution, categorical contradiction, missing evidence, and supported controls. Naturalistic annotations use two independent agent passes and adjudicate every claim-span or verdict disagreement. They remain proxy annotations unless a human reviews them, and the report must state that limitation.

## Claim Matching

Claim extraction must return an exact report quote, section, start offset, and end offset rather than only a paraphrase. The evaluator validates that the quote occurs at the supplied offsets. It computes the stable claim ID as the first 16 hexadecimal characters of SHA-256 over the normalized quote, section, and start offset. Duplicate matches are resolved by this ID.

No LLM judge is used to align predictions with gold. Unmatched predicted claims count as false positives and unmatched gold claims as false negatives. A separate text-similarity diagnostic may be reported but cannot change the primary score.

## Experiment Families

### 1. Component ablation

Run paired configurations on the same frozen bundles:

| Family | Configurations | Primary comparison |
| --- | --- | --- |
| Claim extraction | rule-only, LLM-only, hybrid | claim precision, recall, F1, tail recall |
| Evidence context | no evidence, titles only, 200-character snippets, 800-character snippets | verdict macro-F1 and hallucination precision/recall |
| Score composition | fact-only, fact + consistency, full weighted score | report-level AUROC and average precision |

Score-composition variants remove unavailable weights and renormalize the remaining weights. They never substitute a neutral value.

The 200-character condition reproduces the current fact-check context. The 800-character condition uses the already collected per-source content limit. Both use at most 15 sources in a stable order, and the selected limit is part of provenance.

The source-reliability value is identified as a heuristic prior, not a truth label. Report its marginal effect on ranking separately. Do not claim that hard-coded platform weights measure factual reliability.

Suggestion generation is not part of detection ablation because it deterministically consumes verdicts. It is evaluated only in the stage audit.

### 2. Eight-stage audit

| Stage | Audit metric |
| --- | --- |
| 1. Input loading | report load rate, metadata validity, source-reference count |
| 2. Claim extraction | precision, recall, F1, duplicate rate, recall after character 4,000 |
| 3. Source resolution | referenced-source recall and evidence coverage |
| 4. Fact checking | five-class macro-F1, hallucination precision/recall, flagged precision/recall |
| 5. Consistency | contradiction precision, recall, F1 |
| 6. Source prior | score distribution and marginal ranking delta only |
| 7. Aggregation | AUROC and average precision using `100 - overall_score` as risk for reports containing any flagged claim |
| 8. Suggestions | correction precision, recall, coverage, and unsupported suggestion rate |

The product currently has no automatic report acceptance threshold. The experiment therefore uses threshold-free ranking metrics for stage 7 and does not invent a pass/fail workflow.

### 3. Robustness tests

The frozen benchmark includes explicit cases for:

- claims after the current 4,000-character extraction boundary;
- evidence after the current per-source summary boundary;
- missing referenced source files;
- sources that disagree with each other;
- duplicate or overlapping claims;
- non-list JSON, invalid verdicts, missing batch indices, and partial batch output;
- provider exceptions and interrupted runs.

Malformed model output is an experiment failure, not a valid `unverifiable` prediction. Missing evidence is a valid `skipped/no_evidence` state and is scored separately from provider failure.

## Execution and Artifact Reuse

Run the full stage trace once per report and persist immutable intermediate artifacts:

- extracted claims;
- resolved source packets;
- fact-check verdicts;
- consistency result;
- source-prior score;
- aggregate score;
- suggestions;
- per-stage usage and errors.

Ablation configurations reuse an upstream artifact only when the stage input, prompt hash, model parameters, and component configuration are byte-identical. Reuse is recorded by artifact hash. A configuration with changed evidence or claims must produce a new fact-check call.

This application-level artifact reuse is reported separately from provider prefix caching. The report includes:

- actual paid cost;
- provider cache savings;
- application artifact-reuse savings;
- a naive independent-rerun counterfactual.

Stable instructions remain in system messages and variable report, claim, and evidence content remains in user messages to maximize provider prefix-cache reuse.

All strict structured-output calls disable provider thinking. The effective `extra_body` is frozen in provenance because the paid trial showed that thinking consumed the 2,000-token extraction budget before a final JSON response was emitted. The model returns exact report quotes, while the runner derives character offsets locally. Hybrid extraction is capped at 12 claims; exceeding the cap fails that configuration instead of creating a second fact-check batch and breaking the 150-call ceiling.

Provider attempts, responses with usage, calls skipped because no claims were available, provider-cache savings, and structural artifact reuse are separate counters. Prompt, input, parameters, and output are persisted as SHA-256 traces without storing an additional copy of the external payload or raw response.

## Outputs

Write all artifacts under `evaluation/phase3/verifier-runs/<run-name>/`:

- `predictions.jsonl`: bundle, configuration, stage outputs, statuses, errors, and usage;
- `run.json`: hashes, model and provider provenance, progress, failure counts, and cost;
- `metrics.json`: component, stage, robustness, and cost metrics;
- `report.md`: findings, negative results, representative failures, and limitations.

The runner supports exact resume. It rejects changed benchmark hashes, gold hashes, prompt hashes, schema, model, provider parameters, pricing, or component configuration.

The first paid run under `verifier-runs/full/` is frozen as rejected failure evidence. Schema-v2 execution writes to `verifier-runs/full-v2/` and never resumes or overwrites the rejected run.

## Error Semantics

- Provider fallback is disabled.
- Invalid or incomplete structured output fails the affected stage and record.
- Missing sources are not provider failures; they produce a recorded no-evidence state.
- A failed consistency call has no score and cannot default to 100.
- A report with failed claim extraction cannot receive a neutral fact-check score.
- Aggregate metrics exclude unavailable component values and report their denominator explicitly.
- The run continues after record-level failure and reports extraction, source, fact-check, consistency, and scoring failures separately.

## Tests

Offline tests use fake providers and frozen fixtures. They must cover:

1. Exact dataset and manifest validation.
2. Exact quote/offset claim matching without an LLM judge.
3. All component configurations and stage-specific metrics.
4. Weight renormalization when consistency or source prior is absent.
5. Strict rejection of invalid verdicts, duplicate indices, missing indices, and malformed JSON.
6. Missing-source versus provider-failure attribution.
7. Cross-model fallback remaining disabled.
8. Per-stage token, cached-token, and cost accounting.
9. Artifact reuse only for byte-identical stage inputs.
10. Resume acceptance for identical provenance and rejection for every frozen field.
11. Long-report tail-claim recall.
12. Existing verifier API and Phase 3 RAG/HITL regressions continuing to pass.

## Paid Run Gate

Dataset construction, fake-provider tests, report generation, and artifact regression require no paid calls. Before the real verifier run, report the expected number of calls, expected cost, public text sent to the provider, and the exact output directory, then obtain explicit approval.

## Success Criteria

The slice is complete when:

- the 30-bundle benchmark and manifest are frozen and reproducible;
- every stage failure is explicit and no failed call produces a valid-looking score;
- component ablations use paired inputs and applicable metrics;
- all eight stages have an honest audit result, including `not applicable` where appropriate;
- cache and artifact-reuse savings are independently reproducible;
- a formal report includes limitations for synthetic corruption, proxy annotation, platform/content-type confounding, truncation, and heuristic source priors;
- README wording matches the evidence actually produced.

No stage is required to improve quality. A null or negative contribution is a valid result and may justify simplifying or removing that component.
