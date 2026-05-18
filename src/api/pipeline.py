"""SSE route that runs the pre-meeting pipeline and streams progress.

Server-Sent Events per ARCHITECTURE.md — agent output is strictly
server -> client, so SSE over WebSocket.
"""
import json
from typing import Annotated, AsyncIterator

import asyncpg
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from src.agents.pipeline import run_pre_meeting
from src.db import repository
from src.db.connection import connect, get_db

router = APIRouter(prefix="/cases", tags=["pipeline"])

_Db = Annotated[asyncpg.Connection, Depends(get_db)]


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.post("/{case_id}/pre-meeting/run")
async def run_pre_meeting_pipeline(case_id: str, db: _Db) -> StreamingResponse:
    """Trigger CaseCompiler -> SummaryAgent, streaming one SSE event per step.

    The 404 check uses the request-scoped connection. The stream itself opens
    its own connection so it stays valid for the full duration of the response
    (the request-scoped one is torn down once the handler returns).
    """
    if not await repository.get_case(db, case_id):
        raise HTTPException(status_code=404, detail="Case not found")

    async def event_stream() -> AsyncIterator[str]:
        async with connect() as stream_db:
            async for ev in run_pre_meeting(stream_db, case_id):
                yield _sse(ev.event, ev.to_dict())

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
