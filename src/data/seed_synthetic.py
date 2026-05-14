"""Seed the DB with hand-crafted synthetic cases for dev and tests.

Idempotent — re-running upserts the same case_ids without producing duplicates.
Each fixture row carries a `cnv_sample` dict that becomes a case_genomics blob,
so even the synthetic cases exercise the genomics lookup path.

Usage:
    .\\.venv\\Scripts\\python.exe -m src.data.seed_synthetic
"""
import asyncio
import json
from pathlib import Path

from src.data.subtype import classify
from src.db import repository as repo
from src.db.connection import connect
from src.db.init_db import init_db
from src.db.models import Case, CaseGenomics
from src.logging_setup import get_logger

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "synthetic_cases.json"

logger = get_logger(__name__)


async def seed() -> int:
    await init_db()
    raw = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    now = "2026-05-14T00:00:00+00:00"
    inserted = 0

    async with connect() as db:
        for entry in raw:
            cnv_sample = entry.pop("cnv_sample", None)
            subtype = classify(entry.get("er_status"), entry.get("pr_status"), entry.get("her2_status"))
            case = Case(
                **entry,
                molecular_subtype=subtype,
                created_at=now,
                updated_at=now,
            )
            await repo.upsert_case(db, case)
            if cnv_sample:
                await repo.upsert_genomics(
                    db,
                    CaseGenomics(
                        case_id=case.case_id,
                        source="synthetic",
                        copy_numbers=cnv_sample,
                        created_at=now,
                    ),
                )
            inserted += 1

    logger.info(
        "synthetic_seed_complete",
        extra={"extra_fields": {"event": "synthetic_seed_complete", "cases": inserted}},
    )
    return inserted


def main() -> None:
    n = asyncio.run(seed())
    print(f"seeded {n} synthetic cases")


if __name__ == "__main__":
    main()
