from contextlib import asynccontextmanager
from typing import AsyncIterator

import asyncpg

from src.config import get_settings


@asynccontextmanager
async def connect() -> AsyncIterator[asyncpg.Connection]:
    """Open an asyncpg connection to Neon Postgres."""
    conn: asyncpg.Connection = await asyncpg.connect(dsn=get_settings().postgres_url)
    try:
        yield conn
    finally:
        await conn.close()


async def get_db() -> AsyncIterator[asyncpg.Connection]:
    """FastAPI dependency. Yields a connection for the request lifecycle."""
    async with connect() as conn:
        yield conn
