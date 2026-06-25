from __future__ import annotations

import json
from dataclasses import asdict

from fastapi import APIRouter, BackgroundTasks, Query
from pydantic import BaseModel
from loguru import logger

from needradar.core.database import async_session_factory
from needradar.models.verification import (
    VerificationResult,
    VerificationStatus,
)
from needradar.services.content_verifier import get_verifier
from needradar.services.vault_store import vault

router = APIRouter(prefix="/verification", tags=["verification"])


# ── Schemas ──

class ClaimDetail(BaseModel):
    text: str
    section: str = ""
    verdict: str = "unverifiable"
    confidence: float = 0.0
    evidence: str = ""
    risk_flags: list[str] = []


class SuggestionDetail(BaseModel):
    type: str
    claim: str
    verdict: str
    reason: str
    action: str


class VerificationResponse(BaseModel):
    id: int
    report_title: str
    status: str
    overall_score: float | None = None
    fact_check_score: float | None = None
    consistency_score: float | None = None
    source_reliability_score: float | None = None
    total_claims: int = 0
    hallucination_count: int = 0
    flagged_count: int = 0
    claims: list[ClaimDetail] = []
    suggestions: list[SuggestionDetail] = []
    reviewer_note: str | None = None
    verdict_override: str | None = None
    reviewed_at: str | None = None
    created_at: str = ""
    updated_at: str | None = None


class VerificationListResponse(BaseModel):
    items: list[VerificationResponse]
    total: int


class VerifyRequest(BaseModel):
    report_title: str


class FeedbackRequest(BaseModel):
    verdict_override: str | None = None   # manual override
    reviewer_note: str = ""


# ── Endpoints ──

@router.get("/reports")
async def list_verifiable_reports():
    """List all reports available for verification."""
    reports = vault.list_files("初稿")
    return {
        "items": [
            {
                "title": meta.get("标题", path.stem),
                "keyword": meta.get("关键词", [""])[0] if isinstance(meta.get("关键词"), list) and meta.get("关键词") else "",
                "created_at": str(meta.get("创建时间", "")),
            }
            for path, meta, _body in reports
        ],
        "total": len(reports),
    }


@router.post("/verify", response_model=VerificationResponse)
async def trigger_verification(req: VerifyRequest, bg: BackgroundTasks):
    """Trigger verification for a report. Runs in background, returns pending result."""
    async with async_session_factory() as session:
        result = VerificationResult(
            report_title=req.report_title,
            status=VerificationStatus.PENDING,
        )
        session.add(result)
        await session.commit()
        await session.refresh(result)
        result_id = result.id

    bg.add_task(_run_verification, result_id, req.report_title)
    return _to_response(result)


@router.get("/results", response_model=VerificationListResponse)
async def list_results(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List all verification results."""
    async with async_session_factory() as session:
        from sqlalchemy import select, func as sa_func
        count_q = select(sa_func.count()).select_from(VerificationResult)
        total = (await session.execute(count_q)).scalar() or 0
        q = (
            select(VerificationResult)
            .order_by(VerificationResult.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await session.execute(q)).scalars().all()
        return VerificationListResponse(
            items=[_to_response(r) for r in rows],
            total=total,
        )


@router.get("/results/{result_id}", response_model=VerificationResponse)
async def get_result(result_id: int):
    """Get detailed verification result."""
    async with async_session_factory() as session:
        result = await session.get(VerificationResult, result_id)
        if not result:
            from fastapi import HTTPException
            raise HTTPException(404, "Verification result not found")
        return _to_response(result)


@router.post("/results/{result_id}/feedback", response_model=VerificationResponse)
async def submit_feedback(result_id: int, req: FeedbackRequest):
    """Submit human feedback for a verification result."""
    import datetime
    async with async_session_factory() as session:
        result = await session.get(VerificationResult, result_id)
        if not result:
            from fastapi import HTTPException
            raise HTTPException(404, "Verification result not found")
        result.reviewer_note = req.reviewer_note
        if req.verdict_override:
            result.verdict_override = req.verdict_override
        result.reviewed_at = datetime.datetime.now(datetime.timezone.utc)
        await session.commit()
        await session.refresh(result)
        return _to_response(result)


@router.get("/stats")
async def verification_stats():
    """Aggregate verification statistics."""
    async with async_session_factory() as session:
        from sqlalchemy import select, func as sa_func
        total = (await session.execute(
            select(sa_func.count()).select_from(VerificationResult)
        )).scalar() or 0

        avg_score = (await session.execute(
            select(sa_func.avg(VerificationResult.overall_score))
        )).scalar()

        hallu_total = (await session.execute(
            select(sa_func.sum(VerificationResult.hallucination_count))
        )).scalar() or 0

        flagged_total = (await session.execute(
            select(sa_func.sum(VerificationResult.flagged_count))
        )).scalar() or 0

        return {
            "total_verifications": total,
            "average_score": round(float(avg_score), 1) if avg_score else None,
            "total_hallucinations": hallu_total,
            "total_flagged": flagged_total,
        }


@router.get("/results/by-report/{report_title:path}", response_model=VerificationListResponse)
async def get_report_verifications(report_title: str):
    """Get all verification results for a specific report (for trend comparison)."""
    async with async_session_factory() as session:
        from sqlalchemy import select, func as sa_func
        q = (
            select(VerificationResult)
            .where(VerificationResult.report_title == report_title)
            .order_by(VerificationResult.created_at.asc())
        )
        rows = (await session.execute(q)).scalars().all()
        return VerificationListResponse(
            items=[_to_response(r) for r in rows],
            total=len(rows),
        )


# ── Background task ──

async def _run_verification(result_id: int, report_title: str) -> None:
    verifier = get_verifier()
    try:
        async with async_session_factory() as session:
            result = await session.get(VerificationResult, result_id)
            if not result:
                return
            result.status = VerificationStatus.RUNNING
            await session.commit()

        output = await verifier.verify_report(report_title)

        async with async_session_factory() as session:
            result = await session.get(VerificationResult, result_id)
            if not result:
                return
            result.status = VerificationStatus.COMPLETED
            result.overall_score = output.overall_score
            result.fact_check_score = output.fact_check_score
            result.consistency_score = output.consistency_score
            result.source_reliability_score = output.source_reliability_score
            result.total_claims = len(output.claims)
            result.hallucination_count = output.hallucination_count
            result.flagged_count = output.flagged_count
            result.claims_json = json.dumps(
                [asdict(c) for c in output.claims], ensure_ascii=False
            )
            result.suggestions_json = json.dumps(
                output.suggestions, ensure_ascii=False
            )
            await session.commit()

    except Exception as e:
        logger.error("verification_failed", id=result_id, error=str(e))
        async with async_session_factory() as session:
            result = await session.get(VerificationResult, result_id)
            if result:
                result.status = VerificationStatus.FAILED
                await session.commit()


# ── Helpers ──

def _to_response(r: VerificationResult) -> VerificationResponse:
    claims = []
    if r.claims_json:
        try:
            raw = json.loads(r.claims_json)
            claims = [ClaimDetail(**c) for c in raw]
        except (json.JSONDecodeError, TypeError):
            pass

    suggestions = []
    if r.suggestions_json:
        try:
            raw = json.loads(r.suggestions_json)
            suggestions = [SuggestionDetail(**s) for s in raw]
        except (json.JSONDecodeError, TypeError):
            pass

    return VerificationResponse(
        id=r.id,
        report_title=r.report_title,
        status=r.status,
        overall_score=r.overall_score,
        fact_check_score=r.fact_check_score,
        consistency_score=r.consistency_score,
        source_reliability_score=r.source_reliability_score,
        total_claims=r.total_claims,
        hallucination_count=r.hallucination_count,
        flagged_count=r.flagged_count,
        claims=claims,
        suggestions=suggestions,
        reviewer_note=r.reviewer_note,
        verdict_override=r.verdict_override,
        reviewed_at=str(r.reviewed_at) if r.reviewed_at else None,
        created_at=str(r.created_at) if r.created_at else "",
        updated_at=str(r.updated_at) if r.updated_at else None,
    )
