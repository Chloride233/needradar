"""Privacy-minimal user-study ledger and deterministic aggregate reporting."""

from __future__ import annotations

import csv
import json
import statistics
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

CSV_FIELDS = (
    "session_id",
    "consent_confirmed",
    "started_at",
    "completed_at",
    "keyword",
    "outcome",
    "insights_considered",
    "insights_adopted",
    "manual_edits",
    "failure_stage",
    "failure_note",
)
OUTCOMES = {"completed", "abandoned", "failed"}
FAILURE_STAGES = {"none", "crawl", "extraction", "report", "verification", "review", "other"}


def _parse_datetime(value: str, field: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field} must be an ISO-8601 timestamp") from error


def _parse_non_negative_int(value: str, field: str) -> int:
    try:
        result = int(value)
    except ValueError as error:
        raise ValueError(f"{field} must be an integer") from error
    if result < 0:
        raise ValueError(f"{field} must not be negative")
    return result


@dataclass(frozen=True)
class StudySession:
    session_id: str
    started_at: datetime
    completed_at: datetime
    keyword: str
    outcome: str
    insights_considered: int
    insights_adopted: int
    manual_edits: int
    failure_stage: str
    failure_note: str

    @property
    def duration_seconds(self) -> int:
        return int((self.completed_at - self.started_at).total_seconds())

    @classmethod
    def from_row(cls, row: dict[str, str]) -> "StudySession":
        missing = [field for field in CSV_FIELDS if field not in row]
        if missing:
            raise ValueError(f"missing columns: {', '.join(missing)}")
        if row["consent_confirmed"].strip().lower() != "yes":
            raise ValueError("consent_confirmed must be yes")
        if not row["session_id"].strip():
            raise ValueError("session_id is required")
        if not row["keyword"].strip():
            raise ValueError("keyword is required")
        if row["outcome"] not in OUTCOMES:
            raise ValueError(f"outcome must be one of: {', '.join(sorted(OUTCOMES))}")
        if row["failure_stage"] not in FAILURE_STAGES:
            raise ValueError(f"failure_stage must be one of: {', '.join(sorted(FAILURE_STAGES))}")
        if row["outcome"] == "failed" and row["failure_stage"] == "none":
            raise ValueError("failed outcome requires a failure_stage")

        started_at = _parse_datetime(row["started_at"], "started_at")
        completed_at = _parse_datetime(row["completed_at"], "completed_at")
        if completed_at < started_at:
            raise ValueError("completed_at must not precede started_at")
        considered = _parse_non_negative_int(row["insights_considered"], "insights_considered")
        adopted = _parse_non_negative_int(row["insights_adopted"], "insights_adopted")
        if adopted > considered:
            raise ValueError("insights_adopted must not exceed insights_considered")

        return cls(
            session_id=row["session_id"].strip(),
            started_at=started_at,
            completed_at=completed_at,
            keyword=row["keyword"].strip(),
            outcome=row["outcome"],
            insights_considered=considered,
            insights_adopted=adopted,
            manual_edits=_parse_non_negative_int(row["manual_edits"], "manual_edits"),
            failure_stage=row["failure_stage"],
            failure_note=row["failure_note"].strip(),
        )


def load_sessions(path: Path) -> list[StudySession]:
    with path.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames != list(CSV_FIELDS):
            raise ValueError("CSV columns must exactly match the study template")
        rows = list(reader)
    sessions = [StudySession.from_row(row) for row in rows]
    ids = [session.session_id for session in sessions]
    if len(ids) != len(set(ids)):
        raise ValueError("session_id values must be unique")
    return sessions


def summarize_sessions(sessions: list[StudySession]) -> dict:
    durations = [session.duration_seconds for session in sessions]
    completed = [session for session in sessions if session.outcome == "completed"]
    failures: dict[str, int] = {}
    for session in sessions:
        if session.failure_stage != "none":
            failures[session.failure_stage] = failures.get(session.failure_stage, 0) + 1
    considered = sum(session.insights_considered for session in sessions)
    adopted = sum(session.insights_adopted for session in sessions)
    edited_sessions = sum(session.manual_edits > 0 for session in sessions)
    return {
        "sessions": len(sessions),
        "completed_sessions": len(completed),
        "completion_rate": round(len(completed) / len(sessions), 4) if sessions else None,
        "median_duration_seconds": int(statistics.median(durations)) if durations else None,
        "manual_edits": sum(session.manual_edits for session in sessions),
        "sessions_with_manual_edits": edited_sessions,
        "manual_edit_session_rate": round(edited_sessions / len(sessions), 4) if sessions else None,
        "insights_considered": considered,
        "insights_adopted": adopted,
        "insight_adoption_rate": round(adopted / considered, 4) if considered else None,
        "failure_points": dict(sorted(failures.items())),
    }


def write_summary(sessions: list[StudySession], output_path: Path) -> dict:
    summary = summarize_sessions(sessions)
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary
