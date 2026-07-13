# Phase 2 human annotation rubric

## Goal

Create human ground truth for the 100 frozen discussions in
`discussions.jsonl`. Every record requires an independent primary annotation
and a second-person review. Automated or LLM-generated labels do not count as
human review.

## Workflow

1. The primary annotator reads the title, content, and source URL, then fills
   every `primary_*` field in `annotations.csv` without seeing model output.
2. A different reviewer checks the source and primary labels, then sets
   `review_status` to `agree` or `revised`.
3. For `agree`, copy the accepted values into every `final_*` field. For
   `revised`, enter the adjudicated values and list changed field names in
   `review_fields_changed` separated by semicolons.
4. Run the validator. The review is complete only when it reports 100 complete
   rows and zero errors.

Reviewer IDs should be stable pseudonyms such as `reviewer_a`; do not put names
or email addresses in the dataset.

### Resource-constrained agent-assisted protocol

When two independent human annotators are unavailable, use the documented
fallback applied in this repository:

1. Two agents independently blind-label all 100 records.
2. Compare all eight fields and preserve every disagreement.
3. A human reviews every `requirement_present` disagreement without being
   forced to choose either agent.
4. Merge labels while preserving `adjudication_source` and
   `human_requirement_reviewed` on every record.

This protocol is complete when both agent files contain the same 100 unique
IDs, every requirement-presence disagreement has a valid human decision, and
the merged file contains 100 records. Report it as **agent-assisted annotation
with targeted human review**, including the human coverage rate. It must not be
described as full human annotation or inter-annotator agreement between humans.

## Field rules

### Requirement present

- `yes`: the author states or clearly implies a desired capability, improvement,
  workaround replacement, or outcome for an AI/software tool.
- `no`: news, tutorials, pure explanation, promotion, or status reporting with
  no user need attributable to the discussion author.
- `unclear`: plausible need signals exist, but the author intent cannot be
  resolved from the sampled text.

For `no`, leave title, description, pain point, and use case empty; use
`sentiment=mild`, `emotion=neutral`, and still label evidence clarity.

### Title and description

- `title`: one concise need, using source terminology and no invented feature.
- `description`: what capability or outcome is wanted and any explicit
  constraints. Do not infer business context absent from the source.

### Pain point

Record the concrete obstacle, loss, failure, or unwanted manual work stated in
the source. Leave empty when no pain point is expressed. Generic phrases such
as "needs a better tool" are not acceptable unless that is all the source says.

### Use case

Record the task, actor/context, and expected result supported by the source.
Leave empty when the discussion provides no concrete usage context.

### Sentiment strength

- `strong`: explicit urgency or action intent plus a concrete material impact,
  repeated failed alternatives, or a current high-frequency critical blockage.
- `moderate`: a clear desired capability or inconvenience without severe
  consequences or urgency.
- `mild`: vague interest, optional improvement, information seeking, or no
  attributable requirement.

### Emotion

- `positive`: praise, excitement, satisfaction, or optimistic anticipation.
- `negative`: frustration, disappointment, anger, anxiety, or regret.
- `neutral`: factual or balanced language without a dominant emotional valence.

### Evidence clarity

This is the source support for the annotation, not confidence in a model.

- `clear`: the need and key fields are explicit; a reviewer should reach the
  same labels from direct phrases.
- `partial`: the need is supported but at least one key field requires bounded
  interpretation.
- `ambiguous`: requirement presence or multiple key fields remain genuinely
  uncertain.

## Review rules

- Reviewers evaluate each field, not just the overall requirement decision.
- `agree` means all final labels match the primary annotation.
- `revised` requires at least one name in `review_fields_changed` and corrected
  `final_*` values.
- Disagreements unresolved after discussion remain `pending`; they do not count
  as reviewed.
- Do not consult NeedRadar extraction output until final labels are locked.

## Completion command

```bash
PYTHONPATH=src .venv/bin/python scripts/phase2_annotations.py validate
```
