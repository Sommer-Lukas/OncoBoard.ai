"""Meeting room API routes.

Three stages:
  POST /cases/{case_id}/sessions                   — create a session
  POST /sessions/{session_id}/transcribe/stream    — run TranscriptionAgent, SSE stream
  POST /sessions/{session_id}/recommend            — run RecommendationAgent, return JSON
  PATCH /sessions/{session_id}/status              — update session status (end meeting)
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Annotated, AsyncIterator

import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.agents.RecommendationAgent import RecommendationAgent
from src.agents.TranscriptionAgent import TranscriptionAgent
from src.db import repository as repo
from src.db.connection import connect, get_db
from src.db.models import Session

router = APIRouter(tags=["meeting"])

_Db = Annotated[aiosqlite.Connection, Depends(get_db)]


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.post("/cases/{case_id}/sessions")
async def create_meeting_session(case_id: str, db: _Db) -> dict:
    """Create a new in-meeting session for a case."""
    case = await repo.get_case(db, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    session_id = str(uuid.uuid4())
    started_at = _now()
    await repo.create_session(
        db,
        Session(
            session_id=session_id,
            case_id=case_id,
            started_at=started_at,
            status="in_meeting",
        ),
    )
    return {"session_id": session_id, "case_id": case_id, "status": "in_meeting", "started_at": started_at}


@router.post("/sessions/{session_id}/transcribe/stream")
async def stream_transcription(session_id: str, db: _Db) -> StreamingResponse:
    """Run TranscriptionAgent and stream each transcript segment back via SSE.

    The agent generates a fixture transcript for the session's case and saves
    all segments to the DB. Segments are then streamed back one by one with
    ~1.2s delays to simulate a live meeting feed on the frontend.
    """
    session = await repo.get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    async def event_stream() -> AsyncIterator[str]:
        async with connect() as stream_db:
            agent = TranscriptionAgent()
            try:
                output = await agent.execute(stream_db, session_id)
            except Exception as e:
                yield _sse("error", {"message": str(e)})
                return

            segments = await repo.list_transcripts(stream_db, session_id)
            yield _sse("start", {"segment_count": len(segments)})

            for i, seg in enumerate(segments):
                await asyncio.sleep(0.3 if i == 0 else 1.1)
                yield _sse("transcript_line", {
                    "speaker": seg.speaker or "Unknown",
                    "text": seg.text,
                    "timestamp_ms": seg.timestamp_ms,
                })

            yield _sse("complete", output.model_dump())

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/sessions/{session_id}/transcribe/audio")
async def transcribe_audio_upload(
    session_id: str,
    db: _Db,
    file: UploadFile = File(...),
) -> dict:
    """Transcribe a real audio recording via Gemini's audio understanding API.

    Accepts a multipart audio file (webm, wav, ogg, mp4). Passes the bytes
    inline to Gemini Flash for speaker-tagged transcription, saves segments to
    the DB, and returns the transcript output plus the raw segments so the
    frontend can render them immediately.
    """
    session = await repo.get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    audio_bytes = await file.read()
    mime_type = file.content_type or "audio/webm"

    async with connect() as agent_db:
        agent = TranscriptionAgent()
        output = await agent.transcribe_audio(agent_db, session_id, audio_bytes, mime_type=mime_type)
        segments = await repo.list_transcripts(agent_db, session_id)

    return {
        **output.model_dump(),
        "segments": [
            {"speaker": s.speaker, "text": s.text, "timestamp_ms": s.timestamp_ms}
            for s in segments
        ],
    }


@router.post("/sessions/{session_id}/recommend")
async def run_recommendation_agent(session_id: str, db: _Db) -> dict:
    """Run RecommendationAgent on the session transcript. Returns structured decisions."""
    session = await repo.get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    async with connect() as agent_db:
        agent = RecommendationAgent()
        output = await agent.execute(agent_db, session_id)

    return output.model_dump()


class _StatusUpdate(BaseModel):
    status: str


@router.patch("/sessions/{session_id}/status")
async def update_session_status_route(
    session_id: str, body: _StatusUpdate, db: _Db
) -> dict:
    """Update session lifecycle status (e.g., 'post_meeting' when board ends)."""
    session = await repo.get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    await repo.update_session_status(db, session_id, body.status)
    return {"session_id": session_id, "status": body.status}
