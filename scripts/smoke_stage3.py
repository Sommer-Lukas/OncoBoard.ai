"""Stage 3 smoke test. Run from repo root with:
    .\\.venv\\Scripts\\python.exe scripts\\smoke_stage3.py
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Each phase uses its own isolated DB so we don't pollute the working DB.
SYN_DB = Path("./.smoke_stage3_syn.db")
TCGA_DB = Path("./.smoke_stage3_tcga.db")


async def phase_synthetic() -> None:
    os.environ["DB_PATH"] = str(SYN_DB)
    if SYN_DB.exists():
        SYN_DB.unlink()

    # Re-import affected modules so they see the new DB_PATH via get_settings cache.
    from src.config import get_settings
    get_settings.cache_clear()  # type: ignore[attr-defined]

    from src.data import seed_synthetic
    from src.data.subtype import classify
    from src.db import repository as repo
    from src.db.connection import connect

    # Classifier sanity (independent of seeding)
    assert classify("Positive", "Positive", "Negative") == "Luminal A"
    assert classify("Positive", "Positive", "Positive") == "Luminal B"
    assert classify("Negative", "Negative", "Positive") == "HER2-enriched"
    assert classify("Negative", "Negative", "Negative") == "Triple Negative"
    assert classify("Equivocal", "Positive", "Negative") == "Luminal A"  # PR rescues
    assert classify(None, None, "Negative") is None
    print("[ok] subtype classifier rules")

    n = await seed_synthetic.seed()
    assert n == 4

    async with connect() as db:
        total = await repo.count_cases(db)
        assert total == 4
        # Re-running is idempotent (upsert by case_id)
        n2 = await seed_synthetic.seed()
        assert n2 == 4
        async with connect() as db2:
            total2 = await repo.count_cases(db2)
            assert total2 == 4

        # Subtype distribution covers all four
        subtypes = set()
        for case in await repo.list_cases(db, limit=10):
            subtypes.add(case.molecular_subtype)
        assert subtypes == {"Luminal A", "Luminal B", "HER2-enriched", "Triple Negative"}
        print(f"[ok] synthetic seed: 4 cases, subtypes={sorted(subtypes)}")

        # CNV blob lookup works
        genes = await repo.get_gene_copy_numbers(
            db, "SYN-002", ["ERBB2", "TP53"], source="synthetic"
        )
        # SYN-002 = Luminal B (HER2+), ERBB2 = 5.0
        assert genes["ERBB2"] == 5.0 and genes["TP53"] == 1.0
        print(f"[ok] synthetic genomics lookup: {genes}")

    SYN_DB.unlink()


async def phase_tcga() -> None:
    raw_dir = Path("data/raw")
    if not (raw_dir / "Clinical_Treatment_Data.csv").exists():
        print("[skip] TCGA phase — data/raw/Clinical_Treatment_Data.csv not present")
        return

    os.environ["DB_PATH"] = str(TCGA_DB)
    if TCGA_DB.exists():
        TCGA_DB.unlink()

    from src.config import get_settings
    get_settings.cache_clear()  # type: ignore[attr-defined]

    from src.data import seed_tcga
    from src.db import repository as repo
    from src.db.connection import connect

    result = await seed_tcga.seed(raw_dir)
    print(f"[ok] tcga seed result: {result}")

    assert result["cases"] >= 1000, f"expected ~1097 cases, got {result['cases']}"
    assert result["genomics"] >= 100, f"expected ~125 genomics rows, got {result['genomics']}"

    async with connect() as db:
        total = await repo.count_cases(db)
        assert total == result["cases"]

        # Spot-check that a real TCGA case made it in with a derived subtype
        spot = await repo.get_case(db, "TCGA-3C-AALI")
        assert spot is not None
        assert spot.er_status == "Positive"
        assert spot.her2_status == "Positive"
        assert spot.molecular_subtype == "Luminal B"
        assert isinstance(spot.treatments, dict) and "drugs" in spot.treatments
        print(f"[ok] TCGA-3C-AALI: subtype={spot.molecular_subtype}, drugs={spot.treatments['drugs']}")

        # CNV lookup on a real case that has genomics
        # TCGA-AO-A03M is in CNV_RAW.csv
        cnv = await repo.get_gene_copy_numbers(db, "TCGA-AO-A03M", ["TP53", "BRCA1", "ERBB2"])
        non_null = [k for k, v in cnv.items() if v is not None]
        assert len(non_null) == 3, f"expected all 3 genes present, got {cnv}"
        print(f"[ok] TCGA-AO-A03M CNV lookup: {cnv}")

        # List by molecular subtype
        tnbc = await repo.list_cases(db, molecular_subtype="Triple Negative", limit=5)
        print(f"[ok] {len(tnbc)} TNBC cases sampled (first IDs: {[c.case_id for c in tnbc[:3]]})")

    TCGA_DB.unlink()


async def main() -> None:
    await phase_synthetic()
    await phase_tcga()
    print("\nSMOKE TEST PASSED")


if __name__ == "__main__":
    asyncio.run(main())
