"""Post-meeting phase: 4 agents + pipeline + gates/SSE API.

The 4 agents run in two parallel phases, so a FIFO mock would be
order-fragile. Tests use a fake Gemini that routes by response_schema
name — deterministic regardless of asyncio.gather scheduling.
"""
import json

import pytest

import src.agents.gemini_client as gc
from src.agents.ActionDispatchAgent import ActionDispatchAgent, ActionDispatchOutput
from src.agents.FollowUpAgent import FollowUpAgent
from src.agents.gemini_client import GeminiResponse
from src.agents.NoteDraftAgent import NoteDraftAgent, TumorBoardNote
from src.agents.post_meeting_pipeline import run_post_meeting
from src.agents.SchedulingAgent import SchedulingAgent
from src.db import repository as repo
from src.db.connection import connect
from src.db.models import Action, AgentOutput, Case, Session

_NOW = "2026-05-17T00:00:00+00:00"

_PAYLOADS = {
    "TumorBoardNote": {
        "session_id": "x", "case_id": "x",
        "clinical_summary": "52yo, Stage IIA, Luminal A.",
        "imaging_summary": "BI-RADS 4B.", "pathology_summary": "IDC, ER+/PR+/HER2-.",
        "board_discussion": "Consensus on BCS + endocrine therapy.",
        "consensus_plan": "Lumpectomy then AI x5y.",
        "drafted_note": "TUMOR BOARD NOTE\n...full note...",
        "data_gaps": [],
    },
    "_ActionPlan": {
        "actions": [
            {"description": "Order Oncotype DX", "owner": "Oncologist", "due_date": "2026-05-24"},
            {"description": "Schedule RT consult", "owner": "Coordinator", "due_date": "2026-05-31"},
        ],
        "dispatch_summary": "2 actions dispatched.",
    },
    "_Escalation": {"escalation_notes": "1 item overdue — escalate to owner."},
    "SchedulingOutput": {
        "session_id": "x", "case_id": "x",
        "needs_representation": True, "suggested_timeframe": "3 weeks",
        "rationale": "Awaiting genomic assay result.",
        "blocking_items": ["Oncotype DX pending"],
    },
}


class RoutingGemini:
    """Returns the payload matching the requested response_schema."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def generate(self, *, response_schema=None, **kw) -> GeminiResponse:
        name = response_schema.__name__ if response_schema else "?"
        self.calls.append(name)
        return GeminiResponse(text=json.dumps(_PAYLOADS[name]), tokens_used=50)


async def _prep(db, case_id="SYN-001") -> str:
    """Case + session + a successful RecommendationAgent output (the prereq)."""
    await repo.upsert_case(db, Case(
        case_id=case_id, age_at_diagnosis=52, er_status="Positive",
        pr_status="Positive", her2_status="Negative",
        molecular_subtype="Luminal A", ajcc_stage="Stage IIA",
        created_at=_NOW, updated_at=_NOW,
    ))
    sid = "sess-pm-1"
    await repo.create_session(db, Session(
        session_id=sid, case_id=case_id, started_at=_NOW, status="post_meeting",
    ))
    await repo.save_agent_output(db, AgentOutput(
        case_id=case_id, agent_name="RecommendationAgent", run_id="r0",
        output={"decisions": [{"summary": "Adjuvant endocrine therapy"}],
                "next_steps": ["Oncotype DX"]},
        status="success", created_at=_NOW,
    ))
    return sid


# ── individual agents ────────────────────────────────────────────────────────

async def test_note_draft_requires_recommendation(db):
    await repo.upsert_case(db, Case(case_id="C9", created_at=_NOW, updated_at=_NOW))
    await repo.create_session(db, Session(
        session_id="s9", case_id="C9", started_at=_NOW, status="post_meeting"))
    from src.agents.types import AgentError
    with pytest.raises(AgentError, match="RecommendationAgent"):
        await NoteDraftAgent(gemini=RoutingGemini()).execute(db, "s9")


async def test_note_draft_happy_path(db):
    sid = await _prep(db)
    out = await NoteDraftAgent(gemini=RoutingGemini()).execute(db, sid)
    assert isinstance(out, TumorBoardNote)
    assert out.session_id == sid and out.case_id == "SYN-001"
    assert out.drafted_note.startswith("TUMOR BOARD NOTE")


async def test_action_dispatch_writes_actions(db):
    sid = await _prep(db)
    out = await ActionDispatchAgent(gemini=RoutingGemini()).execute(db, sid)
    assert isinstance(out, ActionDispatchOutput)
    assert len(out.actions_created) == 2
    assert all(a.action_id >= 1 for a in out.actions_created)
    persisted = await repo.list_actions(db, sid)
    assert {a.description for a in persisted} == {
        "Order Oncotype DX", "Schedule RT consult"
    }


async def test_follow_up_flags_overdue_deterministically(db):
    sid = await _prep(db)
    await repo.add_action(db, Action(
        session_id=sid, description="Overdue item", owner="Onc",
        due_date="2020-01-01", status="open", created_at=_NOW))
    await repo.add_action(db, Action(
        session_id=sid, description="Future item", owner="Onc",
        due_date="2099-01-01", status="open", created_at=_NOW))
    out = await FollowUpAgent(gemini=RoutingGemini()).execute(db, sid)
    assert out.total_actions == 2
    assert [o.description for o in out.overdue_actions] == ["Overdue item"]
    assert out.overdue_actions[0].days_overdue > 0
    assert out.escalation_notes


async def test_scheduling_agent_happy_path(db):
    sid = await _prep(db)
    out = await SchedulingAgent(gemini=RoutingGemini()).execute(db, sid)
    assert out.needs_representation is True
    assert out.session_id == sid and out.case_id == "SYN-001"


# ── pipeline ─────────────────────────────────────────────────────────────────

async def test_post_meeting_pipeline_order_and_completion(db):
    sid = await _prep(db)
    fake = RoutingGemini()
    events = []
    async for ev in run_post_meeting(db, sid, gemini=fake):
        events.append((ev.event, ev.agent, ev.status))

    done = [a for (e, a, s) in events if s == "done"]
    assert set(done) == {
        "NoteDraftAgent", "ActionDispatchAgent", "FollowUpAgent", "SchedulingAgent"
    }
    assert events[-1] == ("pipeline", None, "complete")
    # Shared run_id across all four.
    async with connect() as db2:
        for name in ("NoteDraftAgent", "ActionDispatchAgent",
                     "FollowUpAgent", "SchedulingAgent"):
            row = await repo.get_latest_agent_output(db2, "SYN-001", name)
            assert row is not None and row.status == "success"


# ── API: gates + SSE ─────────────────────────────────────────────────────────

async def test_post_meeting_run_requires_gate2(client):
    # Create a session via the meeting API, do NOT confirm Gate 2.
    r = await client.post("/cases/SYN-001/sessions")
    sid = r.json()["session_id"]
    r = await client.post(f"/sessions/{sid}/post-meeting/run")
    assert r.status_code == 409
    assert "Gate 2" in r.json()["detail"]


async def test_gate2_then_post_meeting_sse_then_gate3(client):
    r = await client.post("/cases/SYN-002/sessions")
    sid = r.json()["session_id"]

    # Route uses the singleton; install the schema-routing fake.
    gc._singleton = RoutingGemini()
    # Seed the RecommendationAgent prereq for this session's case.
    async with connect() as db:
        await repo.save_agent_output(db, AgentOutput(
            case_id="SYN-002", agent_name="RecommendationAgent", run_id="r0",
            output={"decisions": []}, status="success", created_at=_NOW))

    g2 = await client.post(
        f"/sessions/{sid}/gate2/confirm", json={"approved_by": "dr.smith"})
    assert g2.status_code == 200 and g2.json()["gate"] == "consensus_confirmed"

    seen: list[str] = []
    async with client.stream("POST", f"/sessions/{sid}/post-meeting/run") as resp:
        assert resp.status_code == 200
        async for line in resp.aiter_lines():
            if line.startswith("event: "):
                seen.append(line.removeprefix("event: ").strip())
    assert "agent" in seen and seen[-1] == "pipeline"

    g3 = await client.post(
        f"/sessions/{sid}/gate3/approve", json={"approved_by": "dr.smith", "notes": "ok"})
    assert g3.status_code == 200 and g3.json()["gate"] == "note_approved"

    async with connect() as db:
        gates = await repo.list_gates(db, sid)
    assert {g.gate_name for g in gates} == {"consensus_confirmed", "note_approved"}


async def test_gate_endpoints_404_missing_session(client):
    assert (await client.post(
        "/sessions/ghost/gate2/confirm", json={"approved_by": "x"})).status_code == 404
    assert (await client.post(
        "/sessions/ghost/gate3/approve", json={"approved_by": "x"})).status_code == 404
    assert (await client.post(
        "/sessions/ghost/post-meeting/run")).status_code == 404
