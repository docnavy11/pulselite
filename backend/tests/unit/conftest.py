"""Unit test conftest - shared fixtures for unit tests."""
import pytest_asyncio
from sqlalchemy import text


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _widen_rating_column(engine):
    """Widen message_feedback.rating from varchar(10) to varchar(20).

    The migration created it as String(10), but the application stores
    'thumbs_down' (11 chars). This fixture ensures tests can insert
    realistic rating values.
    """
    async with engine.begin() as conn:
        await conn.execute(
            text("ALTER TABLE message_feedback ALTER COLUMN rating TYPE varchar(20)")
        )
