"""Read-only case API. All DB access goes through repository helpers."""
from typing import Annotated

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.config import get_settings
from src.db import repository
from src.db.connection import get_db
from src.db.models import AgentOutput, Case, CaseFile

router = APIRouter(prefix="/cases", tags=["cases"])

_Db = Annotated[aiosqlite.Connection, Depends(get_db)]


# ── List & detail ──────────────────────────────────────────────────────────────

class CaseListResponse(BaseModel):
    items: list[Case]
    total: int
    limit: int
    offset: int


@router.get("", response_model=CaseListResponse)
async def list_cases(
    db: _Db,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    subtype: Annotated[str | None, Query(description="molecular_subtype filter")] = None,
    has_data: Annotated[bool, Query(description="Only return cases that have genomics + imaging data")] = False,
) -> CaseListResponse:
    cases = await repository.list_cases(db, limit=limit, offset=offset, molecular_subtype=subtype, has_data=has_data)
    total = await repository.count_cases(db)
    return CaseListResponse(items=cases, total=total, limit=limit, offset=offset)


@router.get("/{case_id}", response_model=Case)
async def get_case(case_id: str, db: _Db) -> Case:
    case = await repository.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


# ── Genomics ───────────────────────────────────────────────────────────────────

class GenomicsResponse(BaseModel):
    case_id: str
    has_data: bool
    copy_numbers: dict[str, float | None]


@router.get("/{case_id}/genomics", response_model=GenomicsResponse)
async def get_case_genomics(
    case_id: str,
    db: _Db,
    genes: Annotated[
        str | None,
        Query(description="Comma-separated gene symbols to filter, e.g. TP53,BRCA1. Omit for all genes."),
    ] = None,
) -> GenomicsResponse:
    if not await repository.get_case(db, case_id):
        raise HTTPException(status_code=404, detail="Case not found")

    record = await repository.get_genomics(db, case_id)
    if not record:
        return GenomicsResponse(case_id=case_id, has_data=False, copy_numbers={})

    if genes:
        gene_list = [g.strip() for g in genes.split(",") if g.strip()]
        copy_numbers: dict[str, float | None] = {g: record.copy_numbers.get(g) for g in gene_list}
    else:
        copy_numbers = dict(record.copy_numbers)

    return GenomicsResponse(case_id=case_id, has_data=True, copy_numbers=copy_numbers)


# ── Images ─────────────────────────────────────────────────────────────────────

class ImagesResponse(BaseModel):
    case_id: str
    type: str
    images: list[str]


@router.get("/{case_id}/images", response_model=ImagesResponse)
async def list_case_images(
    case_id: str,
    type: Annotated[str, Query(description="'mri' or 'svs'")] = "mri",
) -> ImagesResponse:
    images_root = get_settings().images_dir
    patient_dir = (images_root / case_id).resolve()
    if not patient_dir.is_dir() or images_root.resolve() not in patient_dir.parents:
        return ImagesResponse(case_id=case_id, type=type, images=[])

    paths: list[str] = []

    if type == "svs":
        target = patient_dir / f"{case_id}-01Z-00-DX1SVS_patches"
        if target.is_dir():
            for f in sorted(target.glob("*.jpg")):
                paths.append(f"/images/{case_id}/{target.name}/{f.name}")

    else:  # mri
        target = patient_dir / f"{case_id}_mri_processed"
        if target.is_dir():
            for series in sorted(target.iterdir()):
                if not series.is_dir():
                    continue
                for f in sorted(series.glob("*.jpg")):
                    paths.append(f"/images/{case_id}/{target.name}/{series.name}/{f.name}")

    return ImagesResponse(case_id=case_id, type=type, images=paths)


# ── Files (DB-tracked) ─────────────────────────────────────────────────────────

@router.get("/{case_id}/files", response_model=list[CaseFile])
async def list_case_files(
    case_id: str,
    db: _Db,
    file_type: Annotated[str | None, Query(alias="type", description="e.g. mri_patch, svs_patch")] = None,
) -> list[CaseFile]:
    if not await repository.get_case(db, case_id):
        raise HTTPException(status_code=404, detail="Case not found")
    return await repository.list_case_files(db, case_id, file_type=file_type)


# ── Agent outputs ──────────────────────────────────────────────────────────────

@router.get("/{case_id}/agents/{agent_name}/latest", response_model=AgentOutput)
async def get_latest_agent_output(case_id: str, agent_name: str, db: _Db) -> AgentOutput:
    output = await repository.get_latest_agent_output(db, case_id, agent_name)
    if not output:
        raise HTTPException(status_code=404, detail="No output found for this agent/case")
    return output
