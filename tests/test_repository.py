"""Repository CRUD + FK cascade + JSON column roundtrips."""
import pytest

from src.db import repository as repo
from src.db.models import (
    Action,
    AgentOutput,
    Case,
    CaseFile,
    CaseGenomics,
    Gate,
    Recommendation,
    Session,
    Transcript,
)

_NOW = "2026-05-15T00:00:00+00:00"


def _case(case_id: str = "TCGA-AO-A03M", **overrides) -> Case:
    base = dict(
        case_id=case_id,
        age_at_diagnosis=42,
        er_status="Positive",
        pr_status="Positive",
        her2_status="Negative",
        molecular_subtype="Luminal A",
        ajcc_stage="Stage I",
        treatments={"drugs": ["Tamoxifen"]},
        created_at=_NOW,
        updated_at=_NOW,
    )
    base.update(overrides)
    return Case(**base)


async def test_case_roundtrip_and_json_column(db):
    await repo.upsert_case(db, _case())
    got = await repo.get_case(db, "TCGA-AO-A03M")
    assert got is not None
    assert got.molecular_subtype == "Luminal A"
    assert got.treatments == {"drugs": ["Tamoxifen"]}


async def test_upsert_is_idempotent(db):
    await repo.upsert_case(db, _case())
    await repo.upsert_case(db, _case(molecular_subtype="Luminal B"))
    assert await repo.count_cases(db) == 1
    got = await repo.get_case(db, "TCGA-AO-A03M")
    assert got.molecular_subtype == "Luminal B"


async def test_list_cases_filter_by_subtype(db):
    await repo.upsert_case(db, _case("C1", molecular_subtype="Luminal A"))
    await repo.upsert_case(db, _case("C2", molecular_subtype="Triple Negative"))
    tnbc = await repo.list_cases(db, molecular_subtype="Triple Negative")
    assert [c.case_id for c in tnbc] == ["C2"]


async def test_genomics_source_agnostic_lookup(db):
    await repo.upsert_case(db, _case())
    await repo.upsert_genomics(db, CaseGenomics(
        case_id="TCGA-AO-A03M", source="synthetic",
        copy_numbers={"TP53": 1.0, "ERBB2": 4.0}, created_at=_NOW,
    ))
    # Pinned-source lookup misses a non-CNV_RAW row…
    assert await repo.get_genomics(db, "TCGA-AO-A03M") is None
    # …but the source-agnostic helper finds it.
    rec = await repo.get_genomics_any(db, "TCGA-AO-A03M")
    assert rec is not None and rec.source == "synthetic"
    assert rec.copy_numbers["ERBB2"] == 4.0


async def test_agent_output_append_and_latest(db):
    await repo.upsert_case(db, _case())
    await repo.save_agent_output(db, AgentOutput(
        case_id="TCGA-AO-A03M", agent_name="CaseCompiler", run_id="r1",
        output={"v": 1}, status="success", created_at=_NOW,
    ))
    await repo.save_agent_output(db, AgentOutput(
        case_id="TCGA-AO-A03M", agent_name="CaseCompiler", run_id="r2",
        output={"v": 2}, status="success", created_at=_NOW,
    ))
    latest = await repo.get_latest_agent_output(db, "TCGA-AO-A03M", "CaseCompiler")
    assert latest.output == {"v": 2}
    run = await repo.list_agent_outputs_for_run(db, "r1")
    assert len(run) == 1 and run[0].output == {"v": 1}


async def test_session_transcript_recommendation_action_gate(db):
    await repo.upsert_case(db, _case())
    await repo.create_session(db, Session(
        session_id="s1", case_id="TCGA-AO-A03M",
        started_at=_NOW, status="in_meeting",
    ))
    await repo.add_transcript(db, Transcript(
        session_id="s1", speaker="Dr. X", text="hello",
        timestamp_ms=1000, created_at=_NOW,
    ))
    rec_id = await repo.save_recommendation(db, Recommendation(
        session_id="s1", content={"plan": "x"}, created_at=_NOW,
    ))
    await repo.confirm_recommendation(db, rec_id)
    act_id = await repo.add_action(db, Action(
        session_id="s1", description="follow up", status="open", created_at=_NOW,
    ))
    await repo.update_action_status(db, act_id, "in_progress")
    await repo.record_gate(db, Gate(
        session_id="s1", gate_name="consensus_confirmed", approved_by="dr.x",
    ))

    assert len(await repo.list_transcripts(db, "s1")) == 1
    assert (await repo.list_actions(db, "s1", status="in_progress"))[0].status == "in_progress"
    assert len(await repo.list_gates(db, "s1")) == 1
    await repo.update_session_status(db, "s1", "completed", ended_at=_NOW)
    assert (await repo.get_session(db, "s1")).status == "completed"


async def test_fk_cascade_on_case_delete(db):
    await repo.upsert_case(db, _case())
    await repo.add_case_file(db, CaseFile(
        case_id="TCGA-AO-A03M", file_type="mri_patch",
        file_path="x.jpg", created_at=_NOW,
    ))
    await repo.save_agent_output(db, AgentOutput(
        case_id="TCGA-AO-A03M", agent_name="A", run_id="r",
        output={}, status="success", created_at=_NOW,
    ))
    await db.execute("DELETE FROM cases WHERE case_id = ?", ("TCGA-AO-A03M",))
    await db.commit()
    assert await repo.count_cases(db) == 0
    assert await repo.list_case_files(db, "TCGA-AO-A03M") == []
    assert await repo.get_latest_agent_output(db, "TCGA-AO-A03M", "A") is None
