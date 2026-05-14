from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import aiosqlite

from src.config import get_settings


def _db_path() -> Path:
    return get_settings().db_path


@asynccontextmanager
async def connect() -> AsyncIterator[aiosqlite.Connection]:
    """Open an aiosqlite connection with FK enforcement + row factory."""
    async with aiosqlite.connect(_db_path()) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys = ON")
        yield db


async def get_db() -> AsyncIterator[aiosqlite.Connection]:
    """FastAPI dependency. Yields a connection for the request lifecycle."""
    async with connect() as db:
        yield db
