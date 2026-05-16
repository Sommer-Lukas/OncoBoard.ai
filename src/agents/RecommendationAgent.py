"""RecommendationAgent — identifies decision moments in the transcript stream.

Reads all transcript segments for the session from the DB and uses Gemini Pro
to identify clinical decision moments — points where the multidisciplinary team
is reaching or has reached consensus on a specific clinical question (treatment
approach, staging confirmation, workup order, clinical trial enrollment, etc.).

The agent captures the *emerging consensus* as the meeting progresses. It does
not make recommendations itself — it surfaces what the board is deciding.
Downstream agents (NoteDraftAgent, ActionDispatchAgent) consume this output.

The structured recommendation is persisted to the `recommendations` table and
also to `agent_outputs` via the SessionBaseAgent lifecycle.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import aiosqlite
from pydantic import BaseModel, ValidationError

from src.agents.session_base import SessionBaseAgent
from src.agents.types import AgentError
from src.db import repository as repo
from src.db.models import Case, Recommendation, Session

_SYSTEM = (
    "You are an oncology decision analyst attending a multidisciplinary tumor board. "
    "Read the meeting transcript and identify all clinical decision moments — points "
    "where the team is reaching or has reached consensus on a clinical question. "
    "For each decision moment, record: the type of decision, a concise summary, "
    "whether consensus was reached, which specialists contributed, any evidence or "
    "guidelines cited, and any caveats raised. "
    "Also capture the overall treatment direction the board is heading toward, "
    "unresolved items that need follow-up, and concrete next steps. "
    "Surface what the board decided — do not add your own clinical judgment. "
    "Respond strictly as JSON matching the provided schema."
)

_DECISION_TYPES = (
    "treatment | staging | workup | follow_up | clinical_trial | "
    "pathology_review | imaging_review | other"
)


class DecisionMoment(BaseModel):
    decision_type: str        # one of _DECISION_TYPES
    summary: str              # one-sentence description of the decision
    consensus_reached: bool
    contributing_specialists: list[str]
    evidence_cited: list[str]
    caveats: list[str]


class _RecommendationPayload(BaseModel):
    decisions: list[DecisionMoment]
    overall_treatment_direction: str
    unresolved_items: list[str]
    next_steps: list[str]


class RecommendationOutput(BaseModel):
    session_id: str
    case_id: str
    decisions: list[DecisionMoment]
    overall_treatment_direction: str
    unresolved_items: list[str]
    next_steps: list[str]
    recommendation_id: int | None = None   # set after DB persist


class RecommendationAgent(SessionBaseAgent[RecommendationOutput]):
    """Extracts clinical decision moments from the session transcript."""

    name = "RecommendationAgent"
    model_tier = "pro"
    output_schema = RecommendationOutput

    async def run(
        self, db: aiosqlite.Connection, session: Session, case: Case, *, run_id: str
    ) -> RecommendationOutput:
        transcripts = await repo.list_transcripts(db, session.session_id)
        if not transcripts:
            raise AgentError(
                f"RecommendationAgent: no transcripts found for session "
                f"{session.session_id} — run TranscriptionAgent first"
            )

        lines = "\n".join(
            f"[{t.timestamp_ms // 1000:>5}s] {t.speaker or 'Unknown'}: {t.text}"
            for t in transcripts
        )

        prompt = (
            "Tumor board meeting transcript:\n\n"
            f"{lines}\n\n"
            "Case context:\n"
            f"  Case ID: {case.case_id}\n"
            f"  AJCC stage: {case.ajcc_stage or 'Unknown'}\n"
            f"  ER: {case.er_status or 'Unknown'}  "
            f"PR: {case.pr_status or 'Unknown'}  "
            f"HER2: {case.her2_status or 'Unknown'}\n"
            f"  Molecular subtype: {case.molecular_subtype or 'Unknown'}\n\n"
            "Identify all clinical decision moments in this transcript. "
            f"Decision types: {_DECISION_TYPES}. "
            "Capture the overall treatment direction, any unresolved items, "
            "and the concrete next steps the board agreed on."
        )

        resp = await self.call_gemini(
            prompt=prompt,
            system_instruction=_SYSTEM,
            response_schema=_RecommendationPayload,
        )

        try:
            payload = json.loads(resp.text)
        except json.JSONDecodeError as e:
            raise AgentError(
                f"RecommendationAgent could not parse Gemini response as JSON: {e}"
            ) from e

        try:
            rec_payload = _RecommendationPayload.model_validate(payload)
        except ValidationError as e:
            raise AgentError(
                f"Gemini response did not match RecommendationPayload schema: {e}"
            ) from e

        rec_content = rec_payload.model_dump()
        rec_content["case_id"] = case.case_id

        rec_id = await repo.save_recommendation(
            db,
            Recommendation(
                session_id=session.session_id,
                content=rec_content,
                created_at=datetime.now(timezone.utc).isoformat(),
            ),
        )

        return RecommendationOutput(
            session_id=session.session_id,
            case_id=case.case_id,
            decisions=rec_payload.decisions,
            overall_treatment_direction=rec_payload.overall_treatment_direction,
            unresolved_items=rec_payload.unresolved_items,
            next_steps=rec_payload.next_steps,
            recommendation_id=rec_id,
        )
