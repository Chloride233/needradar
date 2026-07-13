# Phase 2 extraction metrics

## Scope

- Dataset: 100 public discussions (GitHub 34, Stack Overflow 33, Juejin 33)
- System under test: NeedRadar rule noise filter + `requirement_extraction`
- Model: DeepSeek V4 Flash
- RAG: disabled to isolate extraction behavior
- Gold-label limitation: two-agent blind labels with targeted human review of
  all seven requirement-presence disagreements (7% human coverage)

## Results

| Metric | Result |
| --- | ---: |
| Requirement-presence accuracy | 49/100 (49.00%) |
| Sentiment accuracy on matched positive records | 30/47 (63.83%) |
| Emotion accuracy on matched positive records | 31/47 (65.96%) |
| Rejection rate | 2/100 (2.00%) |
| Rejection precision | 2/2 (100.00%) |
| Rejection recall | 2/53 (3.77%) |
| Normalized-title duplicate rate | 1/98 accepted (1.02%) |
| Persistent extraction failure rate | 0/100 (0.00%) |
| Human-audited requirement edit rate | 6/7 (85.71%) |

Free-text fields use character-bigram Dice similarity because exact matching
would penalize semantically similar Chinese and English phrasing:

| Field | Mean Dice | Records >= 0.50 |
| --- | ---: | ---: |
| Title | 43.60% | 19/47 |
| Description | 36.39% | 15/47 |
| Pain point | 32.23% | 10/47 |
| Use case | 31.42% | 6/47 |

The confidence score has 0.05 mean absolute error against a coarse mapping from
the proxy gold's evidence-clarity label. This is a calibration proxy, not a
human probability judgment.

## Failure modes by source

The three platforms have one source content type each in this sample: GitHub
issues, Stack Overflow questions, and Juejin articles. Platform and content
type results are therefore the same slices and must not be interpreted as two
independent effects.

| Platform | Content type | Gold yes / no | Presence correct | False positives | Largest field mismatch |
| --- | --- | ---: | ---: | ---: | ---: |
| GitHub | Issue | 19 / 15 | 21/34 (61.76%) | 13/15 negatives (86.67%) | Use case below 0.50 Dice: 17/19 (89.47%) |
| Stack Overflow | Question | 28 / 5 | 28/33 (84.85%) | 5/5 negatives (100.00%) | Pain point and use case below 0.50 Dice: 24/28 each (85.71%) |
| Juejin | Article | 0 / 33 | 0/33 (0.00%) | 33/33 negatives (100.00%) | Not applicable: no gold-positive records |

The primary requirement-presence failure is false acceptance, not missed
requirements. There are 51 false positives and no false negatives because the
system accepts 98 records. Juejin accounts for 33 false positives: its `AI 工具`
query returned tool roundups and trend articles, and the extraction schema
converted descriptive content into requirements instead of rejecting it.
GitHub contributes another 13 false positives, including run logs, advisory
reports, dependency dashboards, and tutorial exercises.

The lexical field metrics need a separate caution. Many Stack Overflow gold
fields preserve the English source language while the model predicts Chinese.
The character-bigram score consequently marks semantically close descriptions
as dissimilar. These counts reliably identify output-language inconsistency
and review candidates, but they do not establish semantic extraction error
without additional human review or a validated multilingual semantic metric.

The group distributions are also strongly different: Juejin has no positive
proxy-gold records, while Stack Overflow has 28/33. The platform accuracy gap
therefore combines retrieval relevance, content type, annotation, and model
behavior; it is not a controlled estimate of platform-specific model quality.

## Interpretation

The dominant problem is rejection recall. The production rule filter rejects
only very short, non-technical-keyword, or repetitive content, while the
extraction schema always requires a requirement object. As a result, 98 of 100
records are accepted even though the adjudicated proxy gold contains only 47
positive records.

The 85.71% human-audited edit rate is deliberately measured on the seven cases
where the two annotating agents disagreed about requirement presence. It is a
high-risk-slice metric and must not be presented as the population edit rate.
The automated all-field proxy flags 98% of records under a strict text
similarity threshold; that number is diagnostic only and is not a human edit
rate.

## Cost evidence

The run completed 100/100 records with two rule rejections and zero persistent
LLM failures. The resumable runner recorded 91,860 tokens and CNY 0.054832 for
the final 43 records. Usage for the first 57 records was not persisted by the
initial runner version before a malformed JSON response interrupted the run,
so an exact whole-run cost is unavailable. The pre-run conservative estimate
was CNY 0.374.

## Reproduce

```bash
PYTHONPATH=src .venv/bin/python scripts/score_phase2_extractions.py \
  evaluation/phase2/needradar_predictions.jsonl \
  --output evaluation/phase2/needradar_metrics.json

PYTHONPATH=src .venv/bin/python -m pytest \
  tests/unit/test_extraction_metrics.py \
  tests/unit/test_phase2_dataset.py -q
```

The offline regression test recomputes the report from the frozen discussion,
adjudicated annotation, and prediction JSONL files and requires exact equality
with `needradar_metrics.json`. It makes metric drift visible without repeating
paid model calls.
