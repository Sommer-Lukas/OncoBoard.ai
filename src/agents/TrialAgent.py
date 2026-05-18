"""TrialAgent — clinical trial eligibility matching + evidence retrieval.

Calls ClinicalTrials.gov (v2 API) for recruiting breast cancer trials, then
PubMed E-utilities for supporting literature, and uses Gemini Flash to assess
eligibility delta for the patient. Returns structured trial matches.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import asyncpg
import httpx
from pydantic import BaseModel, ValidationError

from src.agents.base import BaseAgent
from src.agents.types import AgentError
from src.config import get_settings
from src.db.models import Case

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are an oncology clinical research coordinator reviewing recruiting trials "
    "for a breast cancer patient at a tumor board. For each trial, assess eligibility "
    "based on the patient profile and summarize the key eligibility delta "
    "(what criteria the patient meets and what may exclude them). "
    "Surface information only — do not recommend enrollment. "
    "Respond strictly as JSON matching the provided schema."
)

_CT_PAGE_SIZE = 10
_PUBMED_MAX = 5

# ClinicalTrials.gov / NCBI edge layers 403 clients with the default
# python-httpx UA. Send a descriptive identifier so requests aren't blocked.
_HTTP_HEADERS = {
    "User-Agent": "OncoBoard.ai/0.1 (breast cancer tumor board research prototype)",
    "Accept": "application/json",
}


class TrialMatch(BaseModel):
    nct_id: str
    title: str
    phase: str | None
    overall_status: str
    eligibility_delta: str
    brief_summary: str | None = None


class PubMedReference(BaseModel):
    pmid: str
    title: str | None = None
    source: str | None = None


class TrialOutput(BaseModel):
    case_id: str
    search_criteria: dict[str, Any]
    trials_retrieved: int
    matched_trials: list[TrialMatch]
    pubmed_references: list[PubMedReference]
    agent_notes: str


class TrialAgent(BaseAgent[TrialOutput]):
    name = "TrialAgent"
    model_tier = "flash"
    output_schema = TrialOutput

    async def run(
        self, db: asyncpg.Connection, case: Case, *, run_id: str
    ) -> TrialOutput:
        settings = get_settings()
        search_criteria: dict[str, Any] = {
            "er_status": case.er_status,
            "pr_status": case.pr_status,
            "her2_status": case.her2_status,
            "molecular_subtype": case.molecular_subtype,
            "ajcc_stage": case.ajcc_stage,
            "age": case.age_at_diagnosis,
        }

        async with httpx.AsyncClient(timeout=15.0, headers=_HTTP_HEADERS) as client:
            trials_data, pubmed_ids = await asyncio.gather(
                self._fetch_trials(client, settings.clinicaltrials_base_url, case),
                self._search_pubmed(client, settings.pubmed_base_url, case),
            )
            pubmed_refs = await self._fetch_pubmed_summaries(client, settings.pubmed_base_url, pubmed_ids)

        trial_summaries = self._extract_trial_summaries(trials_data)
        prompt = self._build_prompt(case, trial_summaries)

        resp = await self.call_gemini(
            prompt=prompt,
            system_instruction=_SYSTEM,
            response_schema=TrialOutput,
        )

        try:
            payload = json.loads(resp.text)
        except json.JSONDecodeError as e:
            raise AgentError(
                f"TrialAgent could not parse Gemini response as JSON: {e}"
            ) from e

        payload["case_id"] = case.case_id
        payload["search_criteria"] = search_criteria
        payload["trials_retrieved"] = len(trial_summaries)
        if not payload.get("pubmed_references"):
            payload["pubmed_references"] = pubmed_refs
        try:
            return TrialOutput.model_validate(payload)
        except ValidationError as e:
            raise AgentError(
                f"Gemini response did not match TrialOutput schema: {e}"
            ) from e

    async def _fetch_trials(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        case: Case,
    ) -> list[dict[str, Any]]:
        query_terms = ["breast cancer"]
        her2_pos = case.her2_status and "positive" in case.her2_status.lower()
        er_pos = case.er_status and "positive" in case.er_status.lower()
        tnbc = (
            case.her2_status and "negative" in case.her2_status.lower()
            and case.er_status and "negative" in case.er_status.lower()
            and case.pr_status and "negative" in case.pr_status.lower()
        )
        if her2_pos:
            query_terms.append("HER2 positive")
        elif tnbc:
            query_terms.append("triple negative")
        elif er_pos:
            query_terms.append("hormone receptor positive")

        try:
            resp = await client.get(
                f"{base_url}/studies",
                params={
                    "query.cond": " ".join(query_terms),
                    "filter.overallStatus": "RECRUITING",
                    "pageSize": str(_CT_PAGE_SIZE),
                    # No `fields` filter: v2 rejects/empties legacy v1 field
                    # names. The full study record is returned by default and
                    # _extract_trial_summaries only reads the modules it needs.
                    "format": "json",
                },
            )
            resp.raise_for_status()
            return resp.json().get("studies", [])
        except httpx.HTTPError as e:
            logger.warning(
                "clinicaltrials_fetch_failed",
                extra={"extra_fields": {"error": str(e)}},
            )
            return []

    async def _search_pubmed(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        case: Case,
    ) -> list[str]:
        terms = ["breast cancer", "randomized trial"]
        if case.molecular_subtype:
            terms.append(f'"{case.molecular_subtype}"')
        if case.ajcc_stage:
            terms.append(f'"{case.ajcc_stage}"')

        try:
            resp = await client.get(
                f"{base_url}/esearch.fcgi",
                params={
                    "db": "pubmed",
                    "term": " AND ".join(terms),
                    "retmax": str(_PUBMED_MAX),
                    "retmode": "json",
                },
            )
            resp.raise_for_status()
            return resp.json().get("esearchresult", {}).get("idlist", [])
        except httpx.HTTPError as e:
            logger.warning(
                "pubmed_search_failed",
                extra={"extra_fields": {"error": str(e)}},
            )
            return []

    async def _fetch_pubmed_summaries(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        pmids: list[str],
    ) -> list[dict[str, Any]]:
        if not pmids:
            return []
        try:
            resp = await client.get(
                f"{base_url}/esummary.fcgi",
                params={"db": "pubmed", "id": ",".join(pmids), "retmode": "json"},
            )
            resp.raise_for_status()
            result_map = resp.json().get("result", {})
            return [
                {
                    "pmid": pmid,
                    "title": result_map.get(pmid, {}).get("title"),
                    "source": result_map.get(pmid, {}).get("source"),
                }
                for pmid in pmids
            ]
        except httpx.HTTPError as e:
            logger.warning(
                "pubmed_summary_failed",
                extra={"extra_fields": {"error": str(e)}},
            )
            return [{"pmid": p, "title": None, "source": None} for p in pmids]

    def _extract_trial_summaries(
        self, studies: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        out = []
        for study in studies:
            proto = study.get("protocolSection", {})
            id_mod = proto.get("identificationModule", {})
            status_mod = proto.get("statusModule", {})
            design_mod = proto.get("designModule", {})
            elig_mod = proto.get("eligibilityModule", {})
            desc_mod = proto.get("descriptionModule", {})
            phases = design_mod.get("phases", [])
            out.append({
                "nct_id": id_mod.get("nctId", ""),
                "title": id_mod.get("briefTitle", ""),
                "phase": phases[0] if phases else None,
                "overall_status": status_mod.get("overallStatus", ""),
                "eligibility_criteria": (elig_mod.get("eligibilityCriteria") or "")[:1200],
                "brief_summary": (desc_mod.get("briefSummary") or "")[:500],
            })
        return out

    def _build_prompt(self, case: Case, trials: list[dict[str, Any]]) -> str:
        patient = (
            f"Age: {case.age_at_diagnosis or 'unknown'}, "
            f"Stage: {case.ajcc_stage or 'unknown'}, "
            f"ER: {case.er_status or 'unknown'}, "
            f"PR: {case.pr_status or 'unknown'}, "
            f"HER2: {case.her2_status or 'unknown'}, "
            f"Subtype: {case.molecular_subtype or 'unknown'}, "
            f"Histology: {case.histological_type or 'unknown'}."
        )
        if not trials:
            return (
                f"Patient: {patient}\n\n"
                "No trials were retrieved from ClinicalTrials.gov. "
                "Return an empty matched_trials list and note the retrieval failure in agent_notes."
            )
        return (
            f"Patient: {patient}\n\n"
            f"Recruiting trials retrieved ({len(trials)}):\n"
            f"{json.dumps(trials, indent=2)}\n\n"
            "For each trial assess eligibility and describe the key eligibility delta. "
            "Return matched_trials and agent_notes summarising the search."
        )
