"""Stage 2 smoke test. Run from repo root with:
    .\\.venv\\Scripts\\python.exe scripts\\smoke_stage2.py
"""
import asyncio
import os
import sys
from pathlib import Path

# Ensure repo root is importable when running as a standalone script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Use an isolated DB so we don't pollute the real one.
os.environ["DB_PATH"] = "./.smoke_stage2.db"

from src.db import init_db as init_module
from src.db.connection import connect
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
from src.db import repository as repo


async def main() -> None:
    db_path = Path("./.smoke_stage2.db")
    if db_path.exists():
        db_path.unlink()

    await init_module.init_db()
    print("[ok] init_db")

    async with connect() as db:
        # cases
        case = Case(
            case_id="TCGA-AO-A03M",
            age_at_diagnosis=42,
            gender="female",
            er_status="Positive",
            pr_status="Positive",
            her2_status="Negative",
            molecular_subtype="Luminal A",
            ajcc_stage="Stage I",
            treatments={"drugs": ["Tamoxifen", "Doxorubicin"]},
            created_at="2026-05-14T00:00:00+00:00",
            updated_at="2026-05-14T00:00:00+00:00",
        )
        await repo.upsert_case(db, case)
        got = await repo.get_case(db, "TCGA-AO-A03M")
        assert got is not None and got.molecular_subtype == "Luminal A"
        assert got.treatments == {"drugs": ["Tamoxifen", "Doxorubicin"]}
        print(f"[ok] case roundtrip: {got.case_id} ({got.molecular_subtype})")

        # list / filter
        listed = await repo.list_cases(db, molecular_subtype="Luminal A")
        assert len(listed) == 1
        n = await repo.count_cases(db)
        assert n == 1
        print(f"[ok] list_cases + count_cases ({n})")

        # genomics
        await repo.upsert_genomics(
            db,
            CaseGenomics(
                case_id="TCGA-AO-A03M",
                source="CNV_RAW",
                copy_numbers={"TP53": 1.0, "BRCA1": 2.0, "ERBB2": 4.0},
                created_at="2026-05-14T00:00:00+00:00",
            ),
        )
        genes = await repo.get_gene_copy_numbers(
            db, "TCGA-AO-A03M", ["TP53", "ERBB2", "DOES_NOT_EXIST"]
        )
        assert genes == {"TP53": 1.0, "ERBB2": 4.0, "DOES_NOT_EXIST": None}
        print(f"[ok] genomics roundtrip: {genes}")

        # case_files
        file_id = await repo.add_case_file(
            db,
            CaseFile(
                case_id="TCGA-AO-A03M",
                file_type="mri_patch",
                file_path="data/raw/MRI_and_SVS_Patches/.../img_0000.jpg",
                series_id="1.000000-Localization-27022",
                sequence_index=0,
                created_at="2026-05-14T00:00:00+00:00",
            ),
        )
        files = await repo.list_case_files(db, "TCGA-AO-A03M", file_type="mri_patch")
        assert len(files) == 1 and files[0].file_id == file_id
        print(f"[ok] case_files roundtrip (file_id={file_id})")

        # agent_outputs
        out_id = await repo.save_agent_output(
            db,
            AgentOutput(
                case_id="TCGA-AO-A03M",
                agent_name="CaseCompiler",
                run_id="run-001",
                output={"missing_fields": []},
                status="success",
                duration_ms=42,
                tokens_used=128,
                created_at="2026-05-14T00:00:00+00:00",
            ),
        )
        latest = await repo.get_latest_agent_output(db, "TCGA-AO-A03M", "CaseCompiler")
        assert latest is not None and latest.output == {"missing_fields": []}
        run_outs = await repo.list_agent_outputs_for_run(db, "run-001")
        assert len(run_outs) == 1
        print(f"[ok] agent_outputs roundtrip (output_id={out_id})")

        # sessions + transcripts + recommendations + actions + gates
        await repo.create_session(
            db,
            Session(
                session_id="sess-1",
                case_id="TCGA-AO-A03M",
                started_at="2026-05-14T10:00:00+00:00",
                status="in_meeting",
            ),
        )
        await repo.add_transcript(
            db,
            Transcript(
                session_id="sess-1",
                speaker="Dr. Smith",
                text="The case is Stage I, ER+/PR+/HER2-.",
                timestamp_ms=1000,
                created_at="2026-05-14T10:00:01+00:00",
            ),
        )
        ts = await repo.list_transcripts(db, "sess-1")
        assert len(ts) == 1
        print(f"[ok] session + transcript roundtrip ({len(ts)} entry)")

        rec_id = await repo.save_recommendation(
            db,
            Recommendation(
                session_id="sess-1",
                content={"plan": "Adjuvant tamoxifen 5y"},
                created_at="2026-05-14T10:30:00+00:00",
            ),
        )
        await repo.confirm_recommendation(db, rec_id)
        print(f"[ok] recommendation confirm (id={rec_id})")

        action_id = await repo.add_action(
            db,
            Action(
                session_id="sess-1",
                description="Schedule MRI follow-up",
                owner="coordinator",
                due_date="2026-06-14",
                status="open",
                created_at="2026-05-14T10:30:00+00:00",
            ),
        )
        await repo.update_action_status(db, action_id, "in_progress")
        acts = await repo.list_actions(db, "sess-1", status="in_progress")
        assert len(acts) == 1
        print(f"[ok] action lifecycle (id={action_id}, status={acts[0].status})")

        gate_id = await repo.record_gate(
            db,
            Gate(
                session_id="sess-1",
                gate_name="consensus_confirmed",
                approved_by="dr.smith",
            ),
        )
        gates = await repo.list_gates(db, "sess-1")
        assert len(gates) == 1
        print(f"[ok] gate roundtrip (id={gate_id})")

        await repo.update_session_status(db, "sess-1", "completed", ended_at="2026-05-14T11:00:00+00:00")
        sess = await repo.get_session(db, "sess-1")
        assert sess is not None and sess.status == "completed"
        print("[ok] session status update")

    # FK + cascade sanity: deleting a case should cascade everything.
    async with connect() as db:
        await db.execute("DELETE FROM cases WHERE case_id = ?", ("TCGA-AO-A03M",))
        await db.commit()
    async with connect() as db:
        n = await repo.count_cases(db)
        assert n == 0
    print("[ok] FK cascade on case delete")

    # Cleanup
    db_path.unlink()
    print("\nSMOKE TEST PASSED")


if __name__ == "__main__":
    asyncio.run(main())
