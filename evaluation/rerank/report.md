# Rerank experiment report

- Artifact hashes verified: yes
- Candidate snapshot: `5fb066c57c4a1d734dabddc243795f5176ccb1f7c609142b33a0578f5043e977`
- Frozen queries/candidates: 100/2000
- Recall: hybrid_dense_cosine_lexical_ngram_rrf Top 20
- Recall P50/P95: 10.879 / 12.539 ms
- Label status: missing human labels
- Selection: **blocked** - Human relevance labels are incomplete.

## System comparison

| Model | Success | API P50 ms | API P95 ms | E2E P95 ms | Tokens | Cost CNY | Failures |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `BAAI/bge-reranker-v2-m3` | 31/31 | 414.166 | 856.772 | 918.290 | 284747 | 0.000000 | 0 |
| `Qwen/Qwen3-Reranker-0.6B` | 31/31 | 422.575 | 524.147 | 535.452 | 293063 | 0.020514 | 0 |

## Quality comparison

Unavailable until `labels-adjudicated.csv` and its human-review manifest are complete.

## Failures and negative cases

Failure types: `{}`
Negative-benefit cases are unavailable without labels and completed model responses.

## Limitations

- Hybrid recall uses deterministic dense cosine plus n-gram full-text reciprocal-rank fusion.
- No production capability or model advantage is claimed without completed human relevance labels and both model runs.
- Provider model revisions are not immutable, so later runs may drift.
- Context token change is a conservative UTF-8 byte upper bound, not provider tokenizer output.

Real API smoke validated 62 successful request/response paths. It does not establish full frozen-set quality or production reliability.
