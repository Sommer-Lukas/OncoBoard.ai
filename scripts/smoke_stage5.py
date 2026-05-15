"""Stage 5 smoke test — the pre-meeting vertical slice.

Run from repo root:
    .\\.venv\\Scripts\\python.exe scripts\\smoke_stage5.py

Covers:
  A. Pipeline runner directly (explicit MockGemini) — event sequence + DB rows
  B. SSE route via httpx ASGI transport — streamed events + 404
  C. Failure path — SummaryAgent error surfaces as pipeline error event
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SMOKE_DB = Path("./.smoke_stage5.db")
os.environ["DB_PATH"] = str(SMOKE_DB)
os.environ["GEMINI_MOCK"] = "1"

from src.config import get_settings
get_settings.cache_clear()  # type: ignore[attr-defined]

import httpx

from src.agents.gemini_client import MockGeminiClient, get_gemini_client, reset_gemini_client
from src.agents.pipeline import run_pre_meeting
from src.data import seed_synthetic
from src.db import repository as repo
from src.db.connection import connect

_VALID_SUMMARY = json.dumps({
    "case_id": "SYN-001",
    "narrative": "52-year-old postmenopausal woman, Stage IIA invasive ductal "
                 "carcinoma, ER+/PR+/HER2-, Luminal A. No critical data gaps.",
    "key_points": [
        "Stage IIA (T2 N0 M0)",
        "ER+/PR+/HER2- → Luminal A",
        "Lumpectomy, negative margins",
    ],
    "data_gaps_flagged": [],
})


async def phase_a_pipeline_direct() -> None:
    mock = MockGeminiClient()
    mock.queue(_VALID_SUMMARY, tokens_used=210)

    events = []
    async with connect() as db:
        async for ev in run_pre_meeting(db, "SYN-001", gemini=mock):
            events.append((ev.event, ev.agent, ev.status))

    assert ("agent", "CaseCompiler", "running") in events
    assert ("agent", "CaseCompiler", "done") in events
    assert ("agent", "SummaryAgent", "running") in events
    assert ("agent", "SummaryAgent", "done") in events
    assert events[-1] == ("pipeline", None, "complete"), events[-1]
    print(f"[ok] pipeline emitted {len(events)} events in correct order")

    async with connect() as db:
        cc = await repo.get_latest_agent_output(db, "SYN-001", "CaseCompiler")
        sa = await repo.get_latest_agent_output(db, "SYN-001", "SummaryAgent")
        assert cc is not None and cc.status == "success"
        assert sa is not None and sa.status == "success"
        assert cc.run_id == sa.run_id, "both agents must share one run_id"
        assert cc.output["ready_for_review"] is True
        assert cc.output["genomics"]["has_data"] is True  # SYN-001 has CNV sample
        assert sa.output["narrative"].startswith("52-year-old")
        assert sa.tokens_used == 210
        print(f"[ok] DB rows: CaseCompiler + SummaryAgent share run_id={cc.run_id[:8]}…, "
              f"summary tokens={sa.tokens_used}")


async def phase_b_sse_route() -> None:
    from src.main import create_app

    # The route doesn't pass an explicit client, so it uses the singleton.
    reset_gemini_client()
    client_singleton = get_gemini_client()
    assert isinstance(client_singleton, MockGeminiClient)
    client_singleton.queue(_VALID_SUMMARY, tokens_used=99)

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 404 path
        r = await client.post("/cases/NOPE-404/pre-meeting/run")
        assert r.status_code == 404, r.status_code
        print(f"[ok] missing case -> 404 ({r.json()['detail']})")

        # Happy path: stream the SSE response
        seen_events: list[str] = []
        async with client.stream("POST", "/cases/SYN-002/pre-meeting/run") as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")
            async for line in resp.aiter_lines():
                if line.startswith("event: "):
                    seen_events.append(line.removeprefix("event: ").strip())

        assert "agent" in seen_events
        assert "pipeline" in seen_events
        assert seen_events[-1] == "pipeline", seen_events
        print(f"[ok] SSE stream delivered {len(seen_events)} events, "
              f"terminating with '{seen_events[-1]}'")

    async with connect() as db:
        sa = await repo.get_latest_agent_output(db, "SYN-002", "SummaryAgent")
        assert sa is not None and sa.status == "success"
        assert sa.tokens_used == 99
        print("[ok] SSE run persisted SummaryAgent output for SYN-002")


async def phase_c_failure_path() -> None:
    # Empty queue -> mock returns default "{}" -> SummaryAgent can't validate -> error
    mock = MockGeminiClient()
    events = []
    async with connect() as db:
        async for ev in run_pre_meeting(db, "SYN-003", gemini=mock):
            events.append((ev.event, ev.agent, ev.status))

    assert ("agent", "CaseCompiler", "done") in events
    assert ("agent", "SummaryAgent", "error") in events
    assert events[-1] == ("pipeline", None, "error"), events[-1]
    print(f"[ok] failure path: SummaryAgent error propagated as pipeline error")

    async with connect() as db:
        sa = await repo.get_latest_agent_output(db, "SYN-003", "SummaryAgent")
        assert sa is not None and sa.status == "error"
        assert sa.error_message is not None
        print(f"[ok] error row persisted: \"{sa.error_message[:60]}…\"")


async def main() -> None:
    if SMOKE_DB.exists():
        SMOKE_DB.unlink()
    n = await seed_synthetic.seed()
    assert n == 4
    print(f"[ok] seeded {n} synthetic cases\n")

    await phase_a_pipeline_direct()
    print()
    await phase_b_sse_route()
    print()
    await phase_c_failure_path()

    SMOKE_DB.unlink()
    print("\nSMOKE TEST PASSED")


if __name__ == "__main__":
    asyncio.run(main())
