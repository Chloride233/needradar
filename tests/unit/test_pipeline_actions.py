"""Tests for pipeline_actions — Burr action functions."""
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from needradar.models.crawl_task import CrawlTask, TaskStatus
from needradar.models.pipeline_phase import PhaseName, PhaseStatus, PipelinePhase
from needradar.models.pipeline_run import PipelineRun
from needradar.models.quality_gate import GateStatus, GateType, QualityGate
from needradar.schemas.schemas import NoiseVerdict


# ── Fixtures ──


@pytest.fixture
async def sample_run(db_session):
    """Create a sample pipeline run in the DB."""
    run = PipelineRun(
        keyword="test-keyword",
        status="running",
        task_ids_json="[]",
        stages_json="[]",
        is_agent_mode=True,
        current_phase="crawling",
        gate_status="none",
    )
    db_session.add(run)
    await db_session.commit()
    return run


@pytest.fixture
async def sample_task(db_session, sample_run):
    """Create a sample crawl task in the DB."""
    task = CrawlTask(keyword="test-keyword", platform="github", status=TaskStatus.PENDING)
    db_session.add(task)
    await db_session.commit()
    sample_run.task_ids_json = json.dumps([task.id])
    await db_session.commit()
    return task


# ── Helper function tests ──


@pytest.mark.asyncio
async def test_record_phase_creates_new(db_session, sample_run):
    """_record_phase creates a new phase record when none exists."""
    from needradar.services.pipeline_actions import _record_phase

    await _record_phase(sample_run.id, PhaseName.CRAWLING, PhaseStatus.RUNNING)

    result = await db_session.execute(
        select(PipelinePhase).where(
            PipelinePhase.pipeline_run_id == sample_run.id,
            PipelinePhase.phase == PhaseName.CRAWLING.value,
        )
    )
    phase = result.scalar_one_or_none()
    assert phase is not None
    assert phase.status == PhaseStatus.RUNNING.value
    assert phase.started_at is not None


@pytest.mark.asyncio
async def test_record_phase_updates_existing(db_session, sample_run):
    """_record_phase updates an existing phase record."""
    from needradar.services.pipeline_actions import _record_phase

    # Create initial
    await _record_phase(sample_run.id, PhaseName.CRAWLING, PhaseStatus.RUNNING)
    # Update
    await _record_phase(sample_run.id, PhaseName.CRAWLING, PhaseStatus.COMPLETED, {"items": 5})

    result = await db_session.execute(
        select(PipelinePhase).where(
            PipelinePhase.pipeline_run_id == sample_run.id,
            PipelinePhase.phase == PhaseName.CRAWLING.value,
        )
    )
    phase = result.scalar_one()
    assert phase.status == PhaseStatus.COMPLETED.value
    assert phase.completed_at is not None
    assert json.loads(phase.result_json) == {"items": 5}


@pytest.mark.asyncio
async def test_create_gate(db_session, sample_run):
    """_create_gate creates a quality gate and pauses the run."""
    from needradar.services.pipeline_actions import _create_gate

    items = [{"title": "item1", "approved": True}, {"title": "item2", "approved": True}]
    await _create_gate(sample_run.id, GateType.MATERIAL, items)

    # Check gate
    result = await db_session.execute(
        select(QualityGate).where(QualityGate.pipeline_run_id == sample_run.id)
    )
    gate = result.scalar_one_or_none()
    assert gate is not None
    assert gate.gate_type == GateType.MATERIAL.value
    assert gate.status == GateStatus.AWAITING_REVIEW.value
    assert gate.items_count == 2

    # Check run is paused
    await db_session.refresh(sample_run)
    assert sample_run.status == "paused"
    assert sample_run.gate_status == "awaiting_review"


@pytest.mark.asyncio
async def test_update_run(db_session, sample_run):
    """_update_run updates pipeline run fields."""
    from needradar.services.pipeline_actions import _update_run

    await _update_run(sample_run.id, status="paused", current_phase="material_gate")

    await db_session.refresh(sample_run)
    assert sample_run.status == "paused"
    assert sample_run.current_phase == "material_gate"


# ── Action function tests ──


@pytest.mark.asyncio
async def test_archive_action(db_session, sample_run, sample_task):
    """archive_action marks non-failed tasks as completed."""
    from needradar.services.pipeline_actions import archive_action

    sample_task.status = TaskStatus.RUNNING
    await db_session.commit()

    result = await archive_action(sample_run.id)

    assert result == {"status": "done"}
    await db_session.refresh(sample_task)
    assert sample_task.status == TaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_archive_action_skips_failed_tasks(db_session, sample_run, sample_task):
    """archive_action does not change status of failed tasks."""
    from needradar.services.pipeline_actions import archive_action

    sample_task.status = TaskStatus.FAILED
    await db_session.commit()

    result = await archive_action(sample_run.id)

    assert result == {"status": "done"}
    await db_session.refresh(sample_task)
    assert sample_task.status == TaskStatus.FAILED


@pytest.mark.asyncio
async def test_complete_action(db_session, sample_run):
    """complete_action marks pipeline as completed."""
    from needradar.services.pipeline_actions import complete_action

    result = await complete_action(sample_run.id)

    assert result == {"status": "completed"}
    await db_session.refresh(sample_run)
    assert sample_run.status == "completed"
    assert sample_run.current_phase == "completed"


@pytest.mark.asyncio
async def test_distill_action(db_session, sample_run):
    """distill_action runs knowledge distillation."""
    from needradar.services.pipeline_actions import distill_action

    with patch("needradar.services.pipeline_actions.KnowledgeDistiller", create=True) as MockDistiller:
        mock_distiller = AsyncMock()
        MockDistiller.return_value = mock_distiller

        with patch("needradar.services.pipeline_actions.async_session_factory") as mock_factory:
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=db_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await distill_action(sample_run.id)

    assert result == {"status": "done"}


@pytest.mark.asyncio
async def test_crawl_action_run_not_found(db_session):
    """crawl_action returns error when run doesn't exist."""
    from needradar.services.pipeline_actions import crawl_action

    result = await crawl_action(99999, "test", ["github"])
    assert "error" in result


@pytest.mark.asyncio
async def test_extract_action_no_material_gate(db_session, sample_run):
    """extract_action handles missing material gate gracefully."""
    from needradar.services.pipeline_actions import extract_action

    result = await extract_action(sample_run.id, "test-keyword")
    assert result["extracted"] == 0


@pytest.mark.asyncio
async def test_report_action_handles_timeout(db_session, sample_run):
    """report_action handles report generation timeout."""
    from needradar.services.pipeline_actions import report_action

    with patch("needradar.services.report_service.get_report_service") as mock_get_rs:
        mock_rs = AsyncMock()
        mock_rs.generate_report.side_effect = TimeoutError("Report generation timed out")
        mock_get_rs.return_value = mock_rs

        result = await report_action(sample_run.id, "test-keyword")

    assert result["report_path"] is None
