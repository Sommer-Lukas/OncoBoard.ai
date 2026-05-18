"""CaseCompiler — pulls a case together and flags missing data.

DB-only: no Gemini call. It assembles the clinical fields, a genomics
summary, and a file inventory, then flags data gaps. `SummaryAgent`
consumes this output downstream.
"""
from __future__ import annotations

from typing import Any, Literal

import asyncpg
from pydantic import BaseModel

from src.agents.base import BaseAgent
from src.db import repository as repo
from src.db.models import Case

# Clinically relevant breast-cancer genes worth surfacing if CNV data exists.
NOTABLE_GENES = [
    "TP53", "BRCA1", "BRCA2", "ERBB2", "PIK3CA",
    "ESR1", "MYC", "PTEN", "CDH1", "GATA3",
]

# Fields whose absence should block or warn before a tumor board.
_CRITICAL_FIELDS = ("ajcc_stage", "er_status", "pr_status", "her2_status")
_WARNING_FIELDS = ("histological_type", "molecular_subtype", "age_at_diagnosis")


class DataGap(BaseModel):
    field: str
    severity: Literal["critical", "warning"]
    note: str


class GenomicsSummary(BaseModel):
    has_data: bool
    source: str | None = None
    gene_count: int = 0
    notable_genes: dict[str, float] = {}


class CaseCompilerOutput(BaseModel):
    case_id: str
    clinical: dict[str, Any]
    genomics: GenomicsSummary
    file_count: int
    file_types: dict[str, int]
    data_gaps: list[DataGap]
    ready_for_review: bool


class CaseCompiler(BaseAgent[CaseCompilerOutput]):
    name = "CaseCompiler"
    model_tier = "flash"
    output_schema = CaseCompilerOutput

    async def run(
        self, db: asyncpg.Connection, case: Case, *, run_id: str
    ) -> CaseCompilerOutput:
        clinical = {
            "age_at_diagnosis": case.age_at_diagnosis,
            "ajcc_stage": case.ajcc_stage,
            "ajcc_t": case.ajcc_t,
            "ajcc_n": case.ajcc_n,
            "ajcc_m": case.ajcc_m,
            "histological_type": case.histological_type,
            "er_status": case.er_status,
            "pr_status": case.pr_status,
            "her2_status": case.her2_status,
            "her2_ihc_score": case.her2_ihc_score,
            "molecular_subtype": case.molecular_subtype,
            "menopause_status": case.menopause_status,
            "treatments": case.treatments,
        }

        genomics = await self._summarize_genomics(db, case.case_id)
        file_types = await self._inventory_files(db, case.case_id)
        file_count = sum(file_types.values())
        gaps = self._find_gaps(case)
        ready = not any(g.severity == "critical" for g in gaps)

        return CaseCompilerOutput(
            case_id=case.case_id,
            clinical=clinical,
            genomics=genomics,
            file_count=file_count,
            file_types=file_types,
            data_gaps=gaps,
            ready_for_review=ready,
        )

    async def _summarize_genomics(
        self, db: asyncpg.Connection, case_id: str
    ) -> GenomicsSummary:
        record = await repo.get_genomics_any(db, case_id)
        if record is None:
            return GenomicsSummary(has_data=False)
        notable = {
            g: record.copy_numbers[g]
            for g in NOTABLE_GENES
            if g in record.copy_numbers
        }
        return GenomicsSummary(
            has_data=True,
            source=record.source,
            gene_count=len(record.copy_numbers),
            notable_genes=notable,
        )

    async def _inventory_files(
        self, db: asyncpg.Connection, case_id: str
    ) -> dict[str, int]:
        files = await repo.list_case_files(db, case_id)
        counts: dict[str, int] = {}
        for f in files:
            counts[f.file_type] = counts.get(f.file_type, 0) + 1
        return counts

    def _find_gaps(self, case: Case) -> list[DataGap]:
        gaps: list[DataGap] = []
        for field in _CRITICAL_FIELDS:
            if getattr(case, field) in (None, ""):
                gaps.append(DataGap(
                    field=field,
                    severity="critical",
                    note=f"{field} is required for guideline matching and is missing",
                ))
        for field in _WARNING_FIELDS:
            if getattr(case, field) in (None, ""):
                gaps.append(DataGap(
                    field=field,
                    severity="warning",
                    note=f"{field} is missing; downstream agents will have reduced context",
                ))
        return gaps
