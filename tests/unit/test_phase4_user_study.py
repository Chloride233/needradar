import csv

import pytest

from needradar.services.phase4_user_study import (
    CSV_FIELDS,
    StudySession,
    load_sessions,
    summarize_sessions,
    write_summary,
)


def _row(**overrides):
    row = {
        "session_id": "session-01",
        "consent_confirmed": "yes",
        "started_at": "2026-07-14T09:00:00+00:00",
        "completed_at": "2026-07-14T09:05:00+00:00",
        "keyword": "developer tools",
        "outcome": "completed",
        "insights_considered": "4",
        "insights_adopted": "2",
        "manual_edits": "1",
        "failure_stage": "none",
        "failure_note": "",
    }
    return row | overrides


def test_session_rejects_missing_consent():
    with pytest.raises(ValueError, match="consent_confirmed"):
        StudySession.from_row(_row(consent_confirmed="no"))


def test_session_rejects_adoption_above_considered():
    with pytest.raises(ValueError, match="must not exceed"):
        StudySession.from_row(_row(insights_considered="1", insights_adopted="2"))


def test_failed_session_requires_failure_stage():
    with pytest.raises(ValueError, match="requires a failure_stage"):
        StudySession.from_row(_row(outcome="failed"))


def test_summary_reports_duration_edits_adoption_and_failure_points():
    sessions = [
        StudySession.from_row(_row()),
        StudySession.from_row(
            _row(
                session_id="session-02",
                completed_at="2026-07-14T09:15:00+00:00",
                outcome="failed",
                insights_considered="0",
                insights_adopted="0",
                manual_edits="0",
                failure_stage="report",
                failure_note="generation error",
            )
        ),
    ]

    assert summarize_sessions(sessions) == {
        "sessions": 2,
        "completed_sessions": 1,
        "completion_rate": 0.5,
        "median_duration_seconds": 600,
        "manual_edits": 1,
        "sessions_with_manual_edits": 1,
        "manual_edit_session_rate": 0.5,
        "insights_considered": 4,
        "insights_adopted": 2,
        "insight_adoption_rate": 0.5,
        "failure_points": {"report": 1},
    }


def test_load_and_write_summary(tmp_path):
    input_path = tmp_path / "sessions.csv"
    with input_path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerow(_row())

    output_path = tmp_path / "summary.json"
    summary = write_summary(load_sessions(input_path), output_path)

    assert summary["sessions"] == 1
    assert '"insights_adopted": 2' in output_path.read_text(encoding="utf-8")


def test_load_rejects_unexpected_columns(tmp_path):
    input_path = tmp_path / "sessions.csv"
    input_path.write_text("session_id,email\nsession-01,test@example.com\n", encoding="utf-8")

    with pytest.raises(ValueError, match="exactly match"):
        load_sessions(input_path)
