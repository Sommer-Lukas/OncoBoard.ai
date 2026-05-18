"""ActionDispatchAgent — parses decisions into owned, dated action items.

Post-meeting, Gemini Flash. Reads the confirmed RecommendationAgent output,
extracts discrete action items with owners and due dates, and writes each to
the `actions` table. Returns the persisted actions (with DB ids).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import asyncpg
from pydantic import BaseModel, ValidationError

from src.agents.session_base import SessionBaseAgent
from src.agents.types import AgentError
from src.db import repository as repo
from src.db.models import Action, Case, Session

_SYSTEM = (
    "You are a tumor board coordinator converting the board's confirmed "
    "decisions into a concrete action list. For each action specify a clear "
    "description, the responsible role/owner, and a due date (ISO YYYY-MM-DD) "
    "relative to the meeting date. Surface only actions the board agreed on. "
    "Respond strictly as JSON matching the provided schema."
)


class _PlannedAction(BaseModel):
    description: str
    owner: str
    due_date: str          # ISO date


class _ActionPlan(BaseModel):
    actions: list[_PlannedAction]
    dispatch_summary: str


class DispatchedAction(BaseModel):
    action_id: int
    description: str
    owner: str
    due_date: str
    status: str


class ActionDispatchOutput(BaseModel):
    session_id: str
    case_id: str
    actions_created: list[DispatchedAction]
    dispatch_summary: str


class ActionDispatchAgent(SessionBaseAgent[ActionDispatchOutput]):
    name = "ActionDispatchAgent"
    model_tier = "flash"
    output_schema = ActionDispatchOutput

    async def run(
        self, db: asyncpg.Connection, session: Session, case: Case, *, run_id: str
    ) -> ActionDispatchOutput:
        rec = await repo.get_latest_agent_output(db, case.case_id, "RecommendationAgent")
        if rec is None or rec.status != "success":
            raise AgentError(
                "ActionDispatchAgent requires a successful RecommendationAgent "
                "output; run the meeting recommendation step first"
            )

        today = datetime.now(timezone.utc).date().isoformat()
        prompt = (
            f"Meeting date: {today}\n"
            f"Case: {case.case_id} ({case.molecular_subtype or 'Unknown'}, "
            f"{case.ajcc_stage or 'Unknown'})\n\n"
            "Confirmed board recommendation:\n"
            f"{json.dumps(rec.output, indent=2)}\n\n"
            "Extract the discrete follow-up actions. For each: description, owner "
            "(clinical role), and due_date (ISO YYYY-MM-DD on or after the meeting "
            "date). Also give a one-line dispatch_summary."
        )

        resp = await self.call_gemini(
            prompt=prompt, system_instruction=_SYSTEM, response_schema=_ActionPlan
        )

        try:
            plan = _ActionPlan.model_validate(json.loads(resp.text))
        except (json.JSONDecodeError, ValidationError) as e:
            raise AgentError(
                f"ActionDispatchAgent could not parse a valid action plan: {e}"
            ) from e

        now = datetime.now(timezone.utc).isoformat()
        created: list[DispatchedAction] = []
        for a in plan.actions:
            action_id = await repo.add_action(
                db,
                Action(
                    session_id=session.session_id,
                    description=a.description,
                    owner=a.owner,
                    due_date=a.due_date,
                    status="open",
                    created_at=now,
                ),
            )
            created.append(DispatchedAction(
                action_id=action_id,
                description=a.description,
                owner=a.owner,
                due_date=a.due_date,
                status="open",
            ))

        return ActionDispatchOutput(
            session_id=session.session_id,
            case_id=case.case_id,
            actions_created=created,
            dispatch_summary=plan.dispatch_summary,
        )
