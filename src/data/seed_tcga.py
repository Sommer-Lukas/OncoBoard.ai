"""Seed the DB from the real TCGA-BRCA dataset (Kaggle).

Expects the three raw CSVs under data/raw/:
    Clinical_Treatment_Data.csv    (primary patient cohort, ~1097 rows)
    Clinical_Demographic_Data.csv  (richer TCGA fields, joined as source JSON)
    CNV_RAW.csv                    (copy-number variation, ~59K gene columns)

Optional MRI/SVS image directory is registered as case_files when --images-dir
is provided. When --blob-base-url is also given, file_path stores the full Vercel
Blob URL instead of a local filesystem path.

Usage:
    .venv/bin/python -m src.data.seed_tcga
    .venv/bin/python -m src.data.seed_tcga --images-dir data/raw/MRI_and_SVS_Patches
    .venv/bin/python -m src.data.seed_tcga \\
        --images-dir data/raw/MRI_and_SVS_Patches \\
        --blob-base-url https://yngqognljuucdmpc.public.blob.vercel-storage.com
"""
from __future__ import annotations

import argparse
import asyncio
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

import pandas as pd

from src.data.subtype import classify
from src.db import repository as repo
from src.db.connection import connect
from src.db.init_db import init_db
from src.db.models import Case, CaseFile, CaseGenomics
from src.logging_setup import get_logger

logger = get_logger(__name__)

DEFAULT_RAW_DIR = Path("data/raw")
TREATMENT_CSV = "Clinical_Treatment_Data.csv"
DEMOGRAPHIC_CSV = "Clinical_Demographic_Data.csv"
CNV_CSV = "CNV_RAW.csv"


# -------- helpers --------

def _clean(value: Any) -> Any:
    """Convert pandas NaN/None/empty to None; keep other scalars as-is."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "" or stripped.lower() == "nan":
            return None
        return stripped
    return value


def _clean_row(row: pd.Series) -> dict[str, Any]:
    return {k: _clean(v) for k, v in row.to_dict().items()}


def _to_int(value: Any) -> int | None:
    v = _clean(value)
    if v is None:
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _extract_drugs(row: pd.Series) -> list[str]:
    """Treatment CSV one-hots drugs as Drug_<Name> columns with 0/1 values.
    Returns the list of drug names whose flag is 1, deduped case-insensitively."""
    drugs: set[str] = set()
    seen_lower: set[str] = set()
    for col, val in row.items():
        if not col.startswith("Drug_"):
            continue
        try:
            flag = int(val)
        except (TypeError, ValueError):
            continue
        if flag != 1:
            continue
        name = col[len("Drug_"):].strip()
        key = name.lower()
        if key in seen_lower:
            continue
        seen_lower.add(key)
        drugs.add(name)
    return sorted(drugs)


def _build_case(treatment_row: pd.Series, demographic_row: pd.Series | None, now: str) -> Case:
    t = _clean_row(treatment_row)
    er = t.get("er_status_by_ihc")
    pr = t.get("pr_status_by_ihc")
    her2 = t.get("her2_status_by_ihc")
    drugs = _extract_drugs(treatment_row)
    treatments: dict[str, Any] = {"drugs": drugs}
    if t.get("surgical_procedure_first"):
        treatments["surgery"] = t.get("surgical_procedure_first")

    return Case(
        case_id=str(t["bcr_patient_barcode"]),
        age_at_diagnosis=_to_int(t.get("age_at_diagnosis")) or _to_int(t.get("Age_in_Years")),
        gender=t.get("gender"),
        race=t.get("race"),
        ethnicity=t.get("ethnicity"),
        vital_status=t.get("vital_status"),
        tumor_status=t.get("tumor_status"),
        menopause_status=t.get("menopause_status"),
        ajcc_stage=t.get("ajcc_pathologic_tumor_stage"),
        ajcc_t=t.get("ajcc_tumor_pathologic_pt"),
        ajcc_n=t.get("ajcc_nodes_pathologic_pn"),
        ajcc_m=t.get("ajcc_metastasis_pathologic_pm"),
        histological_type=t.get("histological_type"),
        anatomic_subdivision=t.get("anatomic_neoplasm_subdivision"),
        margin_status=t.get("margin_status"),
        surgical_procedure=t.get("surgical_procedure_first"),
        lymph_nodes_examined=_to_int(t.get("lymph_nodes_examined_count")),
        er_status=er,
        pr_status=pr,
        her2_status=her2,
        her2_ihc_score=t.get("her2_ihc_score"),
        molecular_subtype=classify(er, pr, her2),
        treatments=treatments,
        last_contact_days_to=_to_int(t.get("last_contact_days_to")),
        source_treatment={k: v for k, v in t.items() if v is not None and not k.startswith("Drug_")},
        source_demographic=(_clean_row(demographic_row) if demographic_row is not None else None),
        created_at=now,
        updated_at=now,
    )


def _cnv_row_to_dict(row: pd.Series) -> dict[str, float]:
    """Strip the CNV_ prefix and drop NaN cells. Float-coerce remaining values."""
    out: dict[str, float] = {}
    for col, val in row.items():
        if col == "Patient_ID":
            continue
        if isinstance(val, float) and math.isnan(val):
            continue
        if val is None:
            continue
        try:
            f = float(val)
        except (TypeError, ValueError):
            continue
        gene = col[len("CNV_"):] if col.startswith("CNV_") else col
        out[gene] = f
    return out


# -------- main seed routine --------

async def seed(
    raw_dir: Path,
    images_dir: Path | None = None,
    blob_base_url: str | None = None,
) -> dict[str, int]:
    treatment_path = raw_dir / TREATMENT_CSV
    demographic_path = raw_dir / DEMOGRAPHIC_CSV
    cnv_path = raw_dir / CNV_CSV

    if not treatment_path.exists():
        raise FileNotFoundError(f"missing {treatment_path} — download the Kaggle dataset first")

    logger.info("seed_tcga_start", extra={"extra_fields": {"event": "seed_tcga_start"}})

    await init_db()

    now = datetime.now(timezone.utc).isoformat()

    # ---- cases ----
    treatment_df = pd.read_csv(treatment_path, low_memory=False)
    demographic_df = (
        pd.read_csv(demographic_path, low_memory=False) if demographic_path.exists() else None
    )

    demo_index: dict[str, pd.Series] = {}
    if demographic_df is not None and "Patient_ID" in demographic_df.columns:
        for _, drow in demographic_df.iterrows():
            pid = drow.get("Patient_ID")
            if isinstance(pid, str):
                demo_index[pid] = drow

    inserted_cases = 0
    subtype_counts: dict[str, int] = {}

    async with connect() as db:
        async with db.transaction():
            for _, trow in treatment_df.iterrows():
                barcode = trow.get("bcr_patient_barcode")
                if not isinstance(barcode, str) or not barcode.strip():
                    continue
                demo_row = demo_index.get(barcode)
                case = _build_case(trow, demo_row, now)
                await repo.upsert_case(db, case)
                inserted_cases += 1
                key = case.molecular_subtype or "Unknown"
                subtype_counts[key] = subtype_counts.get(key, 0) + 1

    logger.info(
        "seed_tcga_cases_done",
        extra={"extra_fields": {
            "event": "seed_tcga_cases_done",
            "cases": inserted_cases,
            "subtypes": subtype_counts,
        }},
    )

    # ---- genomics ----
    inserted_genomics = 0
    if cnv_path.exists():
        cnv_df = pd.read_csv(cnv_path, low_memory=False)
        async with connect() as db:
            async with db.transaction():
                for _, row in cnv_df.iterrows():
                    pid = row.get("Patient_ID")
                    if not isinstance(pid, str):
                        continue
                    # Only attach genomics for cases we actually inserted.
                    existing = await repo.get_case(db, pid)
                    if not existing:
                        continue
                    copy_numbers = _cnv_row_to_dict(row)
                    if not copy_numbers:
                        continue
                    await repo.upsert_genomics(
                        db,
                        CaseGenomics(
                            case_id=pid,
                            source="CNV_RAW",
                            copy_numbers=copy_numbers,
                            created_at=now,
                        ),
                    )
                    inserted_genomics += 1

        logger.info(
            "seed_tcga_genomics_done",
            extra={"extra_fields": {"event": "seed_tcga_genomics_done", "genomics_rows": inserted_genomics}},
        )

    # ---- images (optional) ----
    inserted_files = 0
    if images_dir is not None:
        if not images_dir.exists():
            logger.info(
                "seed_tcga_images_skip",
                extra={"extra_fields": {"event": "seed_tcga_images_skip", "reason": "missing", "path": str(images_dir)}},
            )
        else:
            inserted_files = await _seed_images(images_dir, now, blob_base_url=blob_base_url)
            logger.info(
                "seed_tcga_images_done",
                extra={"extra_fields": {"event": "seed_tcga_images_done", "files": inserted_files}},
            )

    return {
        "cases": inserted_cases,
        "genomics": inserted_genomics,
        "files": inserted_files,
        **{f"subtype_{k}": v for k, v in subtype_counts.items()},
    }


def _file_type_from_dir(dir_name: str) -> str:
    """Classify a patient subdirectory as mri_patch or svs_patch."""
    if "SVS_patches" in dir_name or "svs_patches" in dir_name.lower():
        return "svs_patch"
    return "mri_patch"


def _blob_url(blob_base_url: str, images_dir: Path, img_path: Path) -> str:
    """Construct the Vercel Blob URL for an image file.

    Blob paths mirror the local structure relative to images_dir's parent, e.g.:
      local:  data/raw/MRI_and_SVS_Patches/TCGA-AO-A03M/TCGA-AO-A03M_mri_processed/.../img.jpg
      blob:   {blob_base_url}/MRI_and_SVS_Patches/TCGA-AO-A03M/TCGA-AO-A03M_mri_processed/.../img.jpg
    """
    # relative_to(images_dir.parent) gives "MRI_and_SVS_Patches/..."
    rel = img_path.relative_to(images_dir.parent).as_posix()
    return f"{blob_base_url.rstrip('/')}/{quote(rel, safe='/')}"


async def _seed_images(
    images_dir: Path,
    now: str,
    *,
    blob_base_url: str | None = None,
) -> int:
    """Walk patient image directories and register files in the DB.

    file_path stores either the full Vercel Blob URL (when blob_base_url is
    given) or the local absolute path (for local-only seeding).
    Only registers files whose case_id is already in the DB.
    """
    inserted = 0
    async with connect() as db:
        patient_dirs: Iterable[Path] = (p for p in images_dir.iterdir() if p.is_dir())
        for patient_dir in patient_dirs:
            case_id = patient_dir.name
            existing = await repo.get_case(db, case_id)
            if not existing:
                continue
            async with db.transaction():
                for top_dir in sorted(patient_dir.iterdir()):
                    if not top_dir.is_dir():
                        continue
                    ftype = _file_type_from_dir(top_dir.name)
                    if ftype == "svs_patch":
                        # SVS patches are directly in the top_dir
                        for img_path in sorted(top_dir.glob("*.jpg")):
                            path = (
                                _blob_url(blob_base_url, images_dir, img_path)
                                if blob_base_url
                                else str(img_path)
                            )
                            await repo.add_case_file(
                                db,
                                CaseFile(
                                    case_id=case_id,
                                    file_type="svs_patch",
                                    file_path=path,
                                    series_id=top_dir.name,
                                    sequence_index=None,
                                    created_at=now,
                                ),
                            )
                            inserted += 1
                    else:
                        # MRI patches are nested: top_dir/series_dir/img.jpg
                        for series_dir in sorted(top_dir.iterdir()):
                            if not series_dir.is_dir():
                                continue
                            for img_path in sorted(series_dir.glob("*.jpg")):
                                seq = _parse_seq_index(img_path.stem)
                                path = (
                                    _blob_url(blob_base_url, images_dir, img_path)
                                    if blob_base_url
                                    else str(img_path)
                                )
                                await repo.add_case_file(
                                    db,
                                    CaseFile(
                                        case_id=case_id,
                                        file_type="mri_patch",
                                        file_path=path,
                                        series_id=series_dir.name,
                                        sequence_index=seq,
                                        created_at=now,
                                    ),
                                )
                                inserted += 1
    return inserted


def _parse_seq_index(stem: str) -> int | None:
    # Filenames look like TCGA-AO-A03M_img_0000
    parts = stem.split("_")
    if not parts:
        return None
    try:
        return int(parts[-1])
    except ValueError:
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Postgres from the TCGA-BRCA Kaggle dataset")
    parser.add_argument("--raw-dir", default=str(DEFAULT_RAW_DIR), help="Directory holding the 3 CSVs")
    parser.add_argument("--images-dir", default=None, help="Optional path to extracted MRI_and_SVS_Patches/")
    parser.add_argument(
        "--blob-base-url",
        default=None,
        help="Vercel Blob base URL. When set, file_path stores blob URLs instead of local paths.",
    )
    args = parser.parse_args()
    raw_dir = Path(args.raw_dir)
    images_dir = Path(args.images_dir) if args.images_dir else None
    result = asyncio.run(seed(raw_dir, images_dir, blob_base_url=args.blob_base_url))
    print("seed complete:")
    for k, v in sorted(result.items()):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
