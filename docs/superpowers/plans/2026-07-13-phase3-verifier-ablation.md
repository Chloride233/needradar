# Phase 3 Verifier Ablation Implementation Plan

## Success Criteria

- Future RAG/HITL reports reject mixed model, provider, pricing, schema, truncation, or prediction-ID provenance.
- Verifier stage failures are explicit and never become valid-looking neutral or perfect scores.
- Experiment calls use an injected provider with cross-model fallback disabled.
- Claims contain verifiable report quotes and offsets that can be matched without an LLM judge.
- A 30-bundle input benchmark and separate gold file reproduce exact hashes and contain no author fields.
- Component ablations, eight-stage audit metrics, robustness metrics, cache savings, and artifact-reuse savings reproduce offline.
- Existing verifier API behavior and Phase 3 RAG/HITL artifact regressions continue to pass.
- No real verifier provider call occurs before a separate paid-run approval.

## Tasks

### 1. Close the current report provenance gap

Add failing tests to `tests/unit/test_phase3_reporting.py` that copy the frozen run artifacts to a temporary directory and mutate one cross-configuration field at a time.

Reject differences in:

- schema version;
- model ID;
- provider parameters;
- frozen pricing;
- maximum discussion length;
- exact prediction ID sets.

Keep RAG provenance differences intentional between `no_rag` and RAG groups, but require `rag` and `rag_hitl` to share retriever provenance.

Verify:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/unit/test_phase3_reporting.py -q
```

### 2. Add strict verifier stage primitives

Write focused tests before modifying `ContentVerifier`.

Implement the minimum production-compatible changes:

- inject the provider through `ContentVerifier.__init__` with the existing singleton provider as default;
- call the provider with `fallback_to_default=False` in strict experiment execution;
- add exact report quote, section, start, end, and derived claim ID fields;
- validate structured responses, verdict enums, and complete fact-check batch indices;
- distinguish `success`, `failed`, and `skipped/no_evidence`;
- expose per-stage usage without writing experiment records to the application database;
- ensure a failed consistency call has no score.

Verify:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/unit/test_content_verifier.py -q
```

### 3. Build the frozen verifier benchmark

Create a narrow benchmark service and script. Generate inputs from the already frozen public Phase 3 corpus without crawler or model calls.

Write:

- `evaluation/phase3/verifier-benchmark.jsonl`;
- `evaluation/phase3/verifier-gold.jsonl`;
- `evaluation/phase3/verifier-benchmark-manifest.json`.

Validate:

- 30 unique bundle IDs and 10 bundles per platform;
- separate input and gold fields;
- 18 controlled and 12 naturalistic report-style bundles;
- 15 clean and 15 flagged reports;
- short, medium, and long reports, including tail claims after character 4,000;
- exact quote offsets and deterministic claim IDs;
- no author fields;
- frozen byte and canonical hashes.

Naturalistic gold remains proxy evidence. Keep its construction and review limitation explicit rather than representing it as human annotation.

Verify:

```bash
PYTHONPATH=src .venv/bin/python scripts/build_phase3_verifier_benchmark.py
PYTHONPATH=src .venv/bin/python -m pytest tests/unit/test_phase3_verifier_benchmark.py -q
```

### 4. Implement offline metrics and component configurations

Create `phase3_verifier_experiment.py` with fixed configurations for:

- claim extraction: rule-only, LLM-only, hybrid;
- evidence: none, titles, 200-character snippets, 800-character snippets;
- score composition: fact-only, fact plus consistency, full weighted score.

Implement:

- exact claim matching;
- claim precision, recall, F1, duplicate rate, and tail recall;
- five-class verdict macro-F1;
- hallucination and flagged precision/recall;
- contradiction precision/recall/F1;
- report risk AUROC and average precision without adding a dependency;
- suggestion precision, recall, coverage, and unsupported rate;
- weight renormalization without neutral filler scores.

Use small local metric functions rather than adding scikit-learn for this experiment.

Verify exact fake-fixture metrics in a dedicated unit test.

### 5. Add stage artifacts, reuse, resume, and cost accounting

Persist immutable per-stage artifacts and hashes. Reuse only byte-identical upstream inputs.

Record:

- prompt, input, output, and artifact hashes;
- input, output, cached, and total tokens;
- actual provider cost;
- no-provider-cache cost;
- naive independent-rerun cost;
- provider cache and application artifact-reuse savings;
- per-stage failure and skip counts.

Reject resume when any frozen provenance field changes.

Tests must prove that changing evidence invalidates fact-check reuse while score-only configurations reuse identical verdict artifacts.

### 6. Add the explicit runner and report

Create scripts for offline/fake execution and the later real run. The real runner must:

- require an explicitly configured preset;
- keep fallback disabled;
- default to a new output directory;
- print expected calls and estimated maximum cost in dry-run mode;
- never activate or call a provider during import.

Generate JSON and Markdown reports covering component results, all eight stage audits, robustness failures, cost savings, representative cases, and limitations.

### 7. Documentation and quality gates

Change public wording from "8-step hallucination detection" to "eight-stage verification pipeline" until evidence supports a narrower quality claim.

Update:

- `evaluation/phase3/README.md`;
- the approved design document only if implementation uncovers a contradiction;
- `vault/05-工作日志/2026-07-13.md`.

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/unit -q
.venv/bin/python -m ruff check <changed-python-files>
.venv/bin/python -m ruff format --check <changed-python-files>
PYTHONPATH=src .venv/bin/python -m compileall -q src scripts tests/unit
git diff --check
```

Before a real verifier run, stop and report the exact public text sent externally, number of calls, expected cost range, output path, and whether application artifact reuse is enabled.
