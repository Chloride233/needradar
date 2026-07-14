# Phase 3 cache smoke report

## Scope

This paid smoke run used the first five frozen Phase 2 discussions under `no_rag`, `rag`, and `rag_hitl`. It validates prompt-prefix caching, artifact accounting, retrieval, and HITL attribution. Five records are not enough to support a RAG quality claim.

All 15 model calls completed. There were no extraction or retrieval failures. Gold and adjudication records remained local.

## Results

| Configuration | Requirement accuracy | HITL edit rate | Total tokens | Cached tokens | Cache hit rate | Actual cost (CNY) | No-cache cost (CNY) | Cache savings (CNY) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `no_rag` | 80% | 0% | 18,556 | 15,488 | 98.32% | 0.006227 | 0.021529 | 0.015302 |
| `rag` | 80% | 0% | 22,541 | 15,488 | 86.70% | 0.012133 | 0.027435 | 0.015302 |
| `rag_hitl` | 100% post-review | 100% | 22,508 | 17,536 | 98.16% | 0.010044 | 0.027370 | 0.017326 |

Combined actual cost was **CNY 0.028404**. The frozen pricing counterfactual without cache hits was **CNY 0.076334**, so prefix caching saved **CNY 0.047930 (62.79%)**.

## Interpretation

- Provider prefix caching is active and materially reduces input cost.
- Keeping the system prompt stable preserved high hit rates after RAG context moved to the user input.
- RAG increased total tokens and actual cost in this sample without changing requirement-presence accuracy.
- RAG changed free-text similarity in mixed directions; the five-record sample is too small for a conclusion.
- Simulated HITL edited all five records. Its post-review accuracy is human/proxy-assisted quality, not model quality.

## Reproduce

The committed outputs are under `evaluation/phase3/runs/cache-smoke`. Recalculate the offline evidence with:

```bash
PYTHONPATH=src .venv/bin/python -m pytest \
  tests/unit/test_phase3_cache_smoke.py -q
```
