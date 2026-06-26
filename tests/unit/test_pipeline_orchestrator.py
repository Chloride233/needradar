"""Tests for PipelineOrchestrator — state machine with quality gates."""
import json
from unittest.mock import AsyncMock, patch

import pytest

from needradar.models.crawl_task import CrawlTask, TaskStatus
from needradar.models.feedback import FeedbackRecord
from needradar.models.pipeline_run import PipelineRun
from needradar.models.quality_gate import GateStatus, GateType, QualityGate
from needradar.services.pipeline_orchestrator import PipelineOrchestrator, get_orchestrator


# ── Fixtures ──


@pytest.fixture
async def run(db_session):
    """Create a pipeline run."""
    run = PipelineRun(
        keyword="test", status="running", task_ids_json="[]",
        stages_json="[]", is_agent_mode=True, current_phase="crawling", gate_status="none",
    )
    db_session.add(run)
    await db_session.commit()
    return run


@pytest.fixture
async def gate(db_session, run):
    """Create a quality gate in awaiting_review state."""
    gate = QualityGate(
        pipeline_run_id=run.id, gate_type=GateType.MATERIAL.value,
        status=GateStatus.AWAITING_REVIEW.value, items_json='[{"title":"t","approved":true}]',
        items_count=1,
    )
    db_session.add(gate)
    run.status = "paused"
    run.gate_status = "awaiting_review"
    await db_session.commit()
    return gate


@pytest.fixture
async def task(db_session, run):
    """Create a crawl task."""
    task = CrawlTask(keyword="test", platform="github", status=TaskStatus.PENDING)
    db_session.add(task)
    await db_session.commit()
    run.task_ids_json = json.dumps([task.id])
    await db_session.commit()
    return task


# ── start() tests ──


@pytest.mark.asyncio
async def test_start_creates_run_and_tasks(db_session):
    """start() creates a pipeline run and crawl tasks."""
    orch = PipelineOrchestrator(db_session)

    with patch("needradar.services.pipeline_orchestrator.asyncio.create_task"):
        run = await orch.start("AI tools", ["github", "stackoverflow"])

    assert run.id is not None
    assert run.keyword == "AI tools"
    assert run.status == "running"
    assert run.is_agent_mode is True

    task_ids = json.loads(run.task_ids_json)
    assert len(task_ids) == 2


# ── resume_after_gate() tests ──


@pytest.mark.asyncio
async def test_resume_approve(db_session, gate, run):
    """resume_after_gate with approve sets gate to approved."""
    orch = PipelineOrchestrator(db_session)

    with patch("needradar.services.pipeline_orchestrator.asyncio.create_task"):
        await orch.resume_after_gate(gate.id, "approve", note="Looks good")

    await db_session.refresh(gate)
    assert gate.status == GateStatus.APPROVED.value
    assert gate.human_decision == "approve"
    assert gate.reviewer_note == "Looks good"
    assert gate.reviewed_at is not None


@pytest.mark.asyncio
async def test_resume_reject(db_session, gate, run):
    """resume_after_gate with reject sets run to rejected."""
    orch = PipelineOrchestrator(db_session)

    await orch.resume_after_gate(gate.id, "reject", note="Bad data")

    await db_session.refresh(gate)
    await db_session.refresh(run)
    assert gate.status == GateStatus.REJECTED.value
    assert run.status == "rejected"


@pytest.mark.asyncio
async def test_resume_edit_records_feedback(db_session, gate, run):
    """resume_after_gate with edit records feedback."""
    orch = PipelineOrchestrator(db_session)
    edits = [{"feedback_type": "item_removed", "entity_id": "123", "before": {"x": 1}, "after": None, "reason": "test"}]

    with patch("needradar.services.pipeline_orchestrator.asyncio.create_task"):
        await orch.resume_after_gate(gate.id, "edit", edits=edits, note="Edited")

    await db_session.refresh(gate)
    assert gate.status == GateStatus.APPROVED.value

    # Check feedback was recorded
    from sqlalchemy import select
    result = await db_session.execute(select(FeedbackRecord).where(FeedbackRecord.gate_id == gate.id))
    feedbacks = result.scalars().all()
    assert len(feedbacks) == 1
    assert feedbacks[0].feedback_type == "item_removed"


@pytest.mark.asyncio
async def test_resume_gate_not_found(db_session):
    """resume_after_gate raises ValueError for missing gate."""
    orch = PipelineOrchestrator(db_session)

    with pytest.raises(ValueError, match="Gate 99999 not found"):
        await orch.resume_after_gate(99999, "approve")


@pytest.mark.asyncio
async def test_resume_gate_not_awaiting(db_session, gate, run):
    """resume_after_gate raises ValueError for non-awaiting gate."""
    gate.status = GateStatus.APPROVED.value
    await db_session.commit()

    orch = PipelineOrchestrator(db_session)

    with pytest.raises(ValueError, match="not awaiting review"):
        await orch.resume_after_gate(gate.id, "approve")


@pytest.mark.asyncio
async def test_resume_invalid_decision(db_session, gate, run):
    """resume_after_gate raises ValueError for invalid decision."""
    orch = PipelineOrchestrator(db_session)

    with pytest.raises(ValueError, match="Invalid decision"):
        await orch.resume_after_gate(gate.id, "invalid")


# ── get_gate_items() tests ──


@pytest.mark.asyncio
async def test_get_gate_items(db_session, gate):
    """get_gate_items returns items from gate."""
    orch = PipelineOrchestrator(db_session)
    items = await orch.get_gate_items(gate.id)
    assert len(items) == 1
    assert items[0]["title"] == "t"


@pytest.mark.asyncio
async def test_get_gate_items_empty(db_session, run):
    """get_gate_items returns empty for gate with no items."""
    gate = QualityGate(
        pipeline_run_id=run.id, gate_type=GateType.MATERIAL.value,
        status=GateStatus.AWAITING_REVIEW.value, items_json=None, items_count=0,
    )
    db_session.add(gate)
    await db_session.commit()

    orch = PipelineOrchestrator(db_session)
    items = await orch.get_gate_items(gate.id)
    assert items == []


@pytest.mark.asyncio
async def test_get_gate_items_not_found(db_session):
    """get_gate_items raises ValueError for missing gate."""
    orch = PipelineOrchestrator(db_session)

    with pytest.raises(ValueError, match="Gate 99999 not found"):
        await orch.get_gate_items(99999)


# ── _resume_from_phase() tests ──


@pytest.mark.asyncio
async def test_resume_from_material_gate(db_session, run):
    """_resume_from_phase calls extract_action for material gate."""
    orch = PipelineOrchestrator(db_session)

    with patch("needradar.services.pipeline_actions.extract_action", new_callable=AsyncMock) as mock_extract:
        mock_extract.return_value = {"extracted": 5}
        await orch._resume_from_phase(run.id, GateType.MATERIAL, "test")

    mock_extract.assert_called_once_with(run.id, "test")


@pytest.mark.asyncio
async def test_resume_from_requirement_gate(db_session, run):
    """_resume_from_phase calls report_action for requirement gate."""
    orch = PipelineOrchestrator(db_session)

    with patch("needradar.services.pipeline_actions.report_action", new_callable=AsyncMock) as mock_report:
        mock_report.return_value = {"report_path": "/path"}
        await orch._resume_from_phase(run.id, GateType.REQUIREMENT, "test")

    mock_report.assert_called_once_with(run.id, "test")


@pytest.mark.asyncio
async def test_resume_from_insight_gate(db_session, run):
    """_resume_from_phase calls archive/distill/complete for insight gate."""
    orch = PipelineOrchestrator(db_session)

    with patch("needradar.services.pipeline_actions.archive_action", new_callable=AsyncMock) as mock_archive, \
         patch("needradar.services.pipeline_actions.distill_action", new_callable=AsyncMock) as mock_distill, \
         patch("needradar.services.pipeline_actions.complete_action", new_callable=AsyncMock) as mock_complete:
        await orch._resume_from_phase(run.id, GateType.INSIGHT, "test")

    mock_archive.assert_called_once()
    mock_distill.assert_called_once()
    mock_complete.assert_called_once()


@pytest.mark.asyncio
async def test_resume_handles_action_error(db_session, run):
    """_resume_from_phase handles errors from actions by calling _fail."""
    orch = PipelineOrchestrator(db_session)

    with patch("needradar.services.pipeline_actions.extract_action", new_callable=AsyncMock) as mock_extract, \
         patch.object(orch, "_fail", new_callable=AsyncMock) as mock_fail:
        mock_extract.return_value = {"error": "Extraction failed"}
        await orch._resume_from_phase(run.id, GateType.MATERIAL, "test")

    mock_fail.assert_called_once_with(run.id, "Extraction failed")


# ── _fail() tests ──


@pytest.mark.asyncio
async def test_fail_updates_run(db_session, run):
    """_fail sets run status to failed via its own session."""
    orch = PipelineOrchestrator(db_session)

    with patch("needradar.services.pipeline_orchestrator.async_session_factory") as mock_factory:
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
        await orch._fail(run.id, "Something went wrong")

    await db_session.refresh(run)
    assert run.status == "failed"
    assert run.error_message == "Something went wrong"
    assert run.current_phase == "failed"


@pytest.mark.asyncio
async def test_fail_truncates_error(db_session, run):
    """_fail truncates long error messages."""
    orch = PipelineOrchestrator(db_session)
    long_error = "x" * 3000

    with patch("needradar.services.pipeline_orchestrator.async_session_factory") as mock_factory:
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
        await orch._fail(run.id, long_error)

    await db_session.refresh(run)
    assert len(run.error_message) == 2000


# ── _record_edits() tests ──


@pytest.mark.asyncio
async def test_record_edits(db_session, gate):
    """_record_edits creates FeedbackRecord entries."""
    orch = PipelineOrchestrator(db_session)
    edits = [
        {"feedback_type": "item_removed", "entity_id": "1", "before": {"x": 1}, "reason": "test"},
        {"feedback_type": "item_edited", "entity_id": "2", "before": {"a": 1}, "after": {"a": 2}},
    ]

    await orch._record_edits(gate, edits)

    from sqlalchemy import select
    result = await db_session.execute(select(FeedbackRecord).where(FeedbackRecord.gate_id == gate.id))
    feedbacks = result.scalars().all()
    assert len(feedbacks) == 2


# ── get_orchestrator() tests ──


def test_get_orchestrator():
    """get_orchestrator returns a PipelineOrchestrator instance."""
    orch = get_orchestrator("fake_db")
    assert isinstance(orch, PipelineOrchestrator)
