"""NoteDraftAgent — drafts the tumor board note from transcript + decisions.

Post-meeting, Gemini Pro. Consumes the session transcript and the confirmed
RecommendationAgent output, produces a structured note ready for EHR entry.
Surfaces information only — the note records what the board decided.
"""
from __future__ import annotations

import json

import asyncpg
from pydantic import BaseModel, ValidationError

from src.agents.session_base import SessionBaseAgent
from src.agents.types import AgentError
from src.db import repository as repo
from src.db.models import Case, Session

_SYSTEM = (
    "You are a tumor board coordinator drafting the official multidisciplinary "
    "tumor board note for a breast cancer case. Write in clinical documentation "
    "style suitable for EHR entry. Record only what the board discussed and "
    "decided — do not introduce new clinical judgment. "
    "Respond strictly as JSON matching the provided schema."
)


class TumorBoardNote(BaseModel):
    session_id: str
    case_id: str
    clinical_summary: str
    imaging_summary: str
    pathology_summary: str
    board_discussion: str
    consensus_plan: str
    drafted_note: str          # full formatted note, ready to copy into the EHR
    data_gaps: list[str]


class NoteDraftAgent(SessionBaseAgent[TumorBoardNote]):
    name = "NoteDraftAgent"
    model_tier = "pro"
    output_schema = TumorBoardNote

    async def run(
        self, db: asyncpg.Connection, session: Session, case: Case, *, run_id: str
    ) -> TumorBoardNote:
        rec = await repo.get_latest_agent_output(db, case.case_id, "RecommendationAgent")
        if rec is None or rec.status != "success":
            raise AgentError(
                "NoteDraftAgent requires a successful RecommendationAgent output; "
                "run the meeting recommendation step before post-meeting"
            )

        transcripts = await repo.list_transcripts(db, session.session_id)
        transcript_text = "\n".join(
            f"[{t.timestamp_ms // 1000:>5}s] {t.speaker or 'Unknown'}: {t.text}"
            for t in transcripts
        ) or "(no transcript captured)"

        prompt = (
            "Case context:\n"
            f"  Case ID: {case.case_id}\n"
            f"  Age: {case.age_at_diagnosis or 'Unknown'}\n"
            f"  AJCC stage: {case.ajcc_stage or 'Unknown'}\n"
            f"  ER/PR/HER2: {case.er_status or '?'}/{case.pr_status or '?'}/"
            f"{case.her2_status or '?'}\n"
            f"  Molecular subtype: {case.molecular_subtype or 'Unknown'}\n"
            f"  Histology: {case.histological_type or 'Unknown'}\n\n"
            "Confirmed board recommendation (from RecommendationAgent):\n"
            f"{json.dumps(rec.output, indent=2)}\n\n"
            "Meeting transcript:\n"
            f"{transcript_text}\n\n"
            "Draft the tumor board note. Provide clinical_summary, imaging_summary, "
            "pathology_summary, board_discussion, consensus_plan, a fully formatted "
            "drafted_note for EHR entry, and any data_gaps."
        )

        resp = await self.call_gemini(
            prompt=prompt, system_instruction=_SYSTEM, response_schema=TumorBoardNote
        )

        try:
            payload = json.loads(resp.text)
        except json.JSONDecodeError as e:
            raise AgentError(
                f"NoteDraftAgent could not parse Gemini response as JSON: {e}"
            ) from e

        payload["session_id"] = session.session_id
        payload["case_id"] = case.case_id
        try:
            return TumorBoardNote.model_validate(payload)
        except ValidationError as e:
            raise AgentError(
                f"Gemini response did not match TumorBoardNote schema: {e}"
            ) from e
