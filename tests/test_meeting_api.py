"""src/api/meeting.py route coverage — previously untested surface.

Drives TranscriptionAgent / RecommendationAgent through the Gemini
singleton mock (the routes instantiate the agents without an explicit
client, same pattern as the SSE pipeline route).
"""
import json

from src.agents.gemini_client import get_gemini_client
from src.db import repository as repo
from src.db.connection import connect
from src.db.models import Transcript

_NOW = "2026-05-17T00:00:00+00:00"

# Short transcript so the SSE test (1.1s/segment server-side pacing) stays fast.
_SEGMENTS = json.dumps({
    "segments": [
        {"speaker": "Oncologist", "text": "Stage IIA, ER+/PR+/HER2-.", "timestamp_ms": 0},
        {"speaker": "Surgeon", "text": "Lumpectomy with clear margins.", "timestamp_ms": 9000},
    ]
})

_RECOMMENDATION = json.dumps({
    "decisions": [
        {
            "decision_type": "treatment",
            "summary": "Adjuvant endocrine therapy agreed.",
            "consensus_reached": True,
            "contributing_specialists": ["Oncologist", "Surgeon"],
            "evidence_cited": ["NCCN Breast v2.2025"],
            "caveats": [],
        }
    ],
    "overall_treatment_direction": "Breast-conserving surgery + adjuvant endocrine therapy.",
    "unresolved_items": ["Genomic recurrence assay pending"],
    "next_steps": ["Order Oncotype DX", "Schedule RT consult"],
})


async def _create_session(client, case_id="SYN-001") -> str:
    r = await client.post(f"/cases/{case_id}/sessions")
    assert r.status_code == 200, r.text
    return r.json()["session_id"]


# ── session creation ─────────────────────────────────────────────────────────

async def test_create_session_ok_and_persisted(client):
    r = await client.post("/cases/SYN-001/sessions")
    assert r.status_code == 200
    body = r.json()
    assert body["case_id"] == "SYN-001"
    assert body["status"] == "in_meeting"
    sid = body["session_id"]

    async with connect() as db:
        sess = await repo.get_session(db, sid)
    assert sess is not None and sess.case_id == "SYN-001"


async def test_create_session_404_for_missing_case(client):
    r = await client.post("/cases/GHOST/sessions")
    assert r.status_code == 404


# ── transcription SSE stream ─────────────────────────────────────────────────

async def test_transcribe_stream_emits_segments(client):
    sid = await _create_session(client)
    get_gemini_client().queue(_SEGMENTS, tokens_used=120)

    events: list[str] = []
    async with client.stream("POST", f"/sessions/{sid}/transcribe/stream") as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        async for line in resp.aiter_lines():
            if line.startswith("event: "):
                events.append(line.removeprefix("event: ").strip())

    assert events[0] == "start"
    assert events.count("transcript_line") == 2
    assert events[-1] == "complete"

    async with connect() as db:
        segs = await repo.list_transcripts(db, sid)
    assert [s.speaker for s in segs] == ["Oncologist", "Surgeon"]


async def test_transcribe_stream_404_missing_session(client):
    r = await client.post("/sessions/no-such-session/transcribe/stream")
    assert r.status_code == 404


# ── audio upload ─────────────────────────────────────────────────────────────

async def test_transcribe_audio_upload(client):
    sid = await _create_session(client, "SYN-002")
    get_gemini_client().queue(_SEGMENTS, tokens_used=88)

    r = await client.post(
        f"/sessions/{sid}/transcribe/audio",
        files={"file": ("clip.webm", b"\x00\x01fake-audio-bytes", "audio/webm")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["session_id"] == sid
    assert body["segment_count"] == 2
    assert len(body["segments"]) == 2
    assert body["segments"][0]["speaker"] == "Oncologist"


async def test_transcribe_audio_404_missing_session(client):
    r = await client.post(
        "/sessions/nope/transcribe/audio",
        files={"file": ("c.webm", b"x", "audio/webm")},
    )
    assert r.status_code == 404


# ── recommendation ───────────────────────────────────────────────────────────

async def test_recommend_returns_decisions_and_persists(client):
    sid = await _create_session(client, "SYN-003")
    # Seed transcripts directly so RecommendationAgent has input.
    async with connect() as db:
        for ts, (spk, txt) in enumerate(
            [("Oncologist", "TNBC, consider chemo."), ("Pathologist", "Grade 3.")]
        ):
            await repo.add_transcript(db, Transcript(
                session_id=sid, speaker=spk, text=txt,
                timestamp_ms=ts * 9000, created_at=_NOW,
            ))
    get_gemini_client().queue(_RECOMMENDATION, tokens_used=400)

    r = await client.post(f"/sessions/{sid}/recommend")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["case_id"] == "SYN-003"
    assert body["decisions"][0]["decision_type"] == "treatment"
    assert body["overall_treatment_direction"]
    # A returned recommendation_id implies the row was persisted.
    assert isinstance(body["recommendation_id"], int) and body["recommendation_id"] >= 1


async def test_recommend_404_missing_session(client):
    r = await client.post("/sessions/ghost/recommend")
    assert r.status_code == 404


# ── status patch ─────────────────────────────────────────────────────────────

async def test_patch_session_status(client):
    sid = await _create_session(client)
    r = await client.patch(f"/sessions/{sid}/status", json={"status": "post_meeting"})
    assert r.status_code == 200
    assert r.json()["status"] == "post_meeting"

    async with connect() as db:
        sess = await repo.get_session(db, sid)
    assert sess.status == "post_meeting"


async def test_patch_session_status_404(client):
    r = await client.patch("/sessions/ghost/status", json={"status": "post_meeting"})
    assert r.status_code == 404
