from __future__ import annotations

from collections import Counter
from typing import Any

VERDICTS = ("supported", "partially", "unverifiable", "contradicted", "hallucination")
FLAGGED_VERDICTS = {"contradicted", "hallucination"}
SCORE_WEIGHTS = {"fact": 0.45, "consistency": 0.30, "source": 0.25}


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _classification_metrics(true_positive: int, false_positive: int, false_negative: int) -> dict[str, float]:
    precision = _ratio(true_positive, true_positive + false_positive)
    recall = _ratio(true_positive, true_positive + false_negative)
    return {
        "precision": precision,
        "recall": recall,
        "f1": _ratio(2 * precision * recall, precision + recall),
    }


def compose_score(
    fact_score: float | None,
    consistency_score: float | None,
    source_score: float | None,
) -> float | None:
    if fact_score is None:
        return None
    available = {
        "fact": fact_score,
        "consistency": consistency_score,
        "source": source_score,
    }
    denominator = sum(SCORE_WEIGHTS[name] for name, value in available.items() if value is not None)
    return sum(SCORE_WEIGHTS[name] * value for name, value in available.items() if value is not None) / denominator


def _auroc(labels: list[bool], risks: list[float]) -> float | None:
    positives = [risk for label, risk in zip(labels, risks) if label]
    negatives = [risk for label, risk in zip(labels, risks) if not label]
    if not positives or not negatives:
        return None
    wins = sum(
        1.0 if positive > negative else 0.5 if positive == negative else 0.0
        for positive in positives
        for negative in negatives
    )
    return wins / (len(positives) * len(negatives))


def _average_precision(labels: list[bool], risks: list[float]) -> float | None:
    positive_count = sum(labels)
    if not positive_count:
        return None
    ranked = sorted(zip(risks, labels), reverse=True)
    found = 0
    precision_sum = 0.0
    rank = 0
    index = 0
    while index < len(ranked):
        risk = ranked[index][0]
        group_positive = 0
        group_size = 0
        while index < len(ranked) and ranked[index][0] == risk:
            group_positive += int(ranked[index][1])
            group_size += 1
            index += 1
        found += group_positive
        rank += group_size
        precision_sum += group_positive * found / rank
    return precision_sum / positive_count


def score_verifier_predictions(
    inputs: list[dict[str, Any]],
    gold_records: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
) -> dict[str, Any]:
    input_by_id = {record["id"]: record for record in inputs}
    gold_by_id = {record["id"]: record for record in gold_records}
    prediction_by_id = {record["id"]: record for record in predictions}
    if set(input_by_id) != set(gold_by_id) or set(gold_by_id) != set(prediction_by_id):
        raise ValueError("verifier metric input, gold, and prediction IDs must match exactly")

    gold_claims = {claim["claim_id"]: (record["id"], claim) for record in gold_records for claim in record["claims"]}
    predicted_claims = [(record["id"], claim) for record in predictions for claim in record.get("claims", [])]
    predicted_ids = [claim["claim_id"] for _record_id, claim in predicted_claims]
    predicted_by_id = {claim["claim_id"]: (record_id, claim) for record_id, claim in predicted_claims}
    matched_ids = set(gold_claims) & set(predicted_by_id)
    duplicate_count = sum(count - 1 for count in Counter(predicted_ids).values() if count > 1)
    claim_metrics = _classification_metrics(
        len(matched_ids),
        len(predicted_ids) - len(matched_ids),
        len(gold_claims) - len(matched_ids),
    )
    tail_ids = {claim_id for claim_id, (_record_id, claim) in gold_claims.items() if claim["start"] > 4000}
    claim_extraction = {
        **claim_metrics,
        "duplicate_rate": _ratio(duplicate_count, len(predicted_ids)),
        "tail_recall": _ratio(len(tail_ids & matched_ids), len(tail_ids)),
    }

    expected_sources = 0
    resolved_sources = 0
    for record_id, input_record in input_by_id.items():
        expected = set(input_record["report_meta"]["source_ids"])
        resolved = set(prediction_by_id[record_id].get("resolved_source_ids", []))
        expected_sources += len(expected)
        resolved_sources += len(expected & resolved)

    per_verdict = {}
    for verdict in VERDICTS:
        true_positive = false_positive = false_negative = 0
        for claim_id, (_record_id, expected) in gold_claims.items():
            predicted = predicted_by_id.get(claim_id, (None, {}))[1].get("verdict")
            if expected["verdict"] == verdict and predicted == verdict:
                true_positive += 1
            elif expected["verdict"] == verdict:
                false_negative += 1
            elif predicted == verdict:
                false_positive += 1
        false_positive += sum(
            claim.get("verdict") == verdict and claim["claim_id"] not in gold_claims
            for _record_id, claim in predicted_claims
        )
        per_verdict[verdict] = _classification_metrics(true_positive, false_positive, false_negative)

    def binary_verdict_metrics(positive_verdicts: set[str]) -> dict[str, float]:
        true_positive = false_positive = false_negative = 0
        for claim_id, (_record_id, expected) in gold_claims.items():
            expected_positive = expected["verdict"] in positive_verdicts
            predicted = predicted_by_id.get(claim_id, (None, {}))[1]
            predicted_positive = predicted.get("verdict") in positive_verdicts
            if expected_positive and predicted_positive:
                true_positive += 1
            elif expected_positive:
                false_negative += 1
            elif predicted_positive:
                false_positive += 1
        false_positive += sum(
            claim.get("verdict") in positive_verdicts and claim["claim_id"] not in gold_claims
            for _record_id, claim in predicted_claims
        )
        return _classification_metrics(true_positive, false_positive, false_negative)

    consistency_true_positive = consistency_false_positive = consistency_false_negative = 0
    ranking_labels = []
    ranking_risks = []
    expected_suggestions = set()
    predicted_suggestions = set()
    for record_id, expected in gold_by_id.items():
        predicted = prediction_by_id[record_id]
        expected_contradiction = bool(expected["internal_contradiction"])
        predicted_contradiction = predicted.get("internal_contradiction")
        if predicted_contradiction is not None:
            if expected_contradiction and predicted_contradiction:
                consistency_true_positive += 1
            elif expected_contradiction:
                consistency_false_negative += 1
            elif predicted_contradiction:
                consistency_false_positive += 1
        if predicted.get("overall_score") is not None:
            ranking_labels.append(bool(expected["flagged"]))
            ranking_risks.append(100.0 - float(predicted["overall_score"]))
        expected_suggestions.update(claim["claim_id"] for claim in expected["claims"] if claim["needs_correction"])
        predicted_suggestions.update(
            suggestion["claim_id"] for suggestion in predicted.get("suggestions", []) if "claim_id" in suggestion
        )

    suggestion_true_positive = len(expected_suggestions & predicted_suggestions)
    return {
        "claim_extraction": claim_extraction,
        "source_resolution": {
            "expected_sources": expected_sources,
            "resolved_sources": resolved_sources,
            "recall": _ratio(resolved_sources, expected_sources),
        },
        "verdicts": {
            "per_class": per_verdict,
            "macro_f1": sum(values["f1"] for values in per_verdict.values()) / len(VERDICTS),
            "hallucination": binary_verdict_metrics({"hallucination"}),
            "flagged": binary_verdict_metrics(FLAGGED_VERDICTS),
        },
        "consistency": _classification_metrics(
            consistency_true_positive,
            consistency_false_positive,
            consistency_false_negative,
        ),
        "ranking": {
            "records": len(ranking_labels),
            "auroc": _auroc(ranking_labels, ranking_risks),
            "average_precision": _average_precision(ranking_labels, ranking_risks),
        },
        "suggestions": {
            **_classification_metrics(
                suggestion_true_positive,
                len(predicted_suggestions - expected_suggestions),
                len(expected_suggestions - predicted_suggestions),
            ),
            "coverage": _ratio(suggestion_true_positive, len(expected_suggestions)),
            "unsupported_rate": _ratio(len(predicted_suggestions - expected_suggestions), len(predicted_suggestions)),
        },
    }
