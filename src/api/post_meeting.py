"""Post-meeting API routes + the surrounding human gates.

  POST /sessions/{id}/gate2/confirm      — Human Gate 2 (consensus confirmed)
  POST /sessions/{id}/post-meeting/run   — post-meeting pipeline, SSE stream
  POST /sessions/{id}/gate3/approve      — Human Gate 3 (note approved)

ARCHITECTURE.md §2: post-meeting agents must not run before Human Gate 2.
The run endpoint enforces that hard stop (409 if Gate 2 is not recorded).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Annotated, AsyncIterator

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.agents.post_meeting_pipeline import run_post_meeting
from src.db import repository as repo
from src.db.connection import connect, get_db
from src.db.models import Gate

router = APIRouter(tags=["post-meeting"])

_Db = Annotated[asyncpg.Connection, Depends(get_db)]

_GATE2 = "consensus_confirmed"
_GATE3 = "note_approved"


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class _GateBody(BaseModel):
    approved_by: str
    notes: str | None = None


async def _require_session(db: asyncpg.Connection, session_id: str):
    session = await repo.get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/sessions/{session_id}/gate2/confirm")
async def confirm_consensus_gate(
    session_id: str, body: _GateBody, db: _Db
) -> dict:
    """Human Gate 2 — record that the board confirmed consensus. Unlocks post-meeting."""
    await _require_session(db, session_id)
    gate_id = await repo.record_gate(db, Gate(
        session_id=session_id, gate_name=_GATE2,
        approved_by=body.approved_by, approved_at=_now(), notes=body.notes,
    ))
    return {"session_id": session_id, "gate": _GATE2, "gate_id": gate_id}


@router.post("/sessions/{session_id}/post-meeting/run")
async def run_post_meeting_pipeline(session_id: str, db: _Db) -> StreamingResponse:
    """Run NoteDraft/ActionDispatch then FollowUp/Scheduling, streaming SSE.

    Hard stop: refuses to run until Human Gate 2 is recorded for the session.
    """
    await _require_session(db, session_id)

    gates = await repo.list_gates(db, session_id)
    if not any(g.gate_name == _GATE2 for g in gates):
        raise HTTPException(
            status_code=409,
            detail="Human Gate 2 (consensus_confirmed) not recorded — "
                   "confirm consensus before running the post-meeting pipeline",
        )

    async def event_stream() -> AsyncIterator[str]:
        async with connect() as stream_db:
            async for ev in run_post_meeting(stream_db, session_id):
                yield _sse(ev.event, ev.to_dict())

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/sessions/{session_id}/gate3/approve")
async def approve_note_gate(
    session_id: str, body: _GateBody, db: _Db
) -> dict:
    """Human Gate 3 — record clinician approval of the drafted tumor board note."""
    await _require_session(db, session_id)
    gate_id = await repo.record_gate(db, Gate(
        session_id=session_id, gate_name=_GATE3,
        approved_by=body.approved_by, approved_at=_now(), notes=body.notes,
    ))
    return {"session_id": session_id, "gate": _GATE3, "gate_id": gate_id}
