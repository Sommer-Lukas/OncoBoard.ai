"""PathologyAgent — genomic + biopsy interpretation in CAP synoptic format.

Reads copy-number data and clinical biopsy fields, interprets driver gene
alterations and IHC in pathologist language. Uses Gemini Pro.
"""
from __future__ import annotations

import json

import asyncpg
from pydantic import BaseModel, ValidationError

from src.agents.base import BaseAgent
from src.agents.types import AgentError
from src.db import repository as repo
from src.db.models import Case

_SYSTEM = (
    "You are a breast cancer pathologist preparing a CAP synoptic-format report "
    "for a multidisciplinary tumor board. Use precise pathologist language and "
    "CAP/WHO breast tumor classification terminology. "
    "Do not recommend treatment. "
    "Respond strictly as JSON matching the provided schema."
)

_DRIVER_GENES = [
    "ERBB2", "TP53", "BRCA1", "BRCA2", "PIK3CA", "ESR1",
    "MYC", "PTEN", "CDH1", "GATA3", "CCND1", "RB1", "AKT1",
]
_AMP_THRESHOLD = 2.5
_DEL_THRESHOLD = 1.5


class PathologyOutput(BaseModel):
    case_id: str
    ihc_profile: dict[str, str]       # {"ER": "Positive (Allred 7/8)", "HER2": "2+ (equivocal)"}
    molecular_subtype_interpretation: str
    driver_alterations: list[str]     # e.g. ["ERBB2 amplification (CNV 4.2)"]
    prognostic_markers: list[str]
    synoptic_summary: str             # CAP-style narrative paragraph
    pathologist_comment: str
    data_gaps: list[str]


class PathologyAgent(BaseAgent[PathologyOutput]):
    name = "PathologyAgent"
    model_tier = "pro"
    output_schema = PathologyOutput

    async def run(
        self, db: asyncpg.Connection, case: Case, *, run_id: str
    ) -> PathologyOutput:
        genomics = await repo.get_genomics_any(db, case.case_id)
        gene_cnv: dict[str, float | None] = {g: None for g in _DRIVER_GENES}
        if genomics:
            for gene in _DRIVER_GENES:
                gene_cnv[gene] = genomics.copy_numbers.get(gene)

        alterations: list[str] = []
        for gene, cnv in gene_cnv.items():
            if cnv is None:
                continue
            if cnv >= _AMP_THRESHOLD:
                alterations.append(f"{gene} amplification (CNV {cnv:.2f})")
            elif cnv <= _DEL_THRESHOLD:
                alterations.append(f"{gene} deletion/loss (CNV {cnv:.2f})")

        cnv_lines = "\n".join(
            f"  {g}: {v:.2f}" for g, v in gene_cnv.items() if v is not None
        ) or "  No CNV data available"

        prompt = (
            "Pathology and genomics data for CAP synoptic report:\n\n"
            "IHC / receptor status:\n"
            f"  ER: {case.er_status or 'Not reported'}\n"
            f"  PR: {case.pr_status or 'Not reported'}\n"
            f"  HER2 IHC: {case.her2_status or 'Not reported'} "
            f"(score: {case.her2_ihc_score or 'N/A'})\n"
            f"  Molecular subtype (derived at seed): {case.molecular_subtype or 'Unknown'}\n\n"
            "Surgical/pathologic data:\n"
            f"  Histological type: {case.histological_type or 'Not reported'}\n"
            f"  Margin status: {case.margin_status or 'Not reported'}\n"
            f"  Surgical procedure: {case.surgical_procedure or 'Not reported'}\n"
            f"  Lymph nodes examined: {case.lymph_nodes_examined or 'Not reported'}\n"
            f"  AJCC stage: {case.ajcc_stage or 'Unknown'} "
            f"(T{case.ajcc_t or '?'} N{case.ajcc_n or '?'} M{case.ajcc_m or '?'})\n\n"
            f"Driver gene CNV ({sum(1 for v in gene_cnv.values() if v is not None)} "
            f"of {len(_DRIVER_GENES)} genes with data):\n"
            f"{cnv_lines}\n\n"
            f"Rule-based pre-classification: {alterations or ['None detected above thresholds']}\n\n"
            "Generate a CAP synoptic-format pathology report with: IHC profile dict, "
            "molecular subtype interpretation, driver alterations with clinical significance, "
            "prognostic markers, synoptic summary paragraph, pathologist comment, and data gaps."
        )

        resp = await self.call_gemini(
            prompt=prompt,
            system_instruction=_SYSTEM,
            response_schema=PathologyOutput,
        )

        try:
            payload = json.loads(resp.text)
        except json.JSONDecodeError as e:
            raise AgentError(
                f"PathologyAgent could not parse Gemini response as JSON: {e}"
            ) from e

        payload["case_id"] = case.case_id
        try:
            return PathologyOutput.model_validate(payload)
        except ValidationError as e:
            raise AgentError(
                f"Gemini response did not match PathologyOutput schema: {e}"
            ) from e
