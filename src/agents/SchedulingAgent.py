"""SchedulingAgent — flags cases needing re-presentation at a future board.

Post-meeting, Gemini Flash. Reads the session's action items and decides
whether the case should return to a future tumor board (e.g. pending
results, unresolved decisions) and on what timeframe.
"""
from __future__ import annotations

import json

import aiosqlite
from pydantic import BaseModel, ValidationError

from src.agents.session_base import SessionBaseAgent
from src.agents.types import AgentError
from src.db import repository as repo
from src.db.models import Case, Session

_SYSTEM = (
    "You are a tumor board scheduling coordinator. Given a case's open action "
    "items, decide whether the case needs to be re-presented at a future board "
    "and why. Surface the scheduling judgment only — no clinical recommendations. "
    "Respond strictly as JSON matching the provided schema."
)

_OPEN_STATUSES = {"open", "in_progress"}


class SchedulingOutput(BaseModel):
    session_id: str
    case_id: str
    needs_representation: bool
    suggested_timeframe: str | None
    rationale: str
    blocking_items: list[str]


class SchedulingAgent(SessionBaseAgent[SchedulingOutput]):
    name = "SchedulingAgent"
    model_tier = "flash"
    output_schema = SchedulingOutput

    async def run(
        self, db: aiosqlite.Connection, session: Session, case: Case, *, run_id: str
    ) -> SchedulingOutput:
        actions = await repo.list_actions(db, session.session_id)
        open_actions = [
            {"description": a.description, "owner": a.owner,
             "due_date": a.due_date, "status": a.status}
            for a in actions if a.status in _OPEN_STATUSES
        ]

        prompt = (
            f"Case: {case.case_id} ({case.molecular_subtype or 'Unknown'}, "
            f"{case.ajcc_stage or 'Unknown'})\n"
            f"Open action items ({len(open_actions)}):\n"
            f"{json.dumps(open_actions, indent=2)}\n\n"
            "Decide: does this case need re-presentation at a future tumor board? "
            "Provide needs_representation (bool), suggested_timeframe "
            "(e.g. '2 weeks' or null), rationale, and blocking_items."
        )

        resp = await self.call_gemini(
            prompt=prompt, system_instruction=_SYSTEM, response_schema=SchedulingOutput
        )

        try:
            payload = json.loads(resp.text)
        except json.JSONDecodeError as e:
            raise AgentError(
                f"SchedulingAgent could not parse Gemini response as JSON: {e}"
            ) from e

        payload["session_id"] = session.session_id
        payload["case_id"] = case.case_id
        try:
            return SchedulingOutput.model_validate(payload)
        except ValidationError as e:
            raise AgentError(
                f"Gemini response did not match SchedulingOutput schema: {e}"
            ) from e
