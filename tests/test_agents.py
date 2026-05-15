"""Agent framework + CaseCompiler + SummaryAgent."""
import json

import pytest
from pydantic import BaseModel

from src.agents.base import BaseAgent
from src.agents.case_compiler import CaseCompiler, CaseCompilerOutput
from src.agents.gemini_client import MockGeminiClient
from src.agents.summary_agent import SummaryAgent, SummaryOutput
from src.agents.types import AgentError, AgentOutputValidationError, CaseNotFoundError
from src.db import repository as repo
from src.db.models import Case

_NOW = "2026-05-15T00:00:00+00:00"


class DemoOutput(BaseModel):
    case_id: str
    note: str


class DemoAgent(BaseAgent[DemoOutput]):
    name = "DemoAgent"
    model_tier = "flash"
    output_schema = DemoOutput

    async def run(self, db, case: Case, *, run_id: str) -> DemoOutput:
        resp = await self.call_gemini(prompt=f"summarize {case.case_id}")
        return DemoOutput(case_id=case.case_id, note=resp.text)


class BrokenAgent(BaseAgent[DemoOutput]):
    name = "BrokenAgent"
    model_tier = "flash"
    output_schema = DemoOutput

    async def run(self, db, case: Case, *, run_id: str):
        return {"not": "valid"}  # type: ignore[return-value]


class RaisingAgent(BaseAgent[DemoOutput]):
    name = "RaisingAgent"
    model_tier = "flash"
    output_schema = DemoOutput

    async def run(self, db, case: Case, *, run_id: str):
        raise RuntimeError("boom")


async def _seed_case(db, case_id="C1") -> None:
    await repo.upsert_case(db, Case(
        case_id=case_id, er_status="Positive", pr_status="Positive",
        her2_status="Negative", molecular_subtype="Luminal A",
        ajcc_stage="Stage I", created_at=_NOW, updated_at=_NOW,
    ))


def test_missing_classvars_rejected_at_definition():
    with pytest.raises(TypeError, match="name|model_tier|output_schema"):
        class Bad(BaseAgent[DemoOutput]):  # noqa: F811
            async def run(self, db, case, *, run_id):
                return DemoOutput(case_id="x", note="y")


async def test_happy_path_persists_and_tracks_tokens(db):
    await _seed_case(db)
    mock = MockGeminiClient()
    mock.queue("hello narrative", tokens_used=137)
    agent = DemoAgent(gemini=mock)

    result = await agent.execute(db, "C1")
    assert isinstance(result, DemoOutput)
    assert result.note == "hello narrative"

    row = await repo.get_latest_agent_output(db, "C1", "DemoAgent")
    assert row.status == "success"
    assert row.tokens_used == 137
    assert row.duration_ms is not None and row.duration_ms >= 0
    assert len(mock.calls) == 1 and mock.calls[0]["model_tier"] == "flash"


async def test_missing_case_raises_and_writes_no_row(db):
    agent = DemoAgent(gemini=MockGeminiClient())
    with pytest.raises(CaseNotFoundError):
        await agent.execute(db, "DOES-NOT-EXIST")
    assert await repo.get_latest_agent_output(db, "DOES-NOT-EXIST", "DemoAgent") is None


async def test_schema_mismatch_persists_error(db):
    await _seed_case(db)
    with pytest.raises(AgentOutputValidationError):
        await BrokenAgent().execute(db, "C1")
    row = await repo.get_latest_agent_output(db, "C1", "BrokenAgent")
    assert row.status == "error" and "DemoOutput" in row.error_message


async def test_subclass_exception_persists_error(db):
    await _seed_case(db)
    with pytest.raises(RuntimeError, match="boom"):
        await RaisingAgent().execute(db, "C1")
    row = await repo.get_latest_agent_output(db, "C1", "RaisingAgent")
    assert row.status == "error" and row.error_message == "boom"


async def test_shared_run_id_groups_outputs(db):
    await _seed_case(db)
    m = MockGeminiClient()
    m.queue("a", tokens_used=10)
    m.queue("b", tokens_used=20)
    await DemoAgent(gemini=m).execute(db, "C1", run_id="shared")
    await DemoAgent(gemini=m).execute(db, "C1", run_id="shared")
    outs = await repo.list_agent_outputs_for_run(db, "shared")
    assert len(outs) == 2
    assert {o.tokens_used for o in outs} == {10, 20}


# ---- CaseCompiler / SummaryAgent specifics ----

async def test_case_compiler_on_synthetic(seeded_db):
    from src.db.connection import connect
    async with connect() as db:
        out = await CaseCompiler().execute(db, "SYN-001")
    assert isinstance(out, CaseCompilerOutput)
    assert out.ready_for_review is True          # complete synthetic case
    assert out.genomics.has_data is True          # source="synthetic" found
    assert out.genomics.gene_count == 7
    assert out.data_gaps == []


async def test_case_compiler_flags_gaps(db):
    await repo.upsert_case(db, Case(
        case_id="GAPPY", created_at=_NOW, updated_at=_NOW,  # no stage/receptors
    ))
    out = await CaseCompiler().execute(db, "GAPPY")
    crit = [g for g in out.data_gaps if g.severity == "critical"]
    assert {g.field for g in crit} >= {"ajcc_stage", "er_status", "her2_status"}
    assert out.ready_for_review is False


async def test_summary_agent_requires_case_compiler_first(seeded_db):
    from src.db.connection import connect
    async with connect() as db:
        with pytest.raises(AgentError, match="CaseCompiler"):
            await SummaryAgent(gemini=MockGeminiClient()).execute(db, "SYN-001")


async def test_summary_agent_happy_path(seeded_db):
    from src.db.connection import connect
    payload = json.dumps({
        "case_id": "SYN-001",
        "narrative": "A 52yo woman, Stage IIA, ER+/PR+/HER2-.",
        "key_points": ["Stage IIA", "Luminal A"],
        "data_gaps_flagged": [],
    })
    mock = MockGeminiClient()
    mock.queue(payload, tokens_used=321)
    async with connect() as db:
        await CaseCompiler().execute(db, "SYN-001", run_id="r")
        out = await SummaryAgent(gemini=mock).execute(db, "SYN-001", run_id="r")
    assert isinstance(out, SummaryOutput)
    assert out.case_id == "SYN-001"
    assert "Stage IIA" in out.narrative
