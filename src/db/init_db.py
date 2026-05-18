"""One-shot DB initializer. Idempotent (schema uses IF NOT EXISTS)."""
import asyncio
from pathlib import Path

from src.db.connection import connect
from src.logging_setup import get_logger

SCHEMA_PATH = Path(__file__).parent / "schema.sql"

logger = get_logger(__name__)


async def init_db() -> None:
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    # Split on semicolons so each statement is executed individually.
    # Filter out blank/comment-only chunks produced by the split.
    statements = [s.strip() for s in schema_sql.split(";") if s.strip()]
    async with connect() as conn:
        for stmt in statements:
            await conn.execute(stmt)
    logger.info(
        "db_initialized",
        extra={"extra_fields": {"event": "db_initialized"}},
    )


def main() -> None:
    asyncio.run(init_db())


if __name__ == "__main__":
    main()
