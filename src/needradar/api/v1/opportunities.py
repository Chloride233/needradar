"""Opportunity scoring API — POST /score, GET /, GET /{id}."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from needradar.core.database import get_db
from needradar.schemas.schemas import (
    OpportunityListResponse,
    OpportunityResponse,
    ScoreDimensions,
    ScoreRequest,
    TractionSignal,
)
from needradar.services.opportunity_scorer import OpportunityScorer

router = APIRouter(prefix="/opportunities", tags=["opportunities"])


def _opp_to_response(opp) -> OpportunityResponse:
    try:
        scores_dict = json.loads(opp.scores_json)
        traction_list = json.loads(opp.traction_json)
        req_ids = json.loads(opp.source_req_ids_json)
    except json.JSONDecodeError:
        scores_dict, traction_list, req_ids = {}, [], []
    return OpportunityResponse(
        id=opp.id, keyword=opp.keyword, title=opp.title, description=opp.description,
        scores=ScoreDimensions(**scores_dict) if scores_dict else ScoreDimensions(),
        traction=[TractionSignal(**t) for t in traction_list],
        source_req_ids=req_ids, status=opp.status,
        created_at=str(opp.created_at), updated_at=str(opp.updated_at),
    )


@router.post("/score", response_model=dict)
async def score_opportunities(body: ScoreRequest, db: AsyncSession = Depends(get_db)):
    """Score requirement clusters for a keyword."""
    scorer = OpportunityScorer(db)
    try:
        opportunities = await scorer.score_keyword(body.keyword)
        return {
            "keyword": body.keyword,
            "opportunities_count": len(opportunities),
            "message": f"Generated {len(opportunities)} opportunities for '{body.keyword}'",
        }
    except Exception as e:
        logger.error("scoring_failed", keyword=body.keyword, error=str(e))
        raise HTTPException(status_code=500, detail="Scoring failed — check server logs")


@router.get("", response_model=OpportunityListResponse)
async def list_opportunities(
    keyword: str = Query(""),
    min_score: float = Query(0, ge=0, le=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List scored project opportunities with optional filtering."""
    scorer = OpportunityScorer(db)
    rows, total = await scorer.list_opportunities(
        keyword=keyword, min_score=min_score, page=page, page_size=page_size,
    )
    items = [_opp_to_response(r) for r in rows]
    return OpportunityListResponse(items=items, total=total)


@router.get("/{opportunity_id}", response_model=OpportunityResponse)
async def get_opportunity(opportunity_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single opportunity by ID."""
    scorer = OpportunityScorer(db)
    opp = await scorer.get_opportunity(opportunity_id)
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return _opp_to_response(opp)
