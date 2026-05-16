"""TranscriptionAgent + RecommendationAgent tests.

All tests use MockGeminiClient and an isolated in-memory DB — no API key,
no network calls, no audio hardware required.
"""
from __future__ import annotations

import json

import pytest

from src.agents.gemini_client import MockGeminiClient
from src.agents.RecommendationAgent import (
    DecisionMoment,
    RecommendationAgent,
    RecommendationOutput,
)
from src.agents.TranscriptionAgent import (
    TranscriptionAgent,
    TranscriptionOutput,
)
from src.agents.types import AgentError, SessionNotFoundError
from src.db import repository as repo
from src.db.models import Case, Session, Transcript

_NOW = "2026-05-16T00:00:00+00:00"


# ── Fixtures ──────────────────────────────────────────────────────────────────

async def _seed_case(db, case_id: str = "C1") -> None:
    await repo.upsert_case(
        db,
        Case(
            case_id=case_id,
            er_status="Positive",
            pr_status="Positive",
            her2_status="Negative",
            molecular_subtype="Luminal A",
            ajcc_stage="Stage IIA",
            ajcc_t="T2",
            ajcc_n="N0",
            ajcc_m="M0",
            age_at_diagnosis=52,
            created_at=_NOW,
            updated_at=_NOW,
        ),
    )


async def _seed_session(db, session_id: str = "S1", case_id: str = "C1") -> None:
    await repo.create_session(
        db,
        Session(
            session_id=session_id,
            case_id=case_id,
            started_at=_NOW,
            status="in_meeting",
        ),
    )


def _fixture_transcript_json() -> str:
    return json.dumps({
        "segments": [
            {"speaker": "Oncologist", "text": "Good morning. We are discussing case C1.", "timestamp_ms": 0},
            {"speaker": "Radiologist", "text": "Imaging shows a 2.3 cm mass, BI-RADS 5.", "timestamp_ms": 9000},
            {"speaker": "Pathologist", "text": "ER positive, Luminal A subtype confirmed.", "timestamp_ms": 18000},
            {"speaker": "Surgeon", "text": "Margins are clear, lumpectomy was successful.", "timestamp_ms": 27000},
            {"speaker": "Oncologist", "text": "Consensus: adjuvant endocrine therapy recommended.", "timestamp_ms": 36000},
        ]
    })


def _fixture_recommendation_json() -> str:
    return json.dumps({
        "decisions": [
            {
                "decision_type": "treatment",
                "summary": "Adjuvant endocrine therapy with tamoxifen or aromatase inhibitor.",
                "consensus_reached": True,
                "contributing_specialists": ["Oncologist", "Pathologist"],
                "evidence_cited": ["NCCN Breast Cancer v2.2024"],
                "caveats": ["Menopause status to be confirmed"],
            }
        ],
        "overall_treatment_direction": "Adjuvant endocrine therapy for ER+ Luminal A Stage IIA.",
        "unresolved_items": ["Confirm menopause status for aromatase inhibitor eligibility"],
        "next_steps": ["Order bone density scan", "Refer to genetics given age"],
    })


# ── Session lifecycle tests ───────────────────────────────────────────────────

async def test_transcription_agent_fixture_path(db):
    await _seed_case(db)
    await _seed_session(db)

    mock = MockGeminiClient()
    mock.queue(_fixture_transcript_json(), tokens_used=210)
    agent = TranscriptionAgent(gemini=mock)

    result = await agent.execute(db, "S1")

    assert isinstance(result, TranscriptionOutput)
    assert result.session_id == "S1"
    assert result.segment_count == 5
    assert "Oncologist" in result.speakers_detected
    assert "Radiologist" in result.speakers_detected

    # Segments saved to transcripts table
    saved = await repo.list_transcripts(db, "S1")
    assert len(saved) == 5
    assert saved[0].speaker == "Oncologist"
    assert saved[1].timestamp_ms == 9000

    # Agent output persisted
    row = await repo.get_latest_agent_output(db, "C1", "TranscriptionAgent")
    assert row is not None and row.status == "success"
    assert row.tokens_used == 210


async def test_transcription_agent_session_not_found(db):
    agent = TranscriptionAgent(gemini=MockGeminiClient())
    with pytest.raises(SessionNotFoundError):
        await agent.execute(db, "NO-SUCH-SESSION")


async def test_transcription_agent_empty_response_raises(db):
    await _seed_case(db)
    await _seed_session(db)

    mock = MockGeminiClient()
    mock.queue(json.dumps({"segments": []}), tokens_used=5)
    with pytest.raises(AgentError, match="empty transcript"):
        await TranscriptionAgent(gemini=mock).execute(db, "S1")


async def test_transcription_agent_invalid_json_raises(db):
    await _seed_case(db)
    await _seed_session(db)

    mock = MockGeminiClient()
    mock.queue("not json at all", tokens_used=5)
    with pytest.raises(AgentError, match="parse Gemini response"):
        await TranscriptionAgent(gemini=mock).execute(db, "S1")


# ── transcribe_audio() path ──────────────────────────────────────────────────

async def test_transcription_agent_audio_path(db):
    await _seed_case(db)
    await _seed_session(db)

    mock = MockGeminiClient()
    mock.queue(_fixture_transcript_json(), tokens_used=480)
    agent = TranscriptionAgent(gemini=mock)

    fake_audio = b"\x00\x01\x02" * 100   # dummy bytes — mock client ignores content
    result = await agent.transcribe_audio(db, "S1", fake_audio, mime_type="audio/wav")

    assert isinstance(result, TranscriptionOutput)
    assert result.segment_count == 5

    call = mock.calls[0]
    assert call["has_audio"] is True
    assert call["audio_mime_type"] == "audio/wav"
    assert call["model_tier"] == "flash"

    # Transcripts saved
    saved = await repo.list_transcripts(db, "S1")
    assert len(saved) == 5

    # Agent output persisted via direct path
    row = await repo.get_latest_agent_output(db, "C1", "TranscriptionAgent")
    assert row is not None and row.status == "success"


async def test_transcription_agent_audio_session_not_found(db):
    agent = TranscriptionAgent(gemini=MockGeminiClient())
    with pytest.raises(SessionNotFoundError):
        await agent.transcribe_audio(db, "GHOST", b"audio")


# ── RecommendationAgent ───────────────────────────────────────────────────────

async def _seed_transcripts(db, session_id: str = "S1") -> None:
    segments = [
        ("Oncologist", "We review the imaging and pathology for case C1.", 0),
        ("Radiologist", "BI-RADS 5 lesion, 2.3 cm, upper outer quadrant.", 9000),
        ("Pathologist", "ER positive 8/8, PR positive, HER2 negative. Luminal A.", 18000),
        ("Surgeon", "Clear margins achieved; lumpectomy complete.", 27000),
        ("Oncologist", "Board consensus: adjuvant endocrine therapy.", 36000),
    ]
    for speaker, text, ts in segments:
        await repo.add_transcript(
            db,
            Transcript(
                session_id=session_id,
                speaker=speaker,
                text=text,
                timestamp_ms=ts,
                created_at=_NOW,
            ),
        )


async def test_recommendation_agent_happy_path(db):
    await _seed_case(db)
    await _seed_session(db)
    await _seed_transcripts(db)

    mock = MockGeminiClient()
    mock.queue(_fixture_recommendation_json(), tokens_used=350)
    agent = RecommendationAgent(gemini=mock)

    result = await agent.execute(db, "S1")

    assert isinstance(result, RecommendationOutput)
    assert result.session_id == "S1"
    assert result.case_id == "C1"
    assert len(result.decisions) == 1
    assert result.decisions[0].consensus_reached is True
    assert result.decisions[0].decision_type == "treatment"
    assert result.recommendation_id is not None

    # Recommendation saved to recommendations table
    recs = await _get_recommendations(db, "S1")
    assert len(recs) == 1
    saved_content = recs[0]["content"]
    assert saved_content["case_id"] == "C1"

    # Agent output persisted
    row = await repo.get_latest_agent_output(db, "C1", "RecommendationAgent")
    assert row is not None and row.status == "success"
    assert row.tokens_used == 350


async def test_recommendation_agent_no_transcripts_raises(db):
    await _seed_case(db)
    await _seed_session(db)
    # No transcripts seeded

    with pytest.raises(AgentError, match="no transcripts"):
        await RecommendationAgent(gemini=MockGeminiClient()).execute(db, "S1")


async def test_recommendation_agent_invalid_json_raises(db):
    await _seed_case(db)
    await _seed_session(db)
    await _seed_transcripts(db)

    mock = MockGeminiClient()
    mock.queue("not valid json", tokens_used=5)
    with pytest.raises(AgentError, match="parse Gemini response"):
        await RecommendationAgent(gemini=mock).execute(db, "S1")


async def test_recommendation_agent_session_not_found(db):
    with pytest.raises(SessionNotFoundError):
        await RecommendationAgent(gemini=MockGeminiClient()).execute(db, "NO-SESSION")


async def test_recommendation_agent_reads_transcript_correctly(db):
    await _seed_case(db)
    await _seed_session(db)
    await _seed_transcripts(db)

    mock = MockGeminiClient()
    mock.queue(_fixture_recommendation_json(), tokens_used=100)
    await RecommendationAgent(gemini=mock).execute(db, "S1")

    # The prompt sent to Gemini should include transcript text
    call = mock.calls[0]
    assert "Oncologist" in call["prompt"]
    assert "BI-RADS 5" in call["prompt"]
    assert call["model_tier"] == "pro"


# ── End-to-end: Transcription → Recommendation ───────────────────────────────

async def test_transcription_then_recommendation_pipeline(db):
    await _seed_case(db)
    await _seed_session(db)

    mock = MockGeminiClient()
    mock.queue(_fixture_transcript_json(), tokens_used=200)
    mock.queue(_fixture_recommendation_json(), tokens_used=400)

    await TranscriptionAgent(gemini=mock).execute(db, "S1")
    result = await RecommendationAgent(gemini=mock).execute(db, "S1")

    assert isinstance(result, RecommendationOutput)
    assert len(result.decisions) >= 1
    assert result.recommendation_id is not None


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_recommendations(db, session_id: str) -> list[dict]:
    import json as _json
    cur = await db.execute(
        "SELECT content_json FROM recommendations WHERE session_id = ?",
        (session_id,),
    )
    rows = await cur.fetchall()
    return [{"content": _json.loads(r["content_json"])} for r in rows]
