"""FollowUpAgent — tracks open-action completion, surfaces overdue items.

Post-meeting, Gemini Flash. The overdue determination is deterministic
(due_date vs today over the actions table); Gemini only writes the
escalation narrative from those computed facts.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone

import asyncpg
from pydantic import BaseModel, ValidationError

from src.agents.session_base import SessionBaseAgent
from src.agents.types import AgentError
from src.db import repository as repo
from src.db.models import Case, Session

_SYSTEM = (
    "You are a tumor board follow-up coordinator. Given a factual breakdown of "
    "open, completed, and overdue action items, write a concise escalation note "
    "for the coordinators. State facts only; do not invent actions. "
    "Respond strictly as JSON matching the provided schema."
)

_OPEN_STATUSES = {"open", "in_progress"}


class _Escalation(BaseModel):
    escalation_notes: str


class OverdueAction(BaseModel):
    action_id: int
    description: str
    owner: str | None
    due_date: str | None
    days_overdue: int


class FollowUpOutput(BaseModel):
    session_id: str
    case_id: str
    total_actions: int
    open_actions: int
    completed_actions: int
    overdue_actions: list[OverdueAction]
    escalation_notes: str


def _days_overdue(due_date: str | None, today: date) -> int | None:
    if not due_date:
        return None
    try:
        d = date.fromisoformat(due_date[:10])
    except ValueError:
        return None
    delta = (today - d).days
    return delta if delta > 0 else None


class FollowUpAgent(SessionBaseAgent[FollowUpOutput]):
    name = "FollowUpAgent"
    model_tier = "flash"
    output_schema = FollowUpOutput

    async def run(
        self, db: asyncpg.Connection, session: Session, case: Case, *, run_id: str
    ) -> FollowUpOutput:
        actions = await repo.list_actions(db, session.session_id)
        today = datetime.now(timezone.utc).date()

        completed = sum(1 for a in actions if a.status == "completed")
        open_count = sum(1 for a in actions if a.status in _OPEN_STATUSES)

        overdue: list[OverdueAction] = []
        for a in actions:
            if a.status not in _OPEN_STATUSES:
                continue
            od = _days_overdue(a.due_date, today)
            if od is not None and a.action_id is not None:
                overdue.append(OverdueAction(
                    action_id=a.action_id,
                    description=a.description,
                    owner=a.owner,
                    due_date=a.due_date,
                    days_overdue=od,
                ))

        facts = {
            "total": len(actions),
            "open": open_count,
            "completed": completed,
            "overdue": [o.model_dump() for o in overdue],
        }
        prompt = (
            f"Case {case.case_id} follow-up status as of {today.isoformat()}:\n"
            f"{json.dumps(facts, indent=2)}\n\n"
            "Write an escalation_notes string: summarize follow-up health and, "
            "if any items are overdue, who needs to act and how urgently."
        )

        resp = await self.call_gemini(
            prompt=prompt,
            system_instruction=_SYSTEM,
            response_schema=_Escalation,  # only escalation_notes is model-authored
        )
        try:
            escalation = json.loads(resp.text).get("escalation_notes", "")
        except json.JSONDecodeError as e:
            raise AgentError(
                f"FollowUpAgent could not parse Gemini response as JSON: {e}"
            ) from e

        try:
            return FollowUpOutput(
                session_id=session.session_id,
                case_id=case.case_id,
                total_actions=len(actions),
                open_actions=open_count,
                completed_actions=completed,
                overdue_actions=overdue,
                escalation_notes=escalation or "No escalation required.",
            )
        except ValidationError as e:  # pragma: no cover - schema is constructed locally
            raise AgentError(f"FollowUpAgent output invalid: {e}") from e
