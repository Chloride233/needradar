# Rerank Top-3 pilot report

- Queries: 30
- Judged Top-3 union candidates: 192
- Labels: single_expert_test_retest_validated
- Selection: **inconclusive_add_batch** - Pilot uncertainty or a quality/system tradeoff remains; Batch 2 may be proposed but not executed automatically.

## System metrics

| Model | Success | API P95 ms | Tokens | Cost CNY | Failures |
| --- | ---: | ---: | ---: | ---: | ---: |
| `BAAI/bge-reranker-v2-m3` | 30/30 | 868.9153999999993 | 272986 | 0.000000 | 0 |
| `Qwen/Qwen3-Reranker-0.6B` | 30/30 | 500.5683 | 281243 | 0.019687 | 0 |

## Quality

| System | MRR@3 | nDCG@3 | Pooled Recall@3 | Precision@3 | Irrelevant Top-3 |
| --- | ---: | ---: | ---: | ---: | ---: |
| `none` | 0.2667 | 0.2365 | 0.2310 | 0.1667 | 0.8333 |
| `BAAI/bge-reranker-v2-m3` | 0.3778 | 0.3460 | 0.3810 | 0.2778 | 0.7222 |
| `Qwen/Qwen3-Reranker-0.6B` | 0.4611 | 0.4170 | 0.4393 | 0.3000 | 0.7000 |

## Pool coverage

- Queries with at least one relevant pooled candidate: 18/30
- All-zero pooled queries: 12/30
- Answerable-only metrics are post-hoc sensitivity analysis, not primary decision evidence.

## Limitations

- This pilot evaluates only the frozen three-system Top-3 union.
- Pooled Recall@3 is not recall against all Recall Top-20 candidates.
- MRR@10, nDCG@10, and relevance-gate calibration are not supported by this pilot.
- Single-expert test-retest labels are not multi-reviewer consensus.
- Retest began after 0.000649 hours, so agreement measures immediate self-consistency rather than delayed temporal stability.
