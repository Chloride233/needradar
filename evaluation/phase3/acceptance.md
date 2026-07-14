# Phase 3 acceptance report

Status: **PASSED**

## Issue #4 checklist

- [x] Compare no RAG, RAG, and RAG plus HITL — `evaluation/phase3/full-report.md`
- [x] Measure accuracy, duplication, edit rate, tokens, and cost — `evaluation/phase3/full-report.json`
- [x] Ablate verifier components and audit all eight stages — `evaluation/phase3/verifier-runs/full-v2/report.md`
- [x] Analyze limited and negative gains — `evaluation/phase3/full-report.md and verifier-runs/full-v2/report.md`
- [x] Publish reproducible configuration and reports — `evaluation/phase3/README.md and artifact regression tests`

## Evidence summary

- RAG/HITL: 100 records per configuration; requirement accuracy 49.00% without RAG and 49.00% with RAG; cost change +20.10%.
- Simulated HITL: 97.00% record edit rate and 437 edited fields.
- Verifier: paired extraction/evidence/score denominators 29/23/23; hybrid extraction F1 0.753.
- Ranking: fact-only AUROC 0.568; full-weighted AUROC 0.553.
- Verifier cost: CNY 0.076725; provider cache saved 27.66%.

## Conclusions

- RAG did not improve requirement-presence accuracy and increased cost and duplication.
- Simulated HITL reached proxy-perfect post-review output only by editing 97% of records; it is not model quality.
- Hybrid claim extraction improved aggregate F1, but regressed on long reports and tail recall.
- Longer evidence improved verdict classification, while report-level ranking remained weak.
- Consistency and source-prior weighting did not improve AUROC; full weighting reduced it.

## Phase 4 handoff

- Measure real reviewer time and edit burden instead of simulated HITL only.
- Evaluate long-report extraction and structured-output failures before production automation.
- Keep fact-only scoring as the evidence-backed baseline until source priors show a gain.

## Reproduce

```bash
PYTHONPATH=src .venv/bin/python scripts/report_phase3_acceptance.py
PYTHONPATH=src .venv/bin/python -m pytest tests/unit/test_phase3_acceptance.py -q
```
