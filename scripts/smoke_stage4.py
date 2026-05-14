"""Stage 4 smoke test. Run from repo root with:
    .\\.venv\\Scripts\\python.exe scripts\\smoke_stage4.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SMOKE_DB = Path("./.smoke_stage4.db")
os.environ["DB_PATH"] = str(SMOKE_DB)
os.environ["GEMINI_MOCK"] = "1"

from pydantic import BaseModel

from src.config import get_settings
get_settings.cache_clear()  # type: ignore[attr-defined]

from src.agents.base import BaseAgent
from src.agents.gemini_client import MockGeminiClient
from src.agents.types import AgentOutputValidationError, CaseNotFoundError
from src.data import seed_synthetic
from src.db import repository as repo
from src.db.connection import connect
from src.db.models import Case


# ---------- A trivial agent used only for smoke testing. ----------

class DemoOutput(BaseModel):
    case_id: str
    subtype: str
    notes: str


class DemoAgent(BaseAgent[DemoOutput]):
    name = "DemoAgent"
    model_tier = "flash"
    output_schema = DemoOutput

    async def run(self, db, case: Case, *, run_id: str) -> DemoOutput:
        # Touch the gemini client so we exercise the token-accumulator path.
        resp = await self.call_gemini(prompt=f"Summarize {case.case_id}")
        return DemoOutput(
            case_id=case.case_id,
            subtype=case.molecular_subtype or "Unknown",
            notes=resp.text,
        )


class BrokenAgent(BaseAgent[DemoOutput]):
    """Returns a dict that doesn't match the declared schema — should produce
    an AgentOutputValidationError and persist a status='error' row."""
    name = "BrokenAgent"
    model_tier = "flash"
    output_schema = DemoOutput

    async def run(self, db, case: Case, *, run_id: str) -> DemoOutput:
        return {"not": "valid"}  # type: ignore[return-value]


class RaisingAgent(BaseAgent[DemoOutput]):
    name = "RaisingAgent"
    model_tier = "flash"
    output_schema = DemoOutput

    async def run(self, db, case: Case, *, run_id: str) -> DemoOutput:
        raise RuntimeError("agent blew up")


# ---------- Tests ----------

async def main() -> None:
    if SMOKE_DB.exists():
        SMOKE_DB.unlink()

    # Seed synthetic data so we have cases to point agents at.
    n = await seed_synthetic.seed()
    assert n == 4
    print(f"[ok] seeded {n} synthetic cases")

    # ----- 1. ClassVar enforcement at subclass-definition time -----
    try:
        class MissingClassVars(BaseAgent[DemoOutput]):  # type: ignore[misc]
            async def run(self, db, case, *, run_id):
                return DemoOutput(case_id=case.case_id, subtype="x", notes="y")
        raise AssertionError("expected TypeError")
    except TypeError as e:
        assert "name" in str(e) or "model_tier" in str(e) or "output_schema" in str(e)
        print(f"[ok] subclass missing ClassVars rejected: {e}")

    # ----- 2. Happy path with mock that returns canned text + tokens -----
    mock = MockGeminiClient()
    mock.queue("synthetic narrative text", tokens_used=137)
    agent = DemoAgent(gemini=mock)

    async with connect() as db:
        result = await agent.execute(db, "SYN-001")
        assert isinstance(result, DemoOutput)
        assert result.case_id == "SYN-001"
        assert result.subtype == "Luminal A"
        assert result.notes == "synthetic narrative text"
        print(f"[ok] happy path: result={result.model_dump()}")

        latest = await repo.get_latest_agent_output(db, "SYN-001", "DemoAgent")
        assert latest is not None
        assert latest.status == "success"
        assert latest.tokens_used == 137
        assert latest.duration_ms is not None and latest.duration_ms >= 0
        assert latest.output["subtype"] == "Luminal A"
        print(
            f"[ok] persisted: status={latest.status}, tokens={latest.tokens_used}, "
            f"duration_ms={latest.duration_ms}"
        )

    # ----- 3. CaseNotFoundError when case is missing -----
    async with connect() as db:
        try:
            await agent.execute(db, "DOES-NOT-EXIST")
            raise AssertionError("expected CaseNotFoundError")
        except CaseNotFoundError as e:
            print(f"[ok] missing case raised: {e}")

        # Ensure no agent_outputs row was written for the missing case.
        ghost = await repo.get_latest_agent_output(db, "DOES-NOT-EXIST", "DemoAgent")
        assert ghost is None

    # ----- 4. Schema mismatch path persists error and re-raises -----
    broken = BrokenAgent()
    async with connect() as db:
        try:
            await broken.execute(db, "SYN-002")
            raise AssertionError("expected AgentOutputValidationError")
        except AgentOutputValidationError as e:
            print(f"[ok] schema mismatch raised: {type(e).__name__}")

        err_row = await repo.get_latest_agent_output(db, "SYN-002", "BrokenAgent")
        assert err_row is not None
        assert err_row.status == "error"
        assert err_row.error_message is not None
        assert "DemoOutput" in err_row.error_message
        print(f"[ok] error persisted: status={err_row.status}, msg head=\"{err_row.error_message[:60]}...\"")

    # ----- 5. Subclass exception also persists status=error and re-raises -----
    raiser = RaisingAgent()
    async with connect() as db:
        try:
            await raiser.execute(db, "SYN-003")
            raise AssertionError("expected RuntimeError")
        except RuntimeError as e:
            assert str(e) == "agent blew up"
            print(f"[ok] subclass exception raised: {e}")

        err_row = await repo.get_latest_agent_output(db, "SYN-003", "RaisingAgent")
        assert err_row is not None and err_row.status == "error"
        assert err_row.error_message == "agent blew up"
        print("[ok] subclass-error row persisted")

    # ----- 6. MockGeminiClient call recording -----
    assert len(mock.calls) == 1
    assert mock.calls[0]["model_tier"] == "flash"
    assert "SYN-001" in mock.calls[0]["prompt"]
    print(f"[ok] mock recorded {len(mock.calls)} call(s) with the right tier")

    # ----- 7. Multiple agents on one case share a run_id when given -----
    async with connect() as db:
        run_id = "shared-run-xyz"
        mock2 = MockGeminiClient()
        mock2.queue("first", tokens_used=10)
        mock2.queue("second", tokens_used=20)
        a1 = DemoAgent(gemini=mock2)
        # Have to override the singleton path: each instance is given its own mock.
        await a1.execute(db, "SYN-004", run_id=run_id)
        a2 = DemoAgent(gemini=mock2)
        await a2.execute(db, "SYN-004", run_id=run_id)

        outs = await repo.list_agent_outputs_for_run(db, run_id)
        assert len(outs) == 2
        assert {o.tokens_used for o in outs} == {10, 20}
        print(f"[ok] run_id grouping: {len(outs)} outputs share run_id, tokens={sorted(o.tokens_used for o in outs)}")

    SMOKE_DB.unlink()
    print("\nSMOKE TEST PASSED")


if __name__ == "__main__":
    asyncio.run(main())
