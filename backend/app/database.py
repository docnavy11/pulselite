import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_reset_on_return="rollback",
)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            try:
                await session.rollback()
            except Exception:
                # Rollback failed — asyncpg connection is stuck (e.g. an async
                # operation was interrupted mid-await by a client disconnect).
                # Dispose the pool so the bad connection is dropped rather than
                # recycled to the next request.
                logger.warning(
                    "Session rollback failed; disposing connection pool to evict bad connection"
                )
                engine.sync_engine.dispose()
            raise
