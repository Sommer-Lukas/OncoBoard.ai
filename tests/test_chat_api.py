"""ClinicalContextAgent (RAG) + /cases/{id}/chat coverage."""
import pytest

from src.agents.ClinicalContextAgent import ClinicalContextAgent
from src.agents.gemini_client import MockGeminiClient, get_gemini_client
from src.db import repository as repo
from src.db.connection import connect
from src.db.models import Action, AgentOutput, Case, Session, Transcript

_NOW = "2026-05-18T00:00:00+00:00"


async def _seed_case(db, case_id="SYN-001") -> None:
    await repo.upsert_case(db, Case(
        case_id=case_id, age_at_diagnosis=52, er_status="Positive",
        pr_status="Positive", her2_status="Negative",
        molecular_subtype="Luminal A", ajcc_stage="Stage IIA",
        created_at=_NOW, updated_at=_NOW,
    ))
    await repo.save_agent_output(db, AgentOutput(
        case_id=case_id, agent_name="SummaryAgent", run_id="r0",
        output={"narrative": "Stage IIA Luminal A IDC."},
        status="success", created_at=_NOW,
    ))


# ── agent: working "pre" phase ───────────────────────────────────────────────

async def test_chat_pre_phase_builds_context_and_replies(db):
    await _seed_case(db)
    mock = MockGeminiClient()
    mock.queue("ER is positive per the patient record.", tokens_used=120)
    agent = ClinicalContextAgent(gemini=mock)

    reply = await agent.chat(
        db, "SYN-001",
        [{"role": "user", "content": "What is the ER status?"}],
        phase="pre",
    )
    assert reply == "ER is positive per the patient record."

    prompt = mock.calls[0]["prompt"]
    assert "PATIENT RECORD" in prompt
    assert "SYN-001" in prompt
    assert "AGENT OUTPUT — SummaryAgent" in prompt
    assert "What is the ER status?" in prompt
    assert mock.calls[0]["model_tier"] == "pro"


async def test_chat_includes_conversation_history(db):
    await _seed_case(db)
    mock = MockGeminiClient()
    mock.queue("Yes, as discussed.", tokens_used=30)
    agent = ClinicalContextAgent(gemini=mock)

    await agent.chat(db, "SYN-001", [
        {"role": "user", "content": "Is this Luminal A?"},
        {"role": "assistant", "content": "Yes, Luminal A."},
        {"role": "user", "content": "Confirm the stage?"},
    ], phase="pre")

    prompt = mock.calls[0]["prompt"]
    assert "CONVERSATION HISTORY" in prompt
    assert "Is this Luminal A?" in prompt          # prior turn echoed
    assert "Confirm the stage?" in prompt          # new question is the tail


async def test_chat_unknown_case_reports_no_data(db):
    mock = MockGeminiClient()
    mock.queue("I can only answer about the current case.")
    agent = ClinicalContextAgent(gemini=mock)
    await agent.chat(db, "DOES-NOT-EXIST",
                     [{"role": "user", "content": "hi"}], phase="pre")
    assert "No case data available yet." in mock.calls[0]["prompt"]


# ── route guards ─────────────────────────────────────────────────────────────

async def test_chat_route_happy_path(client):
    get_gemini_client().queue("Stage IIA, ER+/PR+/HER2-.", tokens_used=90)
    r = await client.post("/cases/SYN-001/chat", json={
        "messages": [{"role": "user", "content": "Summarize this case."}],
        "phase": "pre",
    })
    assert r.status_code == 200, r.text
    assert r.json()["reply"] == "Stage IIA, ER+/PR+/HER2-."


async def test_chat_route_404_missing_case(client):
    r = await client.post("/cases/GHOST/chat", json={
        "messages": [{"role": "user", "content": "hi"}],
    })
    assert r.status_code == 404


async def test_chat_route_422_last_message_not_user(client):
    r = await client.post("/cases/SYN-001/chat", json={
        "messages": [{"role": "assistant", "content": "hi"}],
    })
    assert r.status_code == 422


async def test_chat_route_422_empty_messages(client):
    r = await client.post("/cases/SYN-001/chat", json={"messages": []})
    assert r.status_code == 422


# ── documented bugs: _build_context raw SQL vs actual schema ─────────────────
# sessions has no `created_at` (it's `started_at`); actions has no `case_id`
async def test_chat_mid_phase_pulls_transcript(db):
    await _seed_case(db)
    await repo.create_session(db, Session(
        session_id="s1", case_id="SYN-001", started_at=_NOW, status="in_meeting"))
    await repo.add_transcript(db, Transcript(
        session_id="s1", speaker="Oncologist", text="Recommend BCS.",
        timestamp_ms=0, created_at=_NOW))
    mock = MockGeminiClient()
    mock.queue("ok")
    agent = ClinicalContextAgent(gemini=mock)
    await agent.chat(db, "SYN-001",
                     [{"role": "user", "content": "what was said?"}], phase="mid")
    assert "MEETING TRANSCRIPT" in mock.calls[0]["prompt"]


async def test_chat_post_phase_pulls_actions(db):
    await _seed_case(db)
    await repo.create_session(db, Session(
        session_id="s1", case_id="SYN-001", started_at=_NOW, status="post_meeting"))
    await repo.add_action(db, Action(
        session_id="s1", description="Order MRI follow-up", owner="Dr. Smith",
        due_date="2026-06-01", status="open", created_at=_NOW))
    mock = MockGeminiClient()
    mock.queue("ok")
    agent = ClinicalContextAgent(gemini=mock)
    await agent.chat(db, "SYN-001",
                     [{"role": "user", "content": "open actions?"}], phase="post")
    assert "OPEN ACTIONS" in mock.calls[0]["prompt"]
