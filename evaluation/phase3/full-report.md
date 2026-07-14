# Phase 3 RAG and HITL experiment report

## Executive summary

- Requirement-presence accuracy was 49.00% without RAG and 49.00% with RAG.
- RAG changed emotion accuracy by +8.51 percentage points, description similarity by -3.46 points, and pain-point similarity by -1.41 points.
- RAG increased tokens by 17.08% and actual cost by 20.10%.
- Simulated HITL edited 97/100 records (97.00%); post-review accuracy is proxy-assisted, not model quality.
- Prefix caching reduced combined cost from CNY 1.106998 to CNY 0.393868, saving 64.42%.

## Configuration results

| Configuration | Requirement accuracy | Sentiment | Emotion | Proxy edit rate | Tokens | Cost (CNY) | Cache hit |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `no_rag` | 49.00% | 59.57% | 65.96% | 98.00% | 277,611 | 0.118799 | 94.90% |
| `rag` | 49.00% | 59.57% | 74.47% | 98.00% | 325,039 | 0.142683 | 97.24% |
| `rag_hitl` | 100.00% | 100.00% | 100.00% | 0.00% | 320,109 | 0.132386 | 97.40% |

## RAG ablation

| Metric | No RAG | RAG | Absolute change | Relative change |
| --- | ---: | ---: | ---: | ---: |
| `requirement_presence_accuracy` | 0.490000 | 0.490000 | +0.000000 | 0.00% |
| `sentiment_accuracy` | 0.595745 | 0.595745 | +0.000000 | 0.00% |
| `emotion_accuracy` | 0.659574 | 0.744681 | +0.085106 | 12.90% |
| `title_mean_dice` | 0.494657 | 0.501700 | +0.007043 | 1.42% |
| `description_mean_dice` | 0.403962 | 0.369383 | -0.034579 | -8.56% |
| `pain_point_mean_dice` | 0.370413 | 0.356301 | -0.014112 | -3.81% |
| `use_case_mean_dice` | 0.326717 | 0.339483 | +0.012767 | 3.91% |
| `duplicate_rate` | 0.000000 | 0.010204 | +0.010204 | n/a |
| `proxy_edit_rate` | 0.980000 | 0.980000 | +0.000000 | 0.00% |
| `total_tokens` | 277611.000000 | 325039.000000 | +47428.000000 | 17.08% |
| `cost_cny` | 0.118799 | 0.142683 | +0.023884 | 20.10% |

Requirement-presence correctness transitions: 0 improved, 0 worsened, and 100 unchanged.

### Categorical correctness transitions

| Field | Improved | Worsened | Unchanged |
| --- | ---: | ---: | ---: |
| sentiment | 5 | 5 | 37 |
| emotion | 8 | 4 | 35 |

### Platform requirement accuracy

| Platform | No RAG | RAG | Absolute change |
| --- | ---: | ---: | ---: |
| github | 61.76% | 61.76% | +0.00 points |
| juejin | 0.00% | 0.00% | +0.00 points |
| stackoverflow | 84.85% | 84.85% | +0.00 points |

## HITL burden

- Pre-review requirement accuracy: 49.00%
- Post-review requirement accuracy: 100.00%
- Edited records: 97/100 (97.00%)
- Edited fields: 437
- Field counts: `{"description": 84, "emotion": 21, "pain_point": 87, "requirement_present": 51, "sentiment": 30, "title": 72, "use_case": 92}`

## Largest RAG text-similarity changes

### Gains

- `5a372c56011806b8` (stackoverflow): +0.369 — Best AI Tools For Magento Enterprise Level Projects
- `7f5bbcd428a898ce` (stackoverflow): +0.346 — Getting started with AI tools in Python
- `f017ac0e207e5581` (stackoverflow): +0.270 — Monorepo + AI tools (Copilot, Cursor): does having full codebase context provide real advantages in practice?
- `085de6519b94ed47` (github): +0.249 — SYSTEM_PROMPT instructs the LLM to call 'query_multimodal_ai' but the registered tool is 'query_multimodal_api'
- `a922923efae8061c` (stackoverflow): +0.238 — Issues invoking Spring AI MCP tools via SSE in Spring Boot

### Regressions

- `1132979c205a2394` (stackoverflow): -0.458 — How to build an autonomous AI Agent with tool calling using the new Microsoft.Agents.AI framework in .NET?
- `76737bb8ff4f9052` (stackoverflow): -0.378 — Microsoft AI tools and database row-level security
- `02b5d65bae63f4e0` (stackoverflow): -0.302 — Tools for A9G GPRS+GPS Module of chinese AI thinker
- `10b971546306e791` (github): -0.266 — fix(ai): Skill usage telemetry를 privacy-safe versioned schema로 전환
- `d8c7c3d251404b2b` (github): -0.234 — gh shim recursively selects another aidevops shim after hot deploy

## Limitations

- The sample is query-stratified and platform is confounded with content type.
- The proxy gold has only 7% targeted human review; simulated HITL is not 100-person human evidence.
- The current retriever uses fallback-sha256-bow-384 embeddings and always injects top-3 context.
- The two RAG model runs are independent stochastic calls; HITL pre-review metrics may differ from the standalone RAG run.

## Reproduce

```bash
PYTHONPATH=src .venv/bin/python scripts/report_phase3_experiment.py
PYTHONPATH=src .venv/bin/python -m pytest tests/unit/test_phase3_reporting.py -q
```
