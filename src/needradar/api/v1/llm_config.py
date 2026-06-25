from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from needradar.llm.model_presets import PRESETS
from needradar.llm.provider import llm

router = APIRouter(prefix="/llm", tags=["llm-config"])


class PresetUpdateRequest(BaseModel):
    api_key: str | None = None
    temperature: float | None = Field(None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(None, ge=1, le=32768)


class TestResponse(BaseModel):
    success: bool
    response: str = ""
    error: str = ""
    latency_ms: int | None = None


@router.get("/presets")
async def list_presets():
    return {
        "presets": [
            {**p.to_dict(), "health": llm.get_health(p.id)}
            for p in PRESETS.values()
        ],
        "active": llm.active_preset_id,
    }


@router.put("/presets/{preset_id}")
async def update_preset(preset_id: str, req: PresetUpdateRequest):
    if preset_id not in PRESETS:
        raise HTTPException(404, f"Unknown preset: {preset_id}")
    try:
        preset = llm.update_preset(
            preset_id,
            api_key=req.api_key,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
        )
        return {**preset.to_dict(), "health": llm.get_health(preset_id)}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/test/{preset_id}", response_model=TestResponse)
async def test_model(preset_id: str):
    if preset_id not in PRESETS:
        raise HTTPException(404, f"Unknown preset: {preset_id}")
    result = await llm.test_connection(preset_id)
    return TestResponse(
        success=result.get("success", False),
        response=result.get("response", ""),
        error=result.get("error", ""),
        latency_ms=result.get("latency_ms"),
    )
