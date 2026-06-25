# -*- coding: utf-8 -*-
from fastapi import APIRouter
from pydantic import BaseModel, Field

from needradar.services.prompt_optimizer import optimizer

router = APIRouter(prefix="/prompt-optimizer", tags=["prompt-optimizer"])


class StartRequest(BaseModel):
    max_iterations: int = Field(default=10, ge=1, le=50)


class StartFromFeedbackRequest(BaseModel):
    max_iterations: int = Field(default=10, ge=1, le=50)
    min_feedback: int = Field(default=1, ge=1, description="Minimum feedback records required")


class StartResponse(BaseModel):
    started: bool
    message: str


@router.post("/start", response_model=StartResponse)
async def start_optimization(req: StartRequest):
    started = optimizer.start(max_iterations=req.max_iterations)
    if started:
        return StartResponse(started=True, message=f"Prompt optimization started with {req.max_iterations} iterations")
    return StartResponse(started=False, message="Optimization already running")


@router.post("/start-from-feedback", response_model=StartResponse)
async def start_from_feedback(req: StartFromFeedbackRequest):
    """Start optimization using human feedback from quality gates as test cases."""
    started = optimizer.start_from_feedback(
        max_iterations=req.max_iterations,
        min_feedback=req.min_feedback,
    )
    if started:
        return StartResponse(started=True, message=f"Feedback-driven optimization started with {req.max_iterations} iterations")
    return StartResponse(started=False, message="Optimization already running")


@router.post("/stop")
async def stop_optimization():
    optimizer.stop()
    return {"stopped": True}


@router.get("/status")
async def get_status():
    return optimizer.status


@router.get("/results")
async def get_results():
    return optimizer.get_results()
