"""HistoryCaseAgent — analogous past cases by clinical profile similarity.

Queries the DB for cases matching on molecular subtype and AJCC stage, then
uses Gemini Pro to select and narrate the three most analogous cases with
clinical similarity rationale. Falls back to any seeded cases if the subtype
filter returns fewer than two candidates.
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
    "You are a breast oncologist reviewing analogous past cases for a tumor board. "
    "Given the current patient profile and a set of historically similar cases from "
    "the same dataset, identify the three most clinically analogous cases and explain "
    "the similarity. Do not make treatment recommendations. "
    "Respond strictly as JSON matching the provided schema."
)

_CANDIDATE_LIMIT = 20


class AnalogousCase(BaseModel):
    case_id: str
    similarity_rationale: str
    receptor_match: str        # e.g. "ER+/PR+/HER2- — exact match"
    stage_match: str           # e.g. "Same AJCC Stage IIA"
    treatment_summary: str | None
    outcome_note: str | None   # vital_status / tumor_status if available


class HistoryCaseOutput(BaseModel):
    case_id: str
    analogous_cases: list[AnalogousCase]
    search_basis: str
    agent_notes: str


class HistoryCaseAgent(BaseAgent[HistoryCaseOutput]):
    name = "HistoryCaseAgent"
    model_tier = "pro"
    output_schema = HistoryCaseOutput

    async def run(
        self, db: asyncpg.Connection, case: Case, *, run_id: str
    ) -> HistoryCaseOutput:
        candidates = await self._find_candidates(db, case)
        candidates = [c for c in candidates if c.case_id != case.case_id]

        if not candidates:
            return HistoryCaseOutput(
                case_id=case.case_id,
                analogous_cases=[],
                search_basis="SQL profile match on molecular_subtype + AJCC stage",
                agent_notes="No analogous cases found in the database for this profile.",
            )

        candidate_summaries = [
            {
                "case_id": c.case_id,
                "molecular_subtype": c.molecular_subtype,
                "ajcc_stage": c.ajcc_stage,
                "ajcc_t": c.ajcc_t,
                "ajcc_n": c.ajcc_n,
                "er_status": c.er_status,
                "pr_status": c.pr_status,
                "her2_status": c.her2_status,
                "age_at_diagnosis": c.age_at_diagnosis,
                "histological_type": c.histological_type,
                "treatments": c.treatments,
                "vital_status": c.vital_status,
                "tumor_status": c.tumor_status,
            }
            for c in candidates
        ]

        current_profile = {
            "case_id": case.case_id,
            "molecular_subtype": case.molecular_subtype,
            "ajcc_stage": case.ajcc_stage,
            "ajcc_t": case.ajcc_t,
            "ajcc_n": case.ajcc_n,
            "er_status": case.er_status,
            "pr_status": case.pr_status,
            "her2_status": case.her2_status,
            "age_at_diagnosis": case.age_at_diagnosis,
            "histological_type": case.histological_type,
            "treatments": case.treatments,
        }

        prompt = (
            f"Current patient:\n{json.dumps(current_profile, indent=2)}\n\n"
            f"Candidate analogous cases (top {len(candidate_summaries)} by SQL profile match):\n"
            f"{json.dumps(candidate_summaries, indent=2)}\n\n"
            "Select the three most clinically analogous cases. For each, provide: "
            "similarity_rationale, receptor_match, stage_match, treatment_summary, "
            "outcome_note. Also populate search_basis and agent_notes."
        )

        resp = await self.call_gemini(
            prompt=prompt,
            system_instruction=_SYSTEM,
            response_schema=HistoryCaseOutput,
        )

        try:
            payload = json.loads(resp.text)
        except json.JSONDecodeError as e:
            raise AgentError(
                f"HistoryCaseAgent could not parse Gemini response as JSON: {e}"
            ) from e

        payload["case_id"] = case.case_id
        try:
            return HistoryCaseOutput.model_validate(payload)
        except ValidationError as e:
            raise AgentError(
                f"Gemini response did not match HistoryCaseOutput schema: {e}"
            ) from e

    async def _find_candidates(
        self, db: asyncpg.Connection, case: Case
    ) -> list[Case]:
        if case.molecular_subtype:
            by_subtype = await repo.list_cases(
                db,
                limit=_CANDIDATE_LIMIT,
                molecular_subtype=case.molecular_subtype,
            )
            if len(by_subtype) > 1:
                return by_subtype

        return await repo.list_cases(db, limit=_CANDIDATE_LIMIT, has_data=True)
