"""GuidelineAgent — maps stage + receptor status to NCCN/ESMO protocol.

Uses Gemini Pro with the patient's clinical profile to identify the applicable
NCCN Breast Cancer guideline pathway and return the matched protocol summary.
Agents surface information only — no treatment decisions.
"""
from __future__ import annotations

import json

import asyncpg
from pydantic import BaseModel, ValidationError

from src.agents.base import BaseAgent
from src.agents.types import AgentError
from src.db.models import Case

_SYSTEM = (
    "You are a breast oncologist acting as a guideline reference specialist for a "
    "multidisciplinary tumor board. Map the patient profile to the applicable NCCN "
    "Breast Cancer guideline pathway (or ESMO where more applicable). "
    "Surface the protocol — do not make an individualized treatment recommendation. "
    "Respond strictly as JSON matching the provided schema."
)


class GuidelineOutput(BaseModel):
    case_id: str
    matched_guideline: str                # e.g. "NCCN Breast Cancer v2.2024"
    guideline_pathway: str                # e.g. "HR+/HER2- Early Stage, Postmenopausal"
    recommendation_category: str          # "Preferred" | "Other Recommended" | "Useful in Certain Circumstances"
    systemic_therapy_options: list[str]   # chemo regimens or targeted agents listed in pathway
    endocrine_therapy_options: list[str]
    radiation_considerations: str
    surgery_considerations: str
    evidence_level: str                   # "Category 1" | "Category 2A" | "Category 2B" | "Category 3"
    protocol_rationale: str
    data_gaps: list[str]


class GuidelineAgent(BaseAgent[GuidelineOutput]):
    name = "GuidelineAgent"
    model_tier = "pro"
    output_schema = GuidelineOutput

    async def run(
        self, db: asyncpg.Connection, case: Case, *, run_id: str
    ) -> GuidelineOutput:
        prompt = (
            "Patient profile for guideline matching:\n"
            f"  Age: {case.age_at_diagnosis or 'Unknown'}\n"
            f"  Menopause status: {case.menopause_status or 'Unknown'}\n"
            f"  AJCC stage: {case.ajcc_stage or 'Unknown'}\n"
            f"  T: {case.ajcc_t or '?'}  "
            f"N: {case.ajcc_n or '?'}  "
            f"M: {case.ajcc_m or '?'}\n"
            f"  ER: {case.er_status or 'Unknown'}  "
            f"PR: {case.pr_status or 'Unknown'}  "
            f"HER2: {case.her2_status or 'Unknown'} (IHC score: {case.her2_ihc_score or 'N/A'})\n"
            f"  Molecular subtype: {case.molecular_subtype or 'Unknown'}\n"
            f"  Histological type: {case.histological_type or 'Unknown'}\n"
            f"  Surgical procedure: {case.surgical_procedure or 'Not yet performed'}\n"
            f"  Margin status: {case.margin_status or 'Unknown'}\n"
            f"  Lymph nodes examined: {case.lymph_nodes_examined or 'Unknown'}\n\n"
            "Identify the applicable NCCN Breast Cancer guideline pathway. Provide: "
            "matched guideline version, pathway name, recommendation category, "
            "systemic therapy options listed in the pathway, endocrine therapy options, "
            "radiation and surgery considerations, evidence level, protocol rationale, "
            "and data gaps that prevent a complete guideline match."
        )

        resp = await self.call_gemini(
            prompt=prompt,
            system_instruction=_SYSTEM,
            response_schema=GuidelineOutput,
        )

        try:
            payload = json.loads(resp.text)
        except json.JSONDecodeError as e:
            raise AgentError(
                f"GuidelineAgent could not parse Gemini response as JSON: {e}"
            ) from e

        payload["case_id"] = case.case_id
        try:
            return GuidelineOutput.model_validate(payload)
        except ValidationError as e:
            raise AgentError(
                f"Gemini response did not match GuidelineOutput schema: {e}"
            ) from e
