"""Shared pytest fixtures.

Every test gets an isolated temp SQLite DB and a mocked Gemini so the suite
runs in CI with no API key and no quota burn. Fixtures are function-scoped
for full test isolation.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import aiosqlite
import httpx
import pytest
import pytest_asyncio


@pytest.fixture
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the app at a throwaway DB and force mock Gemini.

    Clears the cached Settings and the Gemini client singleton so the new
    env vars actually take effect (both are process-global and memoized).
    """
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("DB_PATH", str(db_file))
    monkeypatch.setenv("GEMINI_MOCK", "1")
    monkeypatch.setenv("GEMINI_API_KEY", "")

    from src.agents.gemini_client import reset_gemini_client
    from src.config import get_settings

    get_settings.cache_clear()
    reset_gemini_client()
    yield db_file
    # Tear down memoized state so the next test starts clean.
    get_settings.cache_clear()
    reset_gemini_client()


@pytest_asyncio.fixture
async def db_path(isolated_env: Path) -> Path:
    """Isolated env + schema initialized. Returns the DB file path."""
    from src.db.init_db import init_db

    await init_db()
    return isolated_env


@pytest_asyncio.fixture
async def db(db_path: Path) -> AsyncIterator[aiosqlite.Connection]:
    """An open connection to the initialized (empty) DB."""
    from src.db.connection import connect

    async with connect() as conn:
        yield conn


@pytest_asyncio.fixture
async def seeded_db(db_path: Path) -> Path:
    """Schema + 4 synthetic cases (SYN-001..004) with genomics blobs."""
    from src.data import seed_synthetic

    n = await seed_synthetic.seed()
    assert n == 4
    return db_path


@pytest.fixture
def mock_gemini():
    """A fresh MockGeminiClient (FIFO queue + .calls recorder)."""
    from src.agents.gemini_client import MockGeminiClient

    return MockGeminiClient()


@pytest_asyncio.fixture
async def client(seeded_db: Path) -> AsyncIterator[httpx.AsyncClient]:
    """httpx client bound to the FastAPI app over ASGI, against the seeded DB."""
    from src.main import create_app

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test"
    ) as c:
        yield c
