"""Seed the Neon Postgres DB from the TCGA-BRCA dataset.

Only the four patients with imaging data on Vercel Blob are seeded.
Everything is batched with executemany — three round-trips total.

Usage:
    python -m src.data.seed_tcga --raw-dir data/raw
    python -m src.data.seed_tcga \\
        --raw-dir data/raw \\
        --images-dir data/raw/MRI_and_SVS_Patches \\
        --blob-base-url https://yngqognljuucdmpc.public.blob.vercel-storage.com
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pandas as pd

from src.data.subtype import classify
from src.db.connection import connect
from src.db.init_db import init_db
from src.logging_setup import get_logger

logger = get_logger(__name__)

DEFAULT_RAW_DIR = Path("data/raw")
TREATMENT_CSV = "Clinical_Treatment_Data.csv"
DEMOGRAPHIC_CSV = "Clinical_Demographic_Data.csv"
CNV_CSV = "CNV_RAW.csv"

# Only seed the four patients that have imaging on Vercel Blob.
SEED_PATIENTS = {"TCGA-AO-A03M", "TCGA-AO-A03V", "TCGA-AO-A0J8", "TCGA-AO-A0J9"}


# ── helpers ──────────────────────────────────────────────────────────────────

def _clean(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, str):
        s = value.strip()
        return None if s == "" or s.lower() == "nan" else s
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
    drugs: set[str] = set()
    seen: set[str] = set()
    for col, val in row.items():
        if not col.startswith("Drug_"):
            continue
        try:
            if int(val) != 1:
                continue
        except (TypeError, ValueError):
            continue
        name = col[len("Drug_"):].strip()
        if name.lower() not in seen:
            seen.add(name.lower())
            drugs.add(name)
    return sorted(drugs)


def _case_to_row(t: dict, demographic_row: pd.Series | None, now: str) -> tuple:
    er = t.get("er_status_by_ihc")
    pr = t.get("pr_status_by_ihc")
    her2 = t.get("her2_status_by_ihc")
    drugs = _extract_drugs(pd.Series(t))
    treatments: dict[str, Any] = {"drugs": drugs}
    if t.get("surgical_procedure_first"):
        treatments["surgery"] = t["surgical_procedure_first"]

    return (
        str(t["bcr_patient_barcode"]),                              # $1  case_id
        _to_int(t.get("age_at_diagnosis")) or _to_int(t.get("Age_in_Years")),  # $2
        t.get("gender"),                                            # $3
        t.get("race"),                                              # $4
        t.get("ethnicity"),                                         # $5
        t.get("vital_status"),                                      # $6
        t.get("tumor_status"),                                      # $7
        t.get("menopause_status"),                                  # $8
        t.get("ajcc_pathologic_tumor_stage"),                       # $9
        t.get("ajcc_tumor_pathologic_pt"),                          # $10
        t.get("ajcc_nodes_pathologic_pn"),                          # $11
        t.get("ajcc_metastasis_pathologic_pm"),                     # $12
        t.get("histological_type"),                                 # $13
        t.get("anatomic_neoplasm_subdivision"),                     # $14
        t.get("margin_status"),                                     # $15
        t.get("surgical_procedure_first"),                          # $16
        _to_int(t.get("lymph_nodes_examined_count")),               # $17
        er,                                                         # $18
        pr,                                                         # $19
        her2,                                                       # $20
        t.get("her2_ihc_score"),                                    # $21
        classify(er, pr, her2),                                     # $22
        json.dumps(treatments),                                     # $23
        _to_int(t.get("last_contact_days_to")),                     # $24
        json.dumps({k: v for k, v in t.items() if v is not None and not k.startswith("Drug_")}),  # $25
        json.dumps(_clean_row(demographic_row)) if demographic_row is not None else None,  # $26
        now,                                                        # $27 created_at
        now,                                                        # $28 updated_at
    )


def _cnv_row_to_json(row: pd.Series) -> str:
    out: dict[str, float] = {}
    for col, val in row.items():
        if col == "Patient_ID":
            continue
        if isinstance(val, float) and math.isnan(val):
            continue
        if val is None:
            continue
        try:
            gene = col[len("CNV_"):] if col.startswith("CNV_") else col
            out[gene] = float(val)
        except (TypeError, ValueError):
            continue
    return json.dumps(out)


def _blob_url(blob_base_url: str, images_dir: Path, img_path: Path) -> str:
    rel = img_path.relative_to(images_dir.parent).as_posix()
    return f"{blob_base_url.rstrip('/')}/{quote(rel, safe='/')}"


# ── main ─────────────────────────────────────────────────────────────────────

UPSERT_CASE_SQL = """
INSERT INTO cases (
    case_id, age_at_diagnosis, gender, race, ethnicity, vital_status,
    tumor_status, menopause_status, ajcc_stage, ajcc_t, ajcc_n, ajcc_m,
    histological_type, anatomic_subdivision, margin_status, surgical_procedure,
    lymph_nodes_examined, er_status, pr_status, her2_status, her2_ihc_score,
    molecular_subtype, treatments_json, last_contact_days_to,
    source_treatment_json, source_demographic_json, created_at, updated_at
) VALUES (
    $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,
    $21,$22,$23,$24,$25,$26,$27,$28
)
ON CONFLICT(case_id) DO UPDATE SET
    age_at_diagnosis=EXCLUDED.age_at_diagnosis, gender=EXCLUDED.gender,
    race=EXCLUDED.race, ethnicity=EXCLUDED.ethnicity,
    vital_status=EXCLUDED.vital_status, tumor_status=EXCLUDED.tumor_status,
    menopause_status=EXCLUDED.menopause_status, ajcc_stage=EXCLUDED.ajcc_stage,
    ajcc_t=EXCLUDED.ajcc_t, ajcc_n=EXCLUDED.ajcc_n, ajcc_m=EXCLUDED.ajcc_m,
    histological_type=EXCLUDED.histological_type,
    anatomic_subdivision=EXCLUDED.anatomic_subdivision,
    margin_status=EXCLUDED.margin_status,
    surgical_procedure=EXCLUDED.surgical_procedure,
    lymph_nodes_examined=EXCLUDED.lymph_nodes_examined,
    er_status=EXCLUDED.er_status, pr_status=EXCLUDED.pr_status,
    her2_status=EXCLUDED.her2_status, her2_ihc_score=EXCLUDED.her2_ihc_score,
    molecular_subtype=EXCLUDED.molecular_subtype,
    treatments_json=EXCLUDED.treatments_json,
    last_contact_days_to=EXCLUDED.last_contact_days_to,
    source_treatment_json=EXCLUDED.source_treatment_json,
    source_demographic_json=EXCLUDED.source_demographic_json,
    updated_at=EXCLUDED.updated_at
"""

UPSERT_GENOMICS_SQL = """
INSERT INTO case_genomics (case_id, source, copy_numbers_json, created_at)
VALUES ($1, $2, $3, $4)
ON CONFLICT(case_id, source) DO UPDATE SET
    copy_numbers_json = EXCLUDED.copy_numbers_json,
    created_at = EXCLUDED.created_at
"""

INSERT_FILE_SQL = """
INSERT INTO case_files
    (case_id, file_type, file_path, series_id, sequence_index, created_at)
VALUES ($1, $2, $3, $4, $5, $6)
"""


async def seed(
    raw_dir: Path,
    images_dir: Path | None = None,
    blob_base_url: str | None = None,
) -> dict[str, int]:
    treatment_path = raw_dir / TREATMENT_CSV
    if not treatment_path.exists():
        raise FileNotFoundError(f"missing {treatment_path}")

    logger.info("seed_tcga_start", extra={"extra_fields": {"event": "seed_tcga_start"}})
    await init_db()
    now = datetime.now(timezone.utc).isoformat()

    # ── cases ────────────────────────────────────────────────────────────────
    treatment_df = pd.read_csv(treatment_path, low_memory=False)
    demographic_path = raw_dir / DEMOGRAPHIC_CSV
    demo_index: dict[str, pd.Series] = {}
    if demographic_path.exists():
        demo_df = pd.read_csv(demographic_path, low_memory=False)
        if "Patient_ID" in demo_df.columns:
            for _, drow in demo_df.iterrows():
                pid = drow.get("Patient_ID")
                if isinstance(pid, str):
                    demo_index[pid] = drow

    case_rows: list[tuple] = []
    subtype_counts: dict[str, int] = {}
    for _, trow in treatment_df.iterrows():
        barcode = trow.get("bcr_patient_barcode")
        if not isinstance(barcode, str) or barcode.strip() not in SEED_PATIENTS:
            continue
        t = _clean_row(trow)
        row = _case_to_row(t, demo_index.get(barcode.strip()), now)
        case_rows.append(row)
        subtype = classify(t.get("er_status_by_ihc"), t.get("pr_status_by_ihc"), t.get("her2_status_by_ihc")) or "Unknown"
        subtype_counts[subtype] = subtype_counts.get(subtype, 0) + 1

    async with connect() as db:
        async with db.transaction():
            await db.executemany(UPSERT_CASE_SQL, case_rows)

    inserted_cases = len(case_rows)
    logger.info("seed_tcga_cases_done", extra={"extra_fields": {"event": "seed_tcga_cases_done", "cases": inserted_cases}})

    # ── genomics ─────────────────────────────────────────────────────────────
    inserted_genomics = 0
    cnv_path = raw_dir / CNV_CSV
    if cnv_path.exists():
        cnv_df = pd.read_csv(cnv_path, low_memory=False)
        genomics_rows: list[tuple] = []
        for _, row in cnv_df.iterrows():
            pid = row.get("Patient_ID")
            if not isinstance(pid, str) or pid.strip() not in SEED_PATIENTS:
                continue
            genomics_rows.append((pid.strip(), "CNV_RAW", _cnv_row_to_json(row), now))

        if genomics_rows:
            async with connect() as db:
                async with db.transaction():
                    await db.executemany(UPSERT_GENOMICS_SQL, genomics_rows)
            inserted_genomics = len(genomics_rows)

        logger.info("seed_tcga_genomics_done", extra={"extra_fields": {"event": "seed_tcga_genomics_done", "genomics_rows": inserted_genomics}})

    # ── images ────────────────────────────────────────────────────────────────
    inserted_files = 0
    if images_dir is not None and images_dir.exists():
        file_rows: list[tuple] = []
        for patient_id in SEED_PATIENTS:
            patient_dir = images_dir / patient_id
            if not patient_dir.is_dir():
                continue
            for top_dir in sorted(patient_dir.iterdir()):
                if not top_dir.is_dir():
                    continue
                is_svs = "SVS_patches" in top_dir.name or "svs_patches" in top_dir.name.lower()
                if is_svs:
                    for img in sorted(top_dir.glob("*.jpg")):
                        path = _blob_url(blob_base_url, images_dir, img) if blob_base_url else str(img)
                        file_rows.append((patient_id, "svs_patch", path, top_dir.name, None, now))
                else:
                    for series_dir in sorted(top_dir.iterdir()):
                        if not series_dir.is_dir():
                            continue
                        for img in sorted(series_dir.glob("*.jpg")):
                            seq = _parse_seq(img.stem)
                            path = _blob_url(blob_base_url, images_dir, img) if blob_base_url else str(img)
                            file_rows.append((patient_id, "mri_patch", path, series_dir.name, seq, now))

        if file_rows:
            async with connect() as db:
                async with db.transaction():
                    await db.executemany(INSERT_FILE_SQL, file_rows)
            inserted_files = len(file_rows)

        logger.info("seed_tcga_images_done", extra={"extra_fields": {"event": "seed_tcga_images_done", "files": inserted_files}})

    return {"cases": inserted_cases, "genomics": inserted_genomics, "files": inserted_files, **{f"subtype_{k}": v for k, v in subtype_counts.items()}}


def _parse_seq(stem: str) -> int | None:
    parts = stem.split("_")
    try:
        return int(parts[-1])
    except (ValueError, IndexError):
        return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", default=str(DEFAULT_RAW_DIR))
    parser.add_argument("--images-dir", default=None)
    parser.add_argument("--blob-base-url", default=None)
    args = parser.parse_args()
    result = asyncio.run(seed(
        Path(args.raw_dir),
        Path(args.images_dir) if args.images_dir else None,
        blob_base_url=args.blob_base_url,
    ))
    print("seed complete:")
    for k, v in sorted(result.items()):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
