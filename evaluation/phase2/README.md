# Phase 2 discussion sample

This directory contains the frozen input sample for measuring requirement
extraction quality. It was collected on 2026-07-13 from anonymous public
endpoints without LLM calls or paid API keys.

## Sampling frame

| Platform | Query | Quota |
| --- | --- | ---: |
| GitHub Issues | `AI tool` | 34 |
| Stack Overflow questions | `AI tool` | 33 |
| Juejin articles | `AI 工具` | 33 |

The sample contains 100 unique source URLs. Records retain the source URL,
title, discussion content, and tags needed for evaluation. Author fields are
not stored. This is a query-stratified relevance sample, not a representative
estimate of all content on any platform.

## Reproduce

```bash
PYTHONPATH=src .venv/bin/python scripts/sample_phase2_discussions.py
```

The command refuses to write a dataset if any platform returns fewer unique
records than its quota. `manifest.json` records the platform counts, queries,
generation time, and SHA-256 of `discussions.jsonl`.

## Human annotation

Follow `annotation-rubric.md` and edit `annotations.csv`. Two different human
reviewer IDs are required for every record. Check completion with:

```bash
PYTHONPATH=src .venv/bin/python scripts/phase2_annotations.py validate
```

## Agent pre-annotation

Two independent agents blind-labeled all 100 records without reading each
other's output. Their files are `annotations_agent_a.jsonl` and
`annotations_agent_b.jsonl`. Compare them with:

```bash
PYTHONPATH=src .venv/bin/python scripts/compare_phase2_agent_annotations.py \
  evaluation/phase2/annotations_agent_a.jsonl \
  evaluation/phase2/annotations_agent_b.jsonl \
  --conflicts evaluation/phase2/agent-conflicts.jsonl
```

Agreement was 93% for requirement presence, 82% for sentiment, 91% for
emotion, and 93% for evidence clarity. Exact-string agreement for free-text
fields ranged from 47% to 57%, so those rates should not be interpreted as
semantic disagreement. The 55-record conflict file includes every exact field
difference for adjudication. Agent labels are pre-annotations and do not count
as completed human review.

The seven requirement-presence disagreements were human-reviewed. The reviewer
selected Agent A five times, Agent B once, and overrode both agents once. The
merged `annotations_adjudicated.jsonl` contains 47 `yes` and 53 `no` labels and
marks the seven reviewed records with `human_requirement_reviewed=true`. This
is a 7% targeted human audit, not a claim that all 100 records were manually
annotated.

## Extraction metrics

Run the resumable NeedRadar benchmark after configuring a DeepSeek key:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_phase2_extractions.py
PYTHONPATH=src .venv/bin/python scripts/score_phase2_extractions.py \
  evaluation/phase2/needradar_predictions.jsonl \
  --output evaluation/phase2/needradar_metrics.json
```

The benchmark disables RAG to isolate extraction behavior, applies the same
rule-based noise filter used by the pipeline, saves after every item, and
records token usage and CNY cost. The scorer reports categorical accuracy,
Unicode character-bigram text similarity, rejection precision/recall, normalized-title
duplicate rate, proxy edit rate, and the edit rate on human-audited records.
It also joins the frozen discussion metadata to report failure modes by
platform and source content type. In this sample those dimensions are
one-to-one: GitHub issue, Stack Overflow question, and Juejin article.

Run the offline regression without an API key or model calls:

```bash
PYTHONPATH=src .venv/bin/python -m pytest \
  tests/unit/test_extraction_metrics.py \
  tests/unit/test_phase2_dataset.py -q
```

The dataset test validates the frozen sample SHA-256 and requires a fresh
metric calculation from the frozen annotations and predictions to exactly
match `needradar_metrics.json`.
