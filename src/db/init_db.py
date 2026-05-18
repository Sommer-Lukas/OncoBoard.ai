"""One-shot DB initializer. Idempotent (schema uses IF NOT EXISTS)."""
import asyncio
import re
from pathlib import Path

from src.db.connection import connect
from src.logging_setup import get_logger

SCHEMA_PATH = Path(__file__).parent / "schema.sql"

logger = get_logger(__name__)


def _strip_comments(sql: str) -> str:
    """Remove -- line comments so asyncpg never sees a comment-only payload."""
    lines = []
    for line in sql.splitlines():
        pos = line.find("--")
        lines.append(line[:pos] if pos >= 0 else line)
    return "\n".join(lines).strip()


async def init_db() -> None:
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    # Strip comments before splitting so semicolons inside comment text
    # don't produce false statement boundaries.
    clean_sql = _strip_comments(schema_sql)
    statements = [s.strip() for s in clean_sql.split(";") if s.strip()]
    async with connect() as conn:
        async with conn.transaction():
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
