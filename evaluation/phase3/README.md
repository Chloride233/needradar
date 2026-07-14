# Phase 3 RAG and HITL experiment

This directory holds the reproducible experiment artifacts for GitHub Issue #4. The first slice compares requirement extraction on the frozen Phase 2 sample under three fixed configurations:

| Configuration | RAG | Simulated HITL |
| --- | --- | --- |
| `no_rag` | No | No |
| `rag` | Yes | No |
| `rag_hitl` | Yes | Yes |

## HITL interpretation

The HITL condition uses the Phase 2 adjudicated proxy gold to simulate review. It corrects requirement presence, categorical mismatches, and text fields whose character-bigram Dice similarity is below 0.5. The output reports the model result before review, the fields edited, and the result after review separately.

The Phase 2 gold set comes from two-agent blind annotation with 7% targeted human review. Post-review accuracy is therefore not a model-quality claim and is not evidence from 100 real human reviews.

## Offline verification

No API key, model call, vector index, or network access is required:

```bash
PYTHONPATH=src .venv/bin/python -m pytest \
  tests/unit/test_phase3_experiment.py \
  tests/unit/test_extraction_benchmark.py \
  tests/unit/test_extraction_metrics.py -q
```

The fake experiment verifies configuration isolation, RAG injection, explicit retrieval failures, HITL attribution, usage accounting, exact metrics, and resume provenance.

## Real experiment

First collect the held-out public corpus. This performs crawler requests but no LLM calls:

```bash
PYTHONPATH=src .venv/bin/python scripts/sample_phase3_rag_corpus.py
```

The command requires 50 records from each platform after excluding every Phase 2 URL. It writes `rag-corpus.jsonl` and `rag-corpus-manifest.json`; the manifest records both dataset hashes and requires zero URL overlap.

After configuring the selected provider API key, run all three conditions:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_phase3_experiment.py \
  --configuration all \
  --preset deepseek-v4-flash
```

The authoritative complete run uses a dedicated output directory:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_phase3_experiment.py \
  --configuration all \
  --preset deepseek-v4-flash \
  --output-dir evaluation/phase3/runs/full-final
```

Use a separate directory for a cache smoke test:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_phase3_experiment.py \
  --configuration all \
  --preset deepseek-v4-flash \
  --limit 5 \
  --output-dir evaluation/phase3/runs/cache-smoke
```

The selection hash stored in `run.json` also prevents a limited run from being resumed as a full run in the same output directory.

Each configuration writes:

- `predictions.jsonl`: predictions, per-record usage, RAG status, and HITL edit metadata;
- `run.json`: hashes, model and RAG provenance, progress, failures, tokens, and cost;
- `metrics.json`: Phase 2 quality metrics, Phase 3 summary, HITL burden, and change from `no_rag`.

All configurations use the same stable system prompt. RAG context is appended to the user input so DeepSeek can reuse the shared prompt prefix across records and groups. Metrics retain provider-reported cached tokens and report cache hit rate, actual cost, counterfactual cost without caching, and cache savings. Outputs are never reused across configurations because that would invalidate the ablation.

RAG runs always inject the top three results (`min_score=0.0`) so retrieval coverage remains comparable when the project uses its local fallback embeddings. Low-relevance context is retained for negative-benefit analysis. The dedicated LanceDB table name is derived from both the frozen corpus hash and embedding backend; corpus hash, record count, backend, and table name are stored in `run.json`. Retrieval exceptions or empty context are recorded as failures rather than silently treated as no RAG.

## Complete results

The schema-v3 `full-final` run completed 100/100 records in every configuration, with no extraction or retrieval failures.

| Configuration | Requirement accuracy | Emotion accuracy | Total tokens | Actual cost (CNY) | Cache hit rate |
| --- | ---: | ---: | ---: | ---: | ---: |
| `no_rag` | 49.00% | 65.96% | 277,611 | 0.118799 | 94.90% |
| `rag` | 49.00% | 74.47% | 325,039 | 0.142683 | 97.24% |
| `rag_hitl` | 100.00% post-review | 100.00% | 320,109 | 0.132386 | 97.40% |

RAG did not improve requirement-presence accuracy. It improved emotion accuracy by 8.51 percentage points, while description and pain-point similarity declined, duplicate rate rose from 0% to 1.02%, tokens rose 17.08%, and actual cost rose 20.10%. Simulated HITL edited 97/100 records and 437 fields; its post-review result is proxy-assisted and is not model quality.

Combined actual cost was CNY 0.393868. The frozen-pricing counterfactual without prefix caching was CNY 1.106998, so caching saved CNY 0.713130 (64.42%). See `full-report.md` and `full-report.json` for platform comparisons, per-record gains and regressions, provenance, and limitations.

Reproduce the report and its exact artifact regression without API calls:

```bash
PYTHONPATH=src .venv/bin/python scripts/report_phase3_experiment.py
PYTHONPATH=src .venv/bin/python -m pytest tests/unit/test_phase3_reporting.py -q
```

## Diagnostic run history

- `runs/cache-smoke`: successful 5-record run for all three configurations; validates provider and cache accounting only.
- `runs/full`: stopped after the provider attempted cross-model fallback; incomplete and excluded from conclusions.
- `runs/full-strict`: completed with fallback disabled, but each RAG group had one deterministic provider input-limit failure above 50,000 characters; retained as diagnostic evidence.
- `runs/full-final`: authoritative schema-v3 run with the same 47,000-character discussion cap across all groups and cross-model fallback disabled.

Approximate cumulative spend across smoke, diagnostic, and authoritative runs was CNY 1.00.

The five-record paid cache smoke is documented in `cache-smoke-report.md`. It validates cache accounting but is not treated as the complete quality experiment.

## Verifier component ablation

The verifier benchmark is separate from the extraction benchmark. It contains 30 frozen report bundles, with GitHub, Stack Overflow, and Juejin contributing 10 each. Inputs and gold are stored separately; 12 naturalistic reports received two independent blind reviews followed by explicit adjudication.

Build and validate the benchmark without network or model calls:

```bash
PYTHONPATH=src .venv/bin/python scripts/build_phase3_verifier_benchmark.py
PYTHONPATH=src .venv/bin/python -m pytest \
  tests/unit/test_phase3_verifier_benchmark.py \
  tests/unit/test_phase3_verifier_metrics.py \
  tests/unit/test_phase3_verifier_experiment.py \
  tests/unit/test_phase3_verifier_reporting.py -q
```

Inspect the paid-run gate without activating a provider:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_phase3_verifier_experiment.py
```

The stage DAG needs at most 150 model calls for 30 reports. Reusing identical upstream artifacts avoids 450 calls relative to 600 naive independent calls. The conservative no-cache ceiling is CNY 1.42128. Gold annotations never leave the local process; only de-authored public report text and embedded public source snippets are sent when `--execute` is explicitly supplied.

The experiment reports component ablations and an eight-stage audit. It does not describe all eight stages as independent hallucination detectors.

### Rejected first verifier run

The first paid run in `verifier-runs/full/` is not accepted as component-ablation evidence. Claim extraction failed for 28/30 reports and returned no LLM claims for the remaining two. It made at least 114 provider attempts, while only 113 responses carried usage metadata; the recorded CNY 0.203212 cost is therefore a lower bound. Structural artifact reuse saved 450 calls, while 36 additional calls were skipped only because extracted claims were empty. These counters are not combined.

Reproduce the rejection decision and exact artifact hashes without provider calls:

```bash
PYTHONPATH=src .venv/bin/python scripts/audit_phase3_verifier_run.py
PYTHONPATH=src .venv/bin/python -m pytest tests/unit/test_phase3_verifier_reporting.py -q
```

See `verifier-runs/full/failed-run-audit.md`. The repaired schema-v2 runner disables provider thinking for structured responses, derives quote offsets locally, rejects unavailable downstream scores, records valid denominators and call hashes, and defaults to the new `verifier-runs/full-v2/` directory.

### Schema-v2 verifier result

The repaired run completed all 30 records with two stable stage failures after one targeted retry each. Component comparisons use common-record intersections: 29 reports for extraction and 23 reports for evidence and score composition. The eligibility funnel is 30 total, 29 extraction-success, 24 nonempty hybrid, and 23 all-evidence-success.

- Hybrid extraction F1 was 0.753 versus 0.597 for rule-only, but hybrid tail recall was lower and long-report hybrid F1 regressed from 0.636 to 0.571.
- On the paired 23 reports, 800-character evidence had macro-F1 0.448, flagged F1 0.640, and AUROC 0.568. Ranking remains weak and the small slices are descriptive only.
- Fact-only AUROC was 0.568; fact plus consistency remained 0.568; the full weighted score declined to 0.553. The source prior therefore provides no measured ranking gain here.
- Actual cost was CNY 0.076725 for 139 provider attempts. Prefix caching saved CNY 0.029338 (27.66%), while structural artifact reuse avoided 450 calls relative to 600 naive independent calls.

The evidence intersection retains only 7/12 naturalistic and 6/10 long reports. These are conditional complete-case results, not full-pipeline accuracy or real-user validation. See `verifier-runs/full-v2/report.md` for the paired component tables, eight-stage audit, slices, failures, cost evidence, provenance, and limitations.

Reproduce the formal report and exact artifact regression without provider calls:

```bash
PYTHONPATH=src .venv/bin/python scripts/report_phase3_verifier_experiment.py
PYTHONPATH=src .venv/bin/python -m pytest tests/unit/test_phase3_verifier_reporting.py -q
```

## Phase 3 acceptance

`acceptance.md` maps the two frozen experiment reports to every GitHub Issue #4 acceptance criterion. The overall result is `PASSED`: the three RAG/HITL configurations, quality and cost metrics, verifier component ablations, eight-stage audit, negative cases, provenance, and reproduction commands are all present.

The acceptance does not claim that every component helped. RAG produced no requirement-accuracy gain, simulated HITL required a 97% record edit rate, long-report hybrid extraction regressed, and full verifier weighting reduced AUROC. Real reviewer time and real-user value remain Phase 4 evidence.

Rebuild the acceptance report without provider calls:

```bash
PYTHONPATH=src .venv/bin/python scripts/report_phase3_acceptance.py
PYTHONPATH=src .venv/bin/python -m pytest tests/unit/test_phase3_acceptance.py -q
```
