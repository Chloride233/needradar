"""API for project proposal generation - produces executable project plans."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from needradar.core.database import get_db
from needradar.schemas.schemas import ProposalGenerateRequest, ProposalListResponse, ProposalResponse
from needradar.services.proposal_generator import ProposalGenerator

router = APIRouter(prefix="/proposals", tags=["proposals"])


def _to_response(p) -> ProposalResponse:
    try:
        mvp = json.loads(p.mvp_scope_json)
        stack = json.loads(p.suggested_stack_json)
        effort = json.loads(p.effort_breakdown_json)
        traction = json.loads(p.traction_signals_json)
        risks = json.loads(p.risks_json)
    except json.JSONDecodeError:
        mvp, stack, effort, traction, risks = [], {}, {}, [], []

    return ProposalResponse(
        id=p.id, opportunity_id=p.opportunity_id, keyword=p.keyword,
        title=p.title, problem_statement=p.problem_statement,
        target_user=p.target_user, mvp_scope=mvp,
        suggested_stack=stack, effort_estimate_hours=p.effort_estimate_hours,
        effort_breakdown=effort, traction_signals=traction,
        claude_prompt=p.claude_prompt, risks=risks, status=p.status,
        vault_path=p.vault_path,
        created_at=str(p.created_at), updated_at=str(p.updated_at),
    )


@router.post("/generate", response_model=dict)
async def generate_proposal(body: ProposalGenerateRequest, db: AsyncSession = Depends(get_db)):
    gen = ProposalGenerator(db)
    proposal = await gen.generate(body.opportunity_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return {"id": proposal.id, "title": proposal.title, "message": "Proposal generated"}


@router.get("", response_model=ProposalListResponse)
async def list_proposals(
    keyword: str = Query(""),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    gen = ProposalGenerator(db)
    rows, total = await gen.list_proposals(keyword=keyword, page=page, page_size=page_size)
    return ProposalListResponse(items=[_to_response(r) for r in rows], total=total)


@router.get("/{proposal_id}", response_model=ProposalResponse)
async def get_proposal(proposal_id: int, db: AsyncSession = Depends(get_db)):
    gen = ProposalGenerator(db)
    p = await gen.get_proposal(proposal_id)
    if not p:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return _to_response(p)


@router.get("/{proposal_id}/prompt", response_class=PlainTextResponse)
async def get_proposal_prompt(proposal_id: int, db: AsyncSession = Depends(get_db)):
    gen = ProposalGenerator(db)
    p = await gen.get_proposal(proposal_id)
    if not p:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return p.claude_prompt or "# No prompt generated"
