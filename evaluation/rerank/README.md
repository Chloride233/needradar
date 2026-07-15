# SiliconFlow rerank experiment

This experiment compares the existing no-rerank order with the exact models `BAAI/bge-reranker-v2-m3` and `Qwen/Qwen3-Reranker-0.6B`. Production behavior remains disabled by default.

Recall combines dense cosine and n-gram full-text candidates with deterministic reciprocal-rank fusion before freezing the shared Top 20.

## Recommended personal-review path

Use the reduced sequential Top-3 pilot under `evaluation/rerank/pilot/`. Batch 1 selects 30 frozen test queries and reviews only the deduplicated union of baseline, BGE, and Qwen3 Top 3 candidates. See `pilot/README.md` for commands and evidence limits.

The 2,000-row template below remains available for comprehensive qrels research but is not required for the personal project decision.

## Human review

Run the local-only blinded review tool:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_rerank_review.py
```

Open `http://127.0.0.1:8765` and follow `review-guide.md`. The accepted single-reviewer path uses a frozen first pass, deterministic hidden 10% retest, independently recomputed exact agreement and quadratic-weighted kappa, and explicit self-adjudication. It is reported as single-expert evidence, never as multi-reviewer consensus.

## No-cost workflow

```bash
PYTHONPATH=src .venv/bin/python scripts/run_rerank_experiment.py --freeze
PYTHONPATH=src .venv/bin/python scripts/run_rerank_experiment.py
PYTHONPATH=src .venv/bin/python scripts/run_rerank_experiment.py --rebuild-report
PYTHONPATH=src .venv/bin/python -m pytest tests/unit/test_reranker.py tests/unit/test_rerank_experiment.py tests/unit/test_rag_retriever.py -q
```

`--freeze` writes the shared top-20 candidate snapshot, manifest, and blind annotation template. The default command is a dry-run: it reports exact request counts, a conservative token ceiling, current public price evidence, and the proposed budget without reading an API key or sending data.

## Paid workflow

Real calls require explicit `--execute` and a positive hard budget:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_rerank_experiment.py \
  --execute --models bge --limit 1 --max-cost-cny <approved-budget>
```

Run the same single-query smoke for `qwen3` before the full comparison. Successful responses are cached under ignored `data/rerank-cache/`; failures are recorded separately and never become successful cache entries. The cache key is `(model_id, query_hash, candidate_set_hash, request_options_hash)`.

Do not run the full experiment until both smoke tests confirm the exact model IDs, response structure, token metadata, latency, and price accounting. Complete and adjudicate the human annotation package as `evaluation/rerank/labels-adjudicated.csv`, with matching provenance in `labels-adjudicated.manifest.json`, before using quality metrics to select a model. Fake-provider tests, dry-runs, and proxy labels are implementation evidence only.
