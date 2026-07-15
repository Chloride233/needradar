# Rerank Top-3 pilot

This directory contains the sequential reduced-review experiment. Batch 1 uses 30 deterministically stratified frozen test queries and at most 60 provider requests. Human review covers only the deduplicated union of baseline, BGE, and Qwen3 Top 3 candidates.

## No-cost preparation

```bash
PYTHONPATH=src .venv/bin/python scripts/run_rerank_pilot.py --prepare --batch 1
```

The command freezes selected query IDs and prints the provider request ceiling, conservative token estimate, current pricing, and proposed hard budget. It does not read an API key or make a network request.

## Approval-gated execution

```bash
PYTHONPATH=src .venv/bin/python scripts/run_rerank_pilot.py \
  --execute --batch 1 --max-cost-cny <approved-budget>
```

After all selected responses are cached:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_rerank_pilot.py --build-pool --batch 1
PYTHONPATH=src .venv/bin/python scripts/run_rerank_review.py \
  --template evaluation/rerank/pilot/annotation-template.csv --port 8765
```

Place the four exported review files in this directory, then run:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_rerank_pilot.py --rebuild-report --batch 1
```

Batch 2 is never automatic. It can be prepared only when the validated Batch 1 report has status `inconclusive_add_batch`, and its paid execution requires separate authorization.

Pilot evidence supports `MRR@3`, `nDCG@3`, `Precision@3`, irrelevant Top-3 rate, and pooled Recall@3 over the judged three-system union. It does not support MRR@10, nDCG@10, full candidate recall, or relevance-gate calibration.
