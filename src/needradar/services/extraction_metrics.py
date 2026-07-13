from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

TEXT_FIELDS = ("title", "description", "pain_point", "use_case")
CATEGORICAL_FIELDS = ("sentiment", "emotion")
CLARITY_CONFIDENCE = {"clear": 0.9, "partial": 0.65, "ambiguous": 0.4}
SOURCE_CONTENT_TYPES = {
    "github": "issue",
    "stackoverflow": "question",
    "juejin": "article",
}


def _load_jsonl(path: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        record = json.loads(line)
        record_id = record.get("id")
        if not record_id or record_id in records:
            raise ValueError(f"{path}:{line_number}: missing or duplicate id")
        records[record_id] = record
    return records


def _normalize(text: str) -> str:
    return re.sub(r"[^\w]+", "", text.casefold(), flags=re.UNICODE)


def _char_ngram_dice(first: str, second: str, size: int = 2) -> float:
    first_normalized = _normalize(first)
    second_normalized = _normalize(second)
    if not first_normalized and not second_normalized:
        return 1.0
    if not first_normalized or not second_normalized:
        return 0.0
    if len(first_normalized) < size or len(second_normalized) < size:
        return float(first_normalized == second_normalized)
    first_ngrams = Counter(first_normalized[index : index + size] for index in range(len(first_normalized) - size + 1))
    second_ngrams = Counter(
        second_normalized[index : index + size] for index in range(len(second_normalized) - size + 1)
    )
    overlap = sum((first_ngrams & second_ngrams).values())
    return 2 * overlap / (sum(first_ngrams.values()) + sum(second_ngrams.values()))


def _failure_summary(
    record_ids: list[str],
    gold: dict[str, dict[str, Any]],
    predictions: dict[str, dict[str, Any]],
    per_record_text: dict[str, dict[str, float]],
) -> dict[str, Any]:
    gold_yes = [record_id for record_id in record_ids if gold[record_id]["requirement_present"] == "yes"]
    gold_no = [record_id for record_id in record_ids if gold[record_id]["requirement_present"] == "no"]
    comparable_yes = [record_id for record_id in gold_yes if predictions[record_id]["requirement_present"] == "yes"]
    confusion = {
        "true_positive": sum(predictions[record_id]["requirement_present"] == "yes" for record_id in gold_yes),
        "true_negative": sum(predictions[record_id]["requirement_present"] == "no" for record_id in gold_no),
        "false_positive": sum(predictions[record_id]["requirement_present"] == "yes" for record_id in gold_no),
        "false_negative": sum(predictions[record_id]["requirement_present"] == "no" for record_id in gold_yes),
        "error": sum(predictions[record_id]["requirement_present"] == "error" for record_id in record_ids),
    }
    failures = {
        "false_positive_requirement": {
            "count": confusion["false_positive"],
            "total": len(gold_no),
        },
        "false_negative_requirement": {
            "count": confusion["false_negative"],
            "total": len(gold_yes),
        },
        "sentiment_mismatch": {
            "count": sum(
                gold[record_id]["sentiment"] != predictions[record_id]["sentiment"] for record_id in comparable_yes
            ),
            "total": len(comparable_yes),
        },
        "emotion_mismatch": {
            "count": sum(
                gold[record_id]["emotion"] != predictions[record_id]["emotion"] for record_id in comparable_yes
            ),
            "total": len(comparable_yes),
        },
    }
    for field in TEXT_FIELDS:
        failures[f"{field}_similarity_below_0_5"] = {
            "count": sum(per_record_text[record_id][field] < 0.5 for record_id in comparable_yes),
            "total": len(comparable_yes),
        }
    for failure in failures.values():
        failure["rate"] = failure["count"] / failure["total"] if failure["total"] else 0.0
    return {
        "record_count": len(record_ids),
        "requirement_presence_confusion": confusion,
        "failure_modes": failures,
        "dominant_failure_modes": [
            {"name": name, **values}
            for name, values in sorted(
                failures.items(),
                key=lambda item: (-item[1]["count"], item[0]),
            )
            if values["count"]
        ],
    }


def score_extractions(
    gold_path: Path,
    prediction_path: Path,
    discussion_path: Path,
) -> dict[str, Any]:
    gold = _load_jsonl(gold_path)
    predictions = _load_jsonl(prediction_path)
    discussions = _load_jsonl(discussion_path)
    if set(gold) != set(predictions):
        raise ValueError("gold and prediction IDs must match")
    if set(gold) != set(discussions):
        raise ValueError("gold and discussion IDs must match")

    total = len(gold)
    accepted_ids = [
        record_id for record_id, prediction in predictions.items() if prediction["requirement_present"] == "yes"
    ]
    rejected_ids = [
        record_id for record_id, prediction in predictions.items() if prediction["requirement_present"] == "no"
    ]
    failed_ids = [
        record_id for record_id, prediction in predictions.items() if prediction["requirement_present"] == "error"
    ]
    gold_no = {record_id for record_id, record in gold.items() if record["requirement_present"] == "no"}
    predicted_no = set(rejected_ids)
    comparable_yes = [
        record_id
        for record_id in gold
        if gold[record_id]["requirement_present"] == "yes" and predictions[record_id]["requirement_present"] == "yes"
    ]

    categorical_accuracy = {}
    for field in CATEGORICAL_FIELDS:
        agreed = sum(gold[record_id][field] == predictions[record_id][field] for record_id in comparable_yes)
        categorical_accuracy[field] = {
            "correct": agreed,
            "total": len(comparable_yes),
            "accuracy": agreed / len(comparable_yes) if comparable_yes else 0.0,
        }

    text_similarity = {}
    per_record_text: dict[str, dict[str, float]] = {}
    for field in TEXT_FIELDS:
        values = {
            record_id: _char_ngram_dice(gold[record_id][field], predictions[record_id][field])
            for record_id in comparable_yes
        }
        for record_id, value in values.items():
            per_record_text.setdefault(record_id, {})[field] = value
        text_similarity[field] = {
            "total": len(values),
            "mean_dice": sum(values.values()) / len(values) if values else 0.0,
            "at_or_above_0_5": sum(value >= 0.5 for value in values.values()),
        }

    edit_ids = set()
    for record_id in gold:
        expected = gold[record_id]
        actual = predictions[record_id]
        if expected["requirement_present"] != actual["requirement_present"]:
            edit_ids.add(record_id)
        elif expected["requirement_present"] == "yes" and (
            any(expected[field] != actual[field] for field in CATEGORICAL_FIELDS)
            or any(value < 0.5 for value in per_record_text.get(record_id, {}).values())
        ):
            edit_ids.add(record_id)

    audited_ids = {record_id for record_id, record in gold.items() if record.get("human_requirement_reviewed")}
    audited_edits = sum(
        gold[record_id]["requirement_present"] != predictions[record_id]["requirement_present"]
        for record_id in audited_ids
    )
    titles = [_normalize(predictions[record_id]["title"]) for record_id in accepted_ids]
    duplicate_count = sum(count - 1 for count in Counter(title for title in titles if title).values() if count > 1)

    confidence_errors = [
        abs(float(predictions[record_id]["confidence"]) - CLARITY_CONFIDENCE[gold[record_id]["evidence_clarity"]])
        for record_id in comparable_yes
        if predictions[record_id].get("confidence") is not None
    ]
    requirement_correct = sum(
        gold[record_id]["requirement_present"] == predictions[record_id]["requirement_present"] for record_id in gold
    )
    platform_groups: dict[str, list[str]] = {}
    content_type_groups: dict[str, list[str]] = {}
    for record_id, discussion in discussions.items():
        platform = discussion["platform"]
        if platform not in SOURCE_CONTENT_TYPES:
            raise ValueError(f"unsupported evaluation platform: {platform}")
        platform_groups.setdefault(platform, []).append(record_id)
        content_type_groups.setdefault(SOURCE_CONTENT_TYPES[platform], []).append(record_id)

    return {
        "methodology": "proxy gold: two-agent blind annotation with 7% targeted human review",
        "record_count": total,
        "requirement_presence": {
            "correct": requirement_correct,
            "accuracy": requirement_correct / total if total else 0.0,
        },
        "categorical_field_accuracy": categorical_accuracy,
        "text_field_similarity": text_similarity,
        "rejection": {
            "count": len(rejected_ids),
            "rate": len(rejected_ids) / total if total else 0.0,
            "precision": len(gold_no & predicted_no) / len(predicted_no) if predicted_no else 0.0,
            "recall": len(gold_no & predicted_no) / len(gold_no) if gold_no else 0.0,
        },
        "extraction_failures": {
            "count": len(failed_ids),
            "rate": len(failed_ids) / total if total else 0.0,
        },
        "duplicates": {
            "count": duplicate_count,
            "rate_among_accepted": duplicate_count / len(accepted_ids) if accepted_ids else 0.0,
        },
        "proxy_record_edit_rate": {
            "count": len(edit_ids),
            "rate": len(edit_ids) / total if total else 0.0,
        },
        "human_audited_requirement_edit_rate": {
            "count": audited_edits,
            "total": len(audited_ids),
            "rate": audited_edits / len(audited_ids) if audited_ids else 0.0,
        },
        "confidence_calibration": {
            "count": len(confidence_errors),
            "mean_absolute_error": sum(confidence_errors) / len(confidence_errors) if confidence_errors else None,
        },
        "failure_analysis": {
            "content_type_by_platform": SOURCE_CONTENT_TYPES,
            "platform_content_type_relationship": "one-to-one in this query-stratified sample",
            "by_platform": {
                platform: _failure_summary(record_ids, gold, predictions, per_record_text)
                for platform, record_ids in sorted(platform_groups.items())
            },
            "by_content_type": {
                content_type: _failure_summary(record_ids, gold, predictions, per_record_text)
                for content_type, record_ids in sorted(content_type_groups.items())
            },
        },
    }
