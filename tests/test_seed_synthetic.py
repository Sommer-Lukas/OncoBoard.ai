"""Synthetic seed path: coverage, idempotency, genomics blob."""
from src.data import seed_synthetic
from src.db import repository as repo
from src.db.connection import connect


async def test_seeds_four_cases_all_subtypes(seeded_db):
    async with connect() as db:
        assert await repo.count_cases(db) == 4
        cases = await repo.list_cases(db, limit=10)
        subtypes = {c.molecular_subtype for c in cases}
    assert subtypes == {
        "Luminal A", "Luminal B", "HER2-enriched", "Triple Negative"
    }


async def test_seed_is_idempotent(seeded_db):
    # seeded_db already seeded once; seed again.
    n = await seed_synthetic.seed()
    assert n == 4
    async with connect() as db:
        assert await repo.count_cases(db) == 4


async def test_synthetic_genomics_blob_lookup(seeded_db):
    async with connect() as db:
        genes = await repo.get_gene_copy_numbers(
            db, "SYN-002", ["ERBB2", "TP53"], source="synthetic"
        )
    # SYN-002 is Luminal B (HER2+); fixture sets ERBB2=5.0
    assert genes["ERBB2"] == 5.0
    assert genes["TP53"] == 1.0
