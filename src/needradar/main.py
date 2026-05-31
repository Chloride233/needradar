from contextlib import asynccontextmanager

from fastapi import FastAPI

from needradar.api.v1.router import router as v1_router
from needradar.core.database import engine
from needradar.core.logger import logger
from needradar.core.security import setup_middlewares


@asynccontextmanager
async def lifespan(app: FastAPI):
    from needradar.models.base import Base
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

    logger.info("needradar_starting")
    yield
    stop_scheduler()
    await engine.dispose()
    logger.info("needradar_stopped")


async def _warm_chroma():
    try:
        import needradar.vector.chroma_store as cs
        cs._get_ef()  # trigger model load
        logger.info("chromadb_model_warmed")
    except Exception as e:
        logger.warning("chromadb_warm_failed", error=str(e))


app = FastAPI(
    title="NeedRadar",
    version="0.1.0",
    description="AI驱动的全网需求挖掘引擎",
    lifespan=lifespan,
)

setup_middlewares(app)
app.include_router(v1_router)
