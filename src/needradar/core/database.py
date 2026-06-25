from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool, QueuePool

from needradar.core.config import settings

# Choose pool class based on dialect
# SQLite: NullPool (no connection pooling, avoids file-locking issues)
# PostgreSQL: QueuePool (standard connection pool for production)
_is_sqlite = settings.database_url.startswith("sqlite")
_pool_class = NullPool if _is_sqlite else QueuePool

engine = create_async_engine(
    str(settings.database_url),
    echo=settings.debug,
    poolclass=_pool_class,
)


# SQLite-specific PRAGMAs (silently ignored on other dialects)
if _is_sqlite:
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
