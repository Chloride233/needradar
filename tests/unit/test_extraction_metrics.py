import json

import pytest

from needradar.services.extraction_metrics import _char_ngram_dice, score_extractions


def _write(path, records):
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def _record(record_id, **changes):
    record = {
        "id": record_id,
        "requirement_present": "yes",
        "title": "CSV export",
        "description": "Export records to CSV",
        "pain_point": "Manual copying",
        "use_case": "Weekly reporting",
        "sentiment": "moderate",
        "emotion": "neutral",
        "evidence_clarity": "clear",
        "confidence": 0.9,
        "human_requirement_reviewed": False,
    }
    record.update(changes)
    return record


def _discussion(record_id, platform="github"):
    return {"id": record_id, "platform": platform}


def test_char_ngram_dice_handles_empty_and_multilingual_text():
    assert _char_ngram_dice("", "") == 1.0
    assert _char_ngram_dice("", "CSV") == 0.0
    assert _char_ngram_dice("导出 CSV 文件", "CSV 文件导出") > 0.5


def test_score_extractions_reports_accuracy_rejection_duplicates_and_edits(tmp_path):
    gold = tmp_path / "gold.jsonl"
    predictions = tmp_path / "predictions.jsonl"
    discussions = tmp_path / "discussions.jsonl"
    _write(
        gold,
        [
            _record("one", human_requirement_reviewed=True),
            _record(
                "two",
                requirement_present="no",
                title="",
                description="",
                pain_point="",
                use_case="",
                sentiment="mild",
                evidence_clarity="clear",
                human_requirement_reviewed=True,
            ),
            _record("three"),
        ],
    )
    _write(
        predictions,
        [
            _record("one"),
            _record("two", title="CSV export"),
            _record("three", title="CSV export", emotion="negative", confidence=0.6),
        ],
    )
    _write(
        discussions,
        [
            _discussion("one"),
            _discussion("two"),
            _discussion("three", platform="stackoverflow"),
        ],
    )

    report = score_extractions(gold, predictions, discussions)

    assert report["requirement_presence"] == {"correct": 2, "accuracy": pytest.approx(2 / 3)}
    assert report["rejection"]["rate"] == 0.0
    assert report["rejection"]["recall"] == 0.0
    assert report["extraction_failures"] == {"count": 0, "rate": 0.0}
    assert report["duplicates"] == {"count": 2, "rate_among_accepted": pytest.approx(2 / 3)}
    assert report["proxy_record_edit_rate"]["count"] == 2
    assert report["human_audited_requirement_edit_rate"] == {"count": 1, "total": 2, "rate": 0.5}
    assert report["confidence_calibration"]["count"] == 2
    github_failures = report["failure_analysis"]["by_platform"]["github"]
    assert github_failures["requirement_presence_confusion"] == {
        "true_positive": 1,
        "true_negative": 0,
        "false_positive": 1,
        "false_negative": 0,
        "error": 0,
    }
    assert github_failures["dominant_failure_modes"][0]["name"] == "false_positive_requirement"
    assert report["failure_analysis"]["by_content_type"]["question"]["record_count"] == 1


def test_score_rejects_mismatched_ids(tmp_path):
    gold = tmp_path / "gold.jsonl"
    predictions = tmp_path / "predictions.jsonl"
    discussions = tmp_path / "discussions.jsonl"
    _write(gold, [_record("one")])
    _write(predictions, [_record("two")])
    _write(discussions, [_discussion("one")])

    with pytest.raises(ValueError, match="IDs must match"):
        score_extractions(gold, predictions, discussions)


def test_score_rejects_mismatched_discussion_ids(tmp_path):
    gold = tmp_path / "gold.jsonl"
    predictions = tmp_path / "predictions.jsonl"
    discussions = tmp_path / "discussions.jsonl"
    _write(gold, [_record("one")])
    _write(predictions, [_record("one")])
    _write(discussions, [_discussion("two")])

    with pytest.raises(ValueError, match="discussion IDs must match"):
        score_extractions(gold, predictions, discussions)
