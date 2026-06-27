import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from needradar.core.database import get_db
from needradar.main import app
from needradar.models import Base  # imports all models to register with Base.metadata

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    poolclass=StaticPool,
)
test_session_factory = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

# NOTE: above fixture is deprecated in pytest-asyncio >= 0.24.
# Migrate to loop_scope="session" on fixtures when upgrading.


async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with test_session_factory() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
async def setup_database(tmp_path_factory):
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    app.dependency_overrides[get_db] = _override_get_db

    # Patch async_session_factory so background tasks use the test DB
    import needradar.core.database as db_mod
    original_factory = db_mod.async_session_factory
    db_mod.async_session_factory = test_session_factory

    # Use a temp vault for tests
    tmp_vault = tmp_path_factory.mktemp("vault")
    for sub in ["01-原始素材库/灵感剪报", "01-原始素材库/高价值片段",
                "02-需求池", "03-分析车间/大纲挑选", "03-分析车间/初稿打磨",
                "03-分析车间/终稿确认", "04-报告归档", "07-知识沉淀/平台质量",
                "07-知识沉淀/关键词效果", "07-知识沉淀/噪声模式", "07-知识沉淀/提取规则"]:
        (tmp_vault / sub).mkdir(parents=True, exist_ok=True)

    import needradar.services.vault_store as vs_mod
    original_root = vs_mod.vault._root
    vs_mod.vault._root = tmp_vault
    # Also patch the _dir method base
    original_dirs = {}
    for stage in ["素材", "需求", "大纲", "初稿", "终稿", "已归档"]:
        original_dirs[stage] = None

    yield

    vs_mod.vault._root = original_root
    db_mod.async_session_factory = original_factory
    app.dependency_overrides.pop(get_db, None)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with test_session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
