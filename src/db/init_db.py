"""One-shot DB initializer. Idempotent (schema uses IF NOT EXISTS)."""
import asyncio
from pathlib import Path

import aiosqlite

from src.config import get_settings
from src.logging_setup import get_logger

SCHEMA_PATH = Path(__file__).parent / "schema.sql"

logger = get_logger(__name__)


async def init_db() -> None:
    settings = get_settings()
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(settings.db_path) as db:
        await db.executescript(schema_sql)
        await db.commit()
    logger.info(
        "db_initialized",
        extra={"extra_fields": {"event": "db_initialized", "db_path": str(settings.db_path)}},
    )


def main() -> None:
    asyncio.run(init_db())


if __name__ == "__main__":
    main()
