# Phase 4 User-Study Protocol

Date: 2026-07-14

## Purpose and Boundary

This protocol measures the path from a participant-provided keyword to an
insight report. It is a future real-user study plan, not evidence that a user
study has occurred. Recruitment, real external crawling, and any paid model
run require separate approval before execution.

## Privacy and Consent

- Record an anonymous `session_id`; do not record names, emails, handles, IP
  addresses, raw prompts, source discussions, or report text in the ledger.
- Before timing begins, explain the local record fields and obtain explicit
  agreement. A row with `consent_confirmed` other than `yes` is rejected.
- Store the ledger locally and only publish aggregate counts. Remove free-text
  failure notes that contain personal or sensitive information before sharing.
- A participant can stop at any time; record `abandoned` without an adoption
  result and without inferring a reason.

## Session Record

Use [user-study-template.csv](user-study-template.csv). One row represents one
attempt, from the first submitted keyword through a completed, abandoned, or
failed outcome.

| Field | Meaning |
| --- | --- |
| `session_id` | Study-local anonymous identifier, unique within the file. |
| `started_at`, `completed_at` | ISO-8601 timestamps used to calculate elapsed seconds. |
| `keyword` | The keyword used for the task; avoid personal or sensitive queries. |
| `outcome` | `completed`, `abandoned`, or `failed`. |
| `insights_considered`, `insights_adopted` | Count reviewed and count the participant says they will act on. Adoption is never inferred. |
| `manual_edits` | Number of explicit material, requirement, or report edits. |
| `failure_stage` | `none`, `crawl`, `extraction`, `report`, `verification`, `review`, or `other`. |
| `failure_note` | Optional, de-identified description; it is not required to explain abandonment. |

## Aggregate Report

```bash
PYTHONPATH=src .venv/bin/python scripts/report_phase4_user_study.py \
  evaluation/phase4/user-study.csv \
  evaluation/phase4/user-study-summary.json
```

The command rejects missing consent, invalid timestamps, negative counts,
adopted counts greater than considered counts, invalid outcome/stage values,
and duplicate session IDs. It reports exact session count, completion rate,
median elapsed seconds, edit burden, adoption rate, and failure-point counts.

The Issue #3 report must state the exact number of consented sessions and must
not generalize synthetic fixtures or a small convenience sample into product
adoption evidence.
