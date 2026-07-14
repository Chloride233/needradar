# Phase 3 RAG and HITL Experiment Design

## Goal

Build the first reproducible Phase 3 experiment slice for GitHub Issue #4. The slice compares requirement extraction under three fixed configurations while preserving the Phase 2 dataset, proxy gold labels, and scoring methodology.

This slice establishes experiment orchestration and attribution. Automated verification does not run paid model calls; real execution is separate and requires explicit approval. The slice does not implement the later eight-step hallucination-verifier ablation.

## Experimental Configurations

The runner accepts exactly these configurations:

| Configuration | Model extraction | RAG context | HITL correction |
| --- | --- | --- | --- |
| `no_rag` | Yes | No | No |
| `rag` | Yes | Yes | No |
| `rag_hitl` | Yes | Yes | Yes |

Arbitrary feature combinations are intentionally unsupported. Fixed configurations prevent unreported differences between experiment groups.

## HITL Definition

The first experiment simulates human review by comparing each RAG prediction with the frozen Phase 2 proxy gold record. It uses the same edit criteria as the Phase 2 scorer: requirement-presence or categorical fields differ, or a text field has character-bigram Dice similarity below 0.5.

The editable fields are `requirement_present`, `title`, `description`, `pain_point`, `use_case`, `sentiment`, and `emotion`. The simulation does not overwrite model confidence, rejection reasons, extraction errors, annotation notes, or evidence clarity. When requirement presence changes, the corrected record takes all editable values from gold so its fields remain internally consistent. Otherwise, only categorical mismatches and text fields below the similarity threshold are replaced.

The experiment must report both states separately:

- pre-review model quality, which is attributable to the model and RAG configuration;
- post-review quality, which includes simulated human corrections;
- records and fields edited during review, which represent the measured review burden.

Post-review accuracy must not be described as model quality or as an HITL accuracy gain without also reporting the simulated edit rate. The Phase 2 gold set is based on two-agent blind annotation with 7% targeted human review, so the report must retain that limitation.

## Architecture

Add a small Phase 3 experiment service around the existing extraction benchmark and `score_extractions` function. Do not drive the full database-backed pipeline for this controlled experiment.

The service has four responsibilities:

1. Load and validate the frozen dataset, gold labels, prompt, and experiment configuration.
2. Run or resume extraction with an injected provider and, for RAG configurations, an injected retriever.
3. Apply simulated review only for `rag_hitl`, while retaining the pre-review prediction.
4. Write uniform run metadata and calculate metrics through the existing Phase 2 scorer.

Provider and retriever injection keeps the orchestration deterministic under tests. Production providers are only used by an explicit experiment script.

## Data Flow

For every frozen discussion record:

1. Apply the existing rule-based noise filter.
2. For accepted records, build the same base extraction prompt used by Phase 2.
3. In `rag` and `rag_hitl`, retrieve context with fixed parameters and append it to the user input. The system prompt remains byte-identical across records and configurations so provider prefix caching can reuse the stable prefix.
4. Call the configured structured extraction provider.
5. Store the pre-review prediction and per-call usage.
6. In `rag_hitl`, compare the prediction with the matching gold record, apply corrections, and record edited fields.
7. Persist progress so an interrupted run can resume by record ID.
8. Score the completed output with `score_extractions`.

All configurations use the same input ordering, rule filter, provider settings, retry behavior, and scorer.

## Outputs

Each configuration writes to its own directory and produces:

### `predictions.jsonl`

One record per input with the existing Phase 2 prediction fields plus:

- `configuration`
- `rag_context_used`
- `hitl_edited`
- `hitl_edited_fields`
- `pre_hitl_prediction` for edited `rag_hitl` records
- `usage` for that record

Gold-only metadata and review fields must not be copied into `no_rag` or `rag` predictions.

### `run.json`

Run-level provenance and accounting:

- configuration name;
- dataset and gold SHA-256 values;
- prompt SHA-256;
- provider/model identifier;
- fixed RAG parameters;
- requested, completed, resumed, and failed counts;
- input, output, cached, and total tokens;
- actual cost in CNY;
- provider parameters and pricing used for the run;
- experiment schema version.

### `metrics.json`

The existing Phase 2 metric output plus a Phase 3 comparison section containing:

- requirement-presence accuracy;
- sentiment and emotion accuracy;
- text-field similarity;
- duplicate and extraction-failure rates;
- proxy record edit rate;
- simulated HITL record and field edit rates;
- token and actual-cost totals;
- cache hit rate, counterfactual cost without caching, and cache savings;
- absolute and relative changes from `no_rag`.

For `rag_hitl`, metrics must expose both pre-review and post-review results.

## Resume and Failure Semantics

- Resume by record ID using the existing Phase 2 behavior.
- Before resuming, compare the stored schema version, configuration, input hashes, prompt hash, model identifier, and RAG parameters with the requested run.
- Reject mismatched resume attempts instead of mixing experiment conditions.
- A RAG retrieval failure in a RAG configuration is an explicit record error. It must not silently fall back to the no-RAG condition.
- A structured-output parse failure follows the existing bounded retry behavior, writes an `error` prediction, and allows remaining records to continue.
- Run summaries report extraction and retrieval failures separately.

## Metric Attribution

The report compares each configuration with `no_rag` using both absolute and relative differences. Relative differences with a zero baseline are reported as unavailable rather than coerced to zero or infinity.

RAG attribution uses pre-review `rag` results. HITL attribution presents the RAG model result, simulated edit burden, and post-review result as three separate quantities. Token and cost accounting must distinguish model extraction from any retrieval cost when the retriever exposes usage. It must retain provider-reported cached tokens and use frozen pricing parameters to calculate cache hit rate, counterfactual no-cache cost, and cache savings. Actual provider cost remains authoritative.

Application-level response reuse is prohibited across configurations because RAG changes the model input and HITL changes attribution. Records remain one call each; batching is excluded because it would change task difficulty, output coupling, and retry granularity.

## Tests

The implementation must include focused tests for:

1. All three configurations producing the same output schema and isolated directories.
2. Only RAG configurations invoking the injected retriever and receiving its context.
3. Retrieval failures remaining explicit rather than degrading to no RAG.
4. Simulated HITL changing only fields that differ from gold and reporting record and field edit rates exactly.
5. Pre-review predictions remaining available for `rag_hitl` attribution.
6. Token and cost totals remaining isolated by configuration.
7. Cached tokens flowing into cache hit rate, no-cache cost, and savings exactly.
8. RAG context appearing in the user input while the system prompt stays identical to `no_rag`.
9. Resume succeeding with identical provenance.
10. Resume rejecting changed inputs, prompt, model, provider parameters, pricing, configuration, or RAG parameters.
11. A small fixed fake-provider fixture reproducing exact aggregate metrics.
12. Existing Phase 2 benchmark and frozen-metric regression tests continuing to pass.

## Reproducibility and Paid Calls

The repository will expose one explicit script for running a selected configuration or all three configurations. The script defaults to the frozen Phase 2 paths and separate Phase 3 output directories.

Automated tests use fake providers and retrievers and perform no network or paid calls. A real experiment requires an explicit provider configuration and user confirmation before execution. The generated run metadata is sufficient to reproduce or audit each result.

## Execution Outcome

After approval, the authoritative schema-v3 run completed 100 records in all three configurations with no extraction or retrieval failures. Requirement-presence accuracy was 49% both without and with RAG. RAG improved emotion accuracy from 65.96% to 74.47%, but increased tokens by 17.08%, cost by 20.10%, and duplicate rate from 0% to 1.02%; description and pain-point similarity declined.

Simulated HITL edited 97 records and 437 fields, producing 100% post-review proxy accuracy. This is review-assisted output, not model quality. Prefix caching reduced combined actual cost from a CNY 1.106998 no-cache counterfactual to CNY 0.393868, a 64.42% saving.

The authoritative artifacts are under `evaluation/phase3/runs/full-final`; `evaluation/phase3/full-report.md` and `full-report.json` contain the detailed comparison. The conclusion remains limited by the query-stratified sample, platform/content-type confounding, proxy gold with 7% targeted human review, fallback bag-of-words embeddings, and independent stochastic RAG calls.

## Scope Boundary

This slice ends when the three-configuration orchestration, uniform artifacts, fake regression, resume validation, and executable script are complete.

The next Phase 3 slice will define a separate report dataset and perform single-factor ablation of the eight content-verification steps. No hallucination-verifier claims are made by this slice.
