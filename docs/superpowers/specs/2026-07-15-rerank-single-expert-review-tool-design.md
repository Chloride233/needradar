# NeedRadar Single-Expert Rerank Review Tool Design

## Goal

Provide a local, system-blinded relevance-review tool for the frozen 100-query, 2,000-candidate rerank dataset. One domain-informed reviewer must be able to complete a first pass, repeat a hidden deterministic 10% sample, adjudicate every self-disagreement, and export labels plus provenance that the rerank report can validate without pretending the result is multi-reviewer consensus.

## Evidence Status

The accepted method is `single_expert_blind_test_retest`. It is modeled on pooled information-retrieval assessment: the reviewer judges the frozen union candidate pool without seeing retrieval or reranker identity, rank, or score.

This method may support an internal model-selection decision when its pre-registered checks pass, but reports must call the labels `single-expert, test-retest-validated qrels`. They must not call them independent dual review, inter-rater agreement, or human consensus.

The pre-registered project checks are:

- every one of the 2,000 frozen candidates receives a grade in `{0, 1, 2}`;
- the hidden retest sample contains exactly 10% of candidates, selected deterministically from the frozen template hash and blind document ID;
- first-pass versus retest exact agreement is at least 0.85;
- quadratic-weighted Cohen's kappa is at least 0.80;
- every first-pass/retest disagreement is explicitly adjudicated;
- source and output hashes, stage timestamps, retest delay, and protocol version are recorded.

The thresholds are conservative project acceptance criteria, not universal industry standards. A failed check leaves quality selection blocked while preserving all review work for inspection.

## Architecture

Use a small local-only Python HTTP server plus a static browser application. This avoids new dependencies, does not require the NeedRadar API or Vue frontend to be running, and uses Python's standard CSV parser for the frozen annotation template.

Files:

- `scripts/run_rerank_review.py`: validates the frozen template, serves a redacted JSON package, and hosts the static application on loopback only.
- `evaluation/rerank/review-tool/index.html`: application shell.
- `evaluation/rerank/review-tool/review.js`: state machine, deterministic retest sampling, metrics, import/export, and integrity checks.
- `evaluation/rerank/review-tool/review.css`: restrained operational layout.
- `tests/unit/test_rerank_review.py`: server/package/export validation.
- `evaluation/rerank/review-guide.md`: reviewer instructions and examples.

The server binds to `127.0.0.1`, never sends data externally, and exposes only fields already present in `annotation-template.csv`. It never reads `candidates.jsonl`, reranker caches, model outputs, ranks, or scores.

## Review Workflow

### First Pass

The app groups work by query to reduce context switching. Query order and candidate order within each query are deterministic but unrelated to frozen recall order. The reviewer sees:

- query text;
- blind document ID;
- platform and title;
- text excerpt;
- grade controls `0`, `1`, and `2`;
- an uncertainty flag and optional notes.

The app does not display original row position, recall rank, recall score, model identity, reranked rank, model score, split, or aggregate model results. The `split` value remains in exports for evaluation but is hidden during review.

Progress is saved after every decision in browser storage under the frozen template SHA-256. The reviewer can also export and restore a progress JSON file. Completing the first pass freezes those judgments for the retest comparison; they cannot be silently edited afterward.

### Hidden Retest

The app selects 200 candidates by sorting a SHA-256-derived key over `(template_sha256, blind_document_id)` and taking the first 200. Retest order is separately deterministic. Previous grades and notes remain hidden.

The tool records the elapsed time between first-pass completion and retest start. It reports that duration rather than fabricating independence. A delay of at least 48 hours is recommended in the guide, but the tool does not destroy work or bypass metric calculation when the delay is shorter.

### Self-Adjudication

Only disagreements are shown. The reviewer sees the query, candidate, first grade, retest grade, and both notes, then selects the final grade and enters a required adjudication reason. Agreements flow directly into the final labels.

The app calculates exact agreement, the weighted confusion matrix, and quadratic-weighted Cohen's kappa before adjudication. Adjudication never overwrites those pre-adjudication reliability statistics.

## Grade Rubric

- `0 — Irrelevant`: the document does not help answer or substantiate the expressed need.
- `1 — Partially relevant`: the document addresses an adjacent problem, supplies limited supporting context, or is useful only with substantial interpretation.
- `2 — Highly relevant`: the document directly addresses the need or supplies strong, actionable supporting evidence.

The reviewer must judge usefulness for the expressed query, not topical word overlap alone. Platform prestige, writing quality, assumed model preference, and guessed recall source are not relevance evidence. Uncertainty is recorded but does not replace a final grade.

## State And Integrity

The browser state includes the source template hash, protocol version, first-pass decisions, retest decisions, adjudications, and timestamps. Import rejects:

- a different template hash;
- missing or duplicate blind document IDs;
- grades outside `{0, 1, 2}`;
- impossible stage transitions;
- changed deterministic retest membership;
- a completed adjudication with unresolved disagreements.

Browser storage contains only review state. Clearing browser data can remove unsaved work, so the guide instructs the reviewer to export a progress checkpoint after each session.

## Outputs

The app exports four files:

1. `rerank-review-progress.json`: resumable private working state.
2. `reviewer-single.csv`: all frozen first-pass grades and notes.
3. `reviewer-retest.csv`: hidden retest grades and notes for the deterministic 10% sample.
4. `labels-adjudicated.csv` and `labels-adjudicated.manifest.json`: final grades and provenance.

The final CSV preserves the existing annotation columns so the experiment runner can map `blind_document_id` back to frozen candidates. The manifest uses schema version 2 and records:

- `review_method: single_expert_blind_test_retest`;
- `reviewer_count: 1` and `independent_review: false`;
- system-blinding and adjudication status;
- source template and final labels SHA-256;
- retest fraction, sample count, delay, exact agreement, weighted kappa, and disagreement count;
- acceptance thresholds and pass/fail result;
- stage completion timestamps and protocol version.

The app creates the manifest only after it has serialized the first-pass, retest, and final CSV files, so every recorded SHA-256 covers the exact downloaded bytes. The runner reloads both raw review files, verifies deterministic retest membership, and recomputes agreement and kappa instead of trusting self-reported manifest values.

## Experiment Integration

`run_rerank_experiment.py` will accept either of two explicit provenance paths:

- the existing dual-independent-review manifest; or
- schema-v2 single-expert test-retest provenance that passes every pre-registered check.

The report will expose the review method and reliability metrics. A valid single-expert package enables quality metric calculation and the existing deterministic model-selection rules, but the conclusion must retain a `moderate_evidence_single_expert` qualifier. Invalid, incomplete, or threshold-failing provenance leaves selection blocked.

The baseline, BGE, and Qwen rankings remain unavailable to the review tool throughout all stages.

## Interface

The application is a quiet desktop review surface rather than a dashboard or landing page:

- compact top bar with source hash, stage, completed count, and export command;
- query context band across the page;
- readable candidate text pane with stable width and scroll position;
- fixed grade control rail with large `0`, `1`, and `2` targets;
- collapsible notes field and uncertainty toggle;
- query navigator showing only completion state, never relevance distribution;
- separate retest and adjudication views unlocked by workflow state.

Keyboard grading is supported, while buttons remain fully usable without shortcuts. Focus states, text wrapping, and narrow-screen behavior must be verified. The tool will not show grade histograms during review because they can encourage distribution matching.

## Validation

Unit tests cover:

- redacted package fields and exact 2,000-row membership;
- deterministic query/candidate shuffle and retest sampling;
- weighted kappa calculation, including perfect agreement and degenerate marginals;
- workflow transition and import validation;
- CSV quoting and final SHA-256 provenance;
- acceptance pass/fail behavior;
- experiment runner acceptance of valid single-expert provenance and rejection of incomplete or weak provenance.

Frontend verification uses Playwright at desktop and mobile widths. It must exercise first-pass grading, persistence after reload, progress import, stage transition, hidden retest, disagreement adjudication, and final downloads. Screenshots and browser console checks must confirm no clipping, overlap, blank state, or network request outside loopback.

The existing backend test suite, touched-file Ruff checks, formatting checks, artifact-hash validation, and `git diff --check` remain required.

## Non-Goals

- No LLM grading, suggested labels, semantic highlighting, or model-assisted notes.
- No display of retrieval or reranker outputs.
- No cloud account, database, reviewer identity, or external upload.
- No attempt to represent one person's repeated judgments as independent reviewers.
- No execution of the full paid rerank experiment.
