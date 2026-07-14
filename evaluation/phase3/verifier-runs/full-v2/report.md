# Phase 3 verifier component ablation and eight-stage audit

## Executive summary

- Run status: `complete_with_stage_failures`; all 30 records completed.
- Paired denominators are 29 for extraction, 23 for evidence, and 23 for score composition.
- Hybrid extraction F1 is 0.753, compared with 0.597 for rule-only.
- 800-character evidence macro-F1 is 0.448; 200-character evidence macro-F1 is 0.421.
- Full-weighted ranking AUROC is 0.553; fact-only AUROC is 0.568.
- Actual cost is CNY 0.076725; prefix caching saved 27.66% and structural reuse saved 450 calls.

## Component ablation

### Claim extraction

| Configuration | Precision | Recall | F1 | Tail recall |
| --- | ---: | ---: | ---: | ---: |
| `rule_only` | 1.000 | 0.425 | 0.597 | 0.400 |
| `llm_only` | 0.847 | 0.575 | 0.685 | 0.000 |
| `hybrid` | 0.866 | 0.667 | 0.753 | 0.300 |

### Evidence context

| Configuration | Macro-F1 | Hallucination precision | Hallucination recall | Flagged F1 |
| --- | ---: | ---: | ---: | ---: |
| `no_evidence` | 0.018 | 0.000 | 0.000 | 0.000 |
| `titles_only` | 0.405 | 0.455 | 1.000 | 0.615 |
| `snippet_200` | 0.421 | 0.500 | 1.000 | 0.583 |
| `snippet_800` | 0.448 | 0.556 | 1.000 | 0.640 |

### Score composition

| Configuration | AUROC | Average precision |
| --- | ---: | ---: |
| `fact_only` | 0.568 | 0.592 |
| `fact_consistency` | 0.568 | 0.585 |
| `full_weighted` | 0.553 | 0.583 |

## Stage failures

- `e1121b612f955555` (stackoverflow, controlled, short): claim_extraction failed after 1 retry.
- `a97e2185ebedb355` (stackoverflow, controlled, short): fact_check failed after 1 retry.

## Eight-stage audit

1. Input loading: 30/30 succeeded.
2. Claim extraction: hybrid F1 0.753 on the paired extraction set.
3. Source resolution: 60/60 references resolved.
4. Fact checking: macro-F1 0.421; flagged F1 0.583.
5. Consistency: precision 0.500, recall 0.333, F1 0.400 on all 30 reports.
6. Source prior: mean 62.833; AUROC delta versus fact+consistency -0.015.
7. Aggregation: AUROC 0.553; average precision 0.583.
8. Suggestions: precision 0.769, recall 0.556, unsupported rate 0.231.

## Cost and reuse

- Provider attempts: 139 (139 with usage).
- Final-stage calls: 132; superseded retry history: 7 calls.
- Tokens: 64,169 input, 20,526 output, 29,696 cached.
- Actual cost: CNY 0.076725; no-cache counterfactual: CNY 0.106063.
- Provider-cache savings: CNY 0.029338 (27.66%).
- Structural artifact reuse: 450 calls saved versus 600 naive calls.

## Slices

### platform

| Value | Extraction n | Rule F1 | Hybrid F1 | Evidence n | 800-char flagged F1 | AUROC | AP |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `github` | 10 | 0.537 | 0.772 | 9 | 0.667 | 0.475 | 0.656 |
| `juejin` | 10 | 0.723 | 0.667 | 7 | 0.750 | 0.833 | 0.833 |
| `stackoverflow` | 9 | 0.500 | 0.826 | 7 | 0.500 | 0.542 | 0.476 |

### length_bucket

| Value | Extraction n | Rule F1 | Hybrid F1 | Evidence n | 800-char flagged F1 | AUROC | AP |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `long` | 10 | 0.636 | 0.571 | 6 | 0.571 | 0.333 | 0.500 |
| `medium` | 10 | 0.605 | 0.830 | 9 | 0.444 | 0.525 | 0.706 |
| `short` | 9 | 0.541 | 0.814 | 8 | 0.889 | 0.688 | 0.747 |

### stratum

| Value | Extraction n | Rule F1 | Hybrid F1 | Evidence n | 800-char flagged F1 | AUROC | AP |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `controlled` | 17 | 0.841 | 0.894 | 16 | 0.588 | 0.523 | 0.533 |
| `naturalistic` | 12 | 0.000 | 0.533 | 7 | 0.750 | 0.667 | 0.830 |

## Limitations

- Component deltas use paired available records, not all 30 reports.
- Five successful extractions returned no hybrid claims; one additional extraction failed.
- One extraction response and one snippet-200 fact-check response failed after a retry.
- The evidence intersection retains 7/12 naturalistic and 6/10 long reports, so slices are descriptive only.
- Controlled corruptions and agent-adjudicated naturalistic gold are proxy evidence, not human-user validation.
- Platform remains confounded with source content type, and source-reliability weights are heuristic priors.
