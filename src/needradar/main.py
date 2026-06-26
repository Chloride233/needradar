from contextlib import asynccontextmanager

from fastapi import FastAPI

from needradar.api.v1.router import router as v1_router
from needradar.core.database import engine
from needradar.core.logger import logger
from needradar.core.security import setup_middlewares


@asynccontextmanager
async def lifespan(app: FastAPI):
    from needradar.models import Base  # imports all models to register with metadata
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from needradar.services.scheduler_service import restore_jobs, start_scheduler, stop_scheduler
    start_scheduler()
    await restore_jobs()

    # Reset stale RUNNING tasks (left from interrupted server shutdown)
    from sqlalchemy import update

    from needradar.models.crawl_task import CrawlTask, TaskStatus
    async with engine.begin() as conn:
        await conn.execute(
            update(CrawlTask)
            .where(CrawlTask.status == TaskStatus.RUNNING)
            .values(status=TaskStatus.FAILED, error_message="Server was interrupted during previous execution")
        )

    # Check API key configuration
    from needradar.core.config import settings
    if not settings.deepseek_api_key and not settings.openai_api_key:
        logger.warning("no_llm_api_key", hint="Set NR_DEEPSEEK_API_KEY or NR_OPENAI_API_KEY in .env")
    elif not settings.deepseek_api_key:
        logger.info("deepseek_not_configured", hint="Using OpenAI as primary LLM")
    if settings.llm_fallback_model and "claude" in settings.llm_fallback_model and not settings.anthropic_api_key:
        logger.warning("fallback_model_unconfigured", model=settings.llm_fallback_model, hint="Set NR_ANTHROPIC_API_KEY for fallback")

    logger.info("needradar_starting")
    yield
    stop_scheduler()
    await engine.dispose()
    logger.info("needradar_stopped")

app = FastAPI(
    title="NeedRadar",
    version="0.1.0",
    description="AI驱动的全网需求挖掘引擎",
    lifespan=lifespan,
)

setup_middlewares(app)
app.include_router(v1_router)
