"""Pipeline runner + SSE route + read-only case endpoints."""
import json

from src.agents.case_compiler import CaseCompiler
from src.agents.gemini_client import MockGeminiClient, get_gemini_client
from src.agents.pipeline import run_pre_meeting
from src.db import repository as repo
from src.db.connection import connect

_VALID_SUMMARY = json.dumps({
    "case_id": "SYN-001",
    "narrative": "52yo woman, Stage IIA, ER+/PR+/HER2-, Luminal A.",
    "key_points": ["Stage IIA", "Luminal A"],
    "data_gaps_flagged": [],
})


async def test_pipeline_event_order_and_shared_run_id(seeded_db):
    mock = MockGeminiClient()
    mock.queue(_VALID_SUMMARY, tokens_used=210)
    events = []
    async with connect() as db:
        async for ev in run_pre_meeting(db, "SYN-001", gemini=mock):
            events.append((ev.event, ev.agent, ev.status))

    assert ("agent", "CaseCompiler", "done") in events
    assert ("agent", "SummaryAgent", "done") in events
    assert events[-1] == ("pipeline", None, "complete")

    async with connect() as db:
        cc = await repo.get_latest_agent_output(db, "SYN-001", "CaseCompiler")
        sa = await repo.get_latest_agent_output(db, "SYN-001", "SummaryAgent")
    assert cc.status == sa.status == "success"
    assert cc.run_id == sa.run_id


async def test_pipeline_failure_propagates(seeded_db):
    mock = MockGeminiClient()  # empty queue -> default "{}" -> SummaryAgent fails
    events = []
    async with connect() as db:
        async for ev in run_pre_meeting(db, "SYN-003", gemini=mock):
            events.append((ev.event, ev.agent, ev.status))
    assert ("agent", "CaseCompiler", "done") in events
    assert ("agent", "SummaryAgent", "error") in events
    assert events[-1] == ("pipeline", None, "error")

    async with connect() as db:
        sa = await repo.get_latest_agent_output(db, "SYN-003", "SummaryAgent")
    assert sa.status == "error" and sa.error_message


async def test_list_and_detail_endpoints(client):
    r = await client.get("/cases?limit=4")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 4
    assert {c["case_id"] for c in body["items"]} == {
        "SYN-001", "SYN-002", "SYN-003", "SYN-004"
    }

    r = await client.get("/cases/SYN-002")
    assert r.status_code == 200
    assert r.json()["molecular_subtype"] == "Luminal B"

    assert (await client.get("/cases/NOPE")).status_code == 404


async def test_health_endpoint(client):
    r = await client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


async def test_sse_route_streams_events(client):
    # Route doesn't pass an explicit client -> uses the singleton mock.
    singleton = get_gemini_client()
    assert isinstance(singleton, MockGeminiClient)
    singleton.queue(_VALID_SUMMARY, tokens_used=99)

    seen: list[str] = []
    async with client.stream("POST", "/cases/SYN-002/pre-meeting/run") as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        async for line in resp.aiter_lines():
            if line.startswith("event: "):
                seen.append(line.removeprefix("event: ").strip())

    assert "agent" in seen
    assert seen[-1] == "pipeline"

    async with connect() as db:
        sa = await repo.get_latest_agent_output(db, "SYN-002", "SummaryAgent")
    assert sa.status == "success" and sa.tokens_used == 99


async def test_sse_route_404_for_missing_case(client):
    r = await client.post("/cases/GHOST/pre-meeting/run")
    assert r.status_code == 404
