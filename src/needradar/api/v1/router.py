from fastapi import APIRouter

from needradar.api.v1.dashboard import router as dashboard_router
from needradar.api.v1.entities import router as entities_router
from needradar.api.v1.links import router as links_router
from needradar.api.v1.llm_config import router as llm_config_router
from needradar.api.v1.reports import router as reports_router
from needradar.api.v1.requirements import router as requirements_router
from needradar.api.v1.scheduler import router as scheduler_router
from needradar.api.v1.tasks import router as tasks_router
from needradar.api.v1.trending import router as trending_router
from needradar.api.v1.usage import router as usage_router
from needradar.api.v1.prompt_optimizer import router as prompt_optimizer_router
from needradar.api.v1.opportunities import router as opportunities_router
from needradar.api.v1.pipeline import router as pipeline_router
from needradar.api.v1.proposals import router as proposals_router
from needradar.api.v1.verification import router as verification_router
from needradar.api.v1.gates import router as gates_router
from needradar.api.v1.feedback import router as feedback_router

router = APIRouter(prefix="/api/v1")


@router.get("/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}


@router.get("/health/detail")
async def health_detail():
    import asyncio

    result = {"status": "ok", "version": "0.1.0", "components": {}}

    # ChromaDB status (run in thread to avoid blocking)
    try:
        from needradar.vector.chroma_store import _get_client
        client = await asyncio.to_thread(_get_client)
        client.heartbeat()
        coll = client.get_or_create_collection("requirements")
        result["components"]["chromadb"] = {"status": "ok", "vectors": coll.count()}
    except Exception as e:
        result["components"]["chromadb"] = {"status": "error", "error": str(e)}
        result["status"] = "degraded"

    # Vault status
    try:
        from needradar.services.vault_store import vault
        stages = {"素材", "需求", "大纲", "初稿", "终稿", "已归档"}
        counts = {s: len(vault.list_files(s)) for s in stages}
        result["components"]["vault"] = {"status": "ok", "files": counts}
    except Exception as e:
        result["components"]["vault"] = {"status": "error", "error": str(e)}
        result["status"] = "degraded"

    return result


router.include_router(tasks_router)
router.include_router(requirements_router)
router.include_router(links_router)
router.include_router(entities_router)
router.include_router(reports_router)
router.include_router(dashboard_router)
router.include_router(llm_config_router)
router.include_router(trending_router)
router.include_router(opportunities_router)
router.include_router(proposals_router)
router.include_router(pipeline_router)
router.include_router(usage_router)
router.include_router(verification_router)
router.include_router(scheduler_router)
router.include_router(prompt_optimizer_router)
router.include_router(gates_router)
router.include_router(feedback_router)
