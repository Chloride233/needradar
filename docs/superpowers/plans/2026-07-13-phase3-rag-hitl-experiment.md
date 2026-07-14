# Phase 3 RAG and HITL Experiment Implementation Plan

## Success Criteria

- The same fixture can run as `no_rag`, `rag`, and `rag_hitl` without network access.
- RAG context, HITL edits, token usage, and cost are attributable to the correct configuration.
- Provider cache hits and savings are measurable without reusing outputs across configurations.
- Resume accepts identical provenance and rejects changed experiment conditions.
- Each configuration writes `predictions.jsonl`, `run.json`, and `metrics.json` with reproducible hashes.
- Existing Phase 2 extraction benchmark and metric tests still pass.

## Tasks

### 1. Add failing orchestration tests

Create `tests/unit/test_phase3_experiment.py` with fake provider and retriever fixtures. Cover configuration isolation, RAG invocation, retrieval failure, HITL edit fields, usage totals, exact metrics, and resume provenance.

Verify:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/unit/test_phase3_experiment.py -q
```

The new tests should fail because the Phase 3 service does not exist yet.

### 2. Implement the experiment service

Create `src/needradar/services/phase3_experiment.py`. Keep the API narrow: one runner for a configuration and one runner for the fixed three-configuration suite. Reuse the Phase 2 prompt loader, noise filter, schemas, and scorer.

Implement:

- fixed configuration validation;
- SHA-256 provenance;
- resumable JSONL output;
- explicit retrieval errors;
- provider and optional retriever usage accounting;
- stable system prompts with variable RAG context in user input;
- cached-token accounting and no-cache cost counterfactuals;
- Phase 2-compatible predictions;
- simulated HITL using the scorer's edit criteria;
- pre-review and post-review metrics;
- baseline deltas with zero-baseline handling.

Verify the new unit test file passes.

### 3. Add the explicit runner

Create `scripts/run_phase3_experiment.py` with `--configuration` (`no_rag`, `rag`, `rag_hitl`, or `all`), `--preset`, and `--limit`. Default to the frozen Phase 2 dataset and gold paths and write under `evaluation/phase3`.

The script must refuse real execution when the selected preset has no API key. It must not activate a provider during import.

Verify:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_phase3_experiment.py --help
```

### 4. Document reproduction

Add `evaluation/phase3/README.md` describing the three configurations, HITL limitation, fake test command, real command, output schema, and the fact that no quality claim exists until all real runs complete.

### 5. Run regression and quality checks

Run:

```bash
PYTHONPATH=src .venv/bin/python -m pytest \
  tests/unit/test_phase3_experiment.py \
  tests/unit/test_extraction_benchmark.py \
  tests/unit/test_extraction_metrics.py -q
.venv/bin/python -m ruff check \
  src/needradar/services/phase3_experiment.py \
  scripts/run_phase3_experiment.py \
  tests/unit/test_phase3_experiment.py
git diff --check
```

Update the daily work log with implemented evidence, commands, and remaining Issue #4 acceptance items.
