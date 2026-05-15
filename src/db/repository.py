"""Typed async CRUD against SQLite. All raw SQL in the project lives here."""
import json
from datetime import datetime, timezone
from typing import Any

import aiosqlite

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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dumps(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value)


def _loads(value: str | None) -> Any:
    if value is None:
        return None
    return json.loads(value)


# ---------- cases ----------

CASE_COLUMNS = (
    "case_id, age_at_diagnosis, gender, race, ethnicity, vital_status, tumor_status, "
    "menopause_status, ajcc_stage, ajcc_t, ajcc_n, ajcc_m, histological_type, "
    "anatomic_subdivision, margin_status, surgical_procedure, lymph_nodes_examined, "
    "er_status, pr_status, her2_status, her2_ihc_score, molecular_subtype, "
    "treatments_json, last_contact_days_to, source_treatment_json, "
    "source_demographic_json, created_at, updated_at"
)


def _row_to_case(row: aiosqlite.Row) -> Case:
    return Case(
        case_id=row["case_id"],
        age_at_diagnosis=row["age_at_diagnosis"],
        gender=row["gender"],
        race=row["race"],
        ethnicity=row["ethnicity"],
        vital_status=row["vital_status"],
        tumor_status=row["tumor_status"],
        menopause_status=row["menopause_status"],
        ajcc_stage=row["ajcc_stage"],
        ajcc_t=row["ajcc_t"],
        ajcc_n=row["ajcc_n"],
        ajcc_m=row["ajcc_m"],
        histological_type=row["histological_type"],
        anatomic_subdivision=row["anatomic_subdivision"],
        margin_status=row["margin_status"],
        surgical_procedure=row["surgical_procedure"],
        lymph_nodes_examined=row["lymph_nodes_examined"],
        er_status=row["er_status"],
        pr_status=row["pr_status"],
        her2_status=row["her2_status"],
        her2_ihc_score=row["her2_ihc_score"],
        molecular_subtype=row["molecular_subtype"],
        treatments=_loads(row["treatments_json"]),
        last_contact_days_to=row["last_contact_days_to"],
        source_treatment=_loads(row["source_treatment_json"]),
        source_demographic=_loads(row["source_demographic_json"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


async def upsert_case(db: aiosqlite.Connection, case: Case) -> None:
    now = _now()
    await db.execute(
        f"""
        INSERT INTO cases ({CASE_COLUMNS}) VALUES (
            :case_id, :age_at_diagnosis, :gender, :race, :ethnicity, :vital_status,
            :tumor_status, :menopause_status, :ajcc_stage, :ajcc_t, :ajcc_n, :ajcc_m,
            :histological_type, :anatomic_subdivision, :margin_status,
            :surgical_procedure, :lymph_nodes_examined, :er_status, :pr_status,
            :her2_status, :her2_ihc_score, :molecular_subtype, :treatments_json,
            :last_contact_days_to, :source_treatment_json, :source_demographic_json,
            :created_at, :updated_at
        )
        ON CONFLICT(case_id) DO UPDATE SET
            age_at_diagnosis=excluded.age_at_diagnosis,
            gender=excluded.gender,
            race=excluded.race,
            ethnicity=excluded.ethnicity,
            vital_status=excluded.vital_status,
            tumor_status=excluded.tumor_status,
            menopause_status=excluded.menopause_status,
            ajcc_stage=excluded.ajcc_stage,
            ajcc_t=excluded.ajcc_t,
            ajcc_n=excluded.ajcc_n,
            ajcc_m=excluded.ajcc_m,
            histological_type=excluded.histological_type,
            anatomic_subdivision=excluded.anatomic_subdivision,
            margin_status=excluded.margin_status,
            surgical_procedure=excluded.surgical_procedure,
            lymph_nodes_examined=excluded.lymph_nodes_examined,
            er_status=excluded.er_status,
            pr_status=excluded.pr_status,
            her2_status=excluded.her2_status,
            her2_ihc_score=excluded.her2_ihc_score,
            molecular_subtype=excluded.molecular_subtype,
            treatments_json=excluded.treatments_json,
            last_contact_days_to=excluded.last_contact_days_to,
            source_treatment_json=excluded.source_treatment_json,
            source_demographic_json=excluded.source_demographic_json,
            updated_at=excluded.updated_at
        """,
        {
            "case_id": case.case_id,
            "age_at_diagnosis": case.age_at_diagnosis,
            "gender": case.gender,
            "race": case.race,
            "ethnicity": case.ethnicity,
            "vital_status": case.vital_status,
            "tumor_status": case.tumor_status,
            "menopause_status": case.menopause_status,
            "ajcc_stage": case.ajcc_stage,
            "ajcc_t": case.ajcc_t,
            "ajcc_n": case.ajcc_n,
            "ajcc_m": case.ajcc_m,
            "histological_type": case.histological_type,
            "anatomic_subdivision": case.anatomic_subdivision,
            "margin_status": case.margin_status,
            "surgical_procedure": case.surgical_procedure,
            "lymph_nodes_examined": case.lymph_nodes_examined,
            "er_status": case.er_status,
            "pr_status": case.pr_status,
            "her2_status": case.her2_status,
            "her2_ihc_score": case.her2_ihc_score,
            "molecular_subtype": case.molecular_subtype,
            "treatments_json": _dumps(case.treatments),
            "last_contact_days_to": case.last_contact_days_to,
            "source_treatment_json": _dumps(case.source_treatment),
            "source_demographic_json": _dumps(case.source_demographic),
            "created_at": case.created_at or now,
            "updated_at": now,
        },
    )
    await db.commit()


async def get_case(db: aiosqlite.Connection, case_id: str) -> Case | None:
    cur = await db.execute(
        f"SELECT {CASE_COLUMNS} FROM cases WHERE case_id = ?", (case_id,)
    )
    row = await cur.fetchone()
    return _row_to_case(row) if row else None


async def list_cases(
    db: aiosqlite.Connection,
    *,
    limit: int = 100,
    offset: int = 0,
    molecular_subtype: str | None = None,
    has_data: bool = False,
) -> list[Case]:
    conditions: list[str] = []
    params: list[object] = []

    if molecular_subtype:
        conditions.append("molecular_subtype = ?")
        params.append(molecular_subtype)
    if has_data:
        conditions.append("case_id IN (SELECT case_id FROM case_genomics)")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    cur = await db.execute(
        f"SELECT {CASE_COLUMNS} FROM cases {where} ORDER BY case_id LIMIT ? OFFSET ?",
        (*params, limit, offset),
    )
    rows = await cur.fetchall()
    return [_row_to_case(r) for r in rows]


async def count_cases(db: aiosqlite.Connection) -> int:
    cur = await db.execute("SELECT COUNT(*) AS n FROM cases")
    row = await cur.fetchone()
    return int(row["n"]) if row else 0


# ---------- case_genomics ----------

async def upsert_genomics(db: aiosqlite.Connection, genomics: CaseGenomics) -> None:
    await db.execute(
        """
        INSERT INTO case_genomics (case_id, source, copy_numbers_json, created_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(case_id, source) DO UPDATE SET
            copy_numbers_json = excluded.copy_numbers_json,
            created_at = excluded.created_at
        """,
        (genomics.case_id, genomics.source, json.dumps(genomics.copy_numbers), genomics.created_at or _now()),
    )
    await db.commit()


async def get_genomics(
    db: aiosqlite.Connection, case_id: str, source: str = "CNV_RAW"
) -> CaseGenomics | None:
    cur = await db.execute(
        "SELECT genomics_id, case_id, source, copy_numbers_json, created_at "
        "FROM case_genomics WHERE case_id = ? AND source = ?",
        (case_id, source),
    )
    row = await cur.fetchone()
    if not row:
        return None
    return CaseGenomics(
        genomics_id=row["genomics_id"],
        case_id=row["case_id"],
        source=row["source"],
        copy_numbers=json.loads(row["copy_numbers_json"]),
        created_at=row["created_at"],
    )


async def get_genomics_any(
    db: aiosqlite.Connection, case_id: str
) -> CaseGenomics | None:
    """Return genomics for a case regardless of source (CNV_RAW, synthetic, …).

    Most callers shouldn't care which source produced the copy-number data;
    pinning a source means synthetic-seeded cases look like they have none.
    Picks the most recent row if a case somehow has multiple sources.
    """
    cur = await db.execute(
        "SELECT genomics_id, case_id, source, copy_numbers_json, created_at "
        "FROM case_genomics WHERE case_id = ? ORDER BY created_at DESC, genomics_id DESC "
        "LIMIT 1",
        (case_id,),
    )
    row = await cur.fetchone()
    if not row:
        return None
    return CaseGenomics(
        genomics_id=row["genomics_id"],
        case_id=row["case_id"],
        source=row["source"],
        copy_numbers=json.loads(row["copy_numbers_json"]),
        created_at=row["created_at"],
    )


async def has_genomics(db: aiosqlite.Connection, case_id: str) -> bool:
    cur = await db.execute(
        "SELECT 1 FROM case_genomics WHERE case_id = ? LIMIT 1", (case_id,)
    )
    return await cur.fetchone() is not None


async def get_gene_copy_numbers(
    db: aiosqlite.Connection, case_id: str, genes: list[str], source: str = "CNV_RAW"
) -> dict[str, float | None]:
    """Convenience: pull just a few genes for an agent without loading 59K of them."""
    record = await get_genomics(db, case_id, source)
    if not record:
        return {g: None for g in genes}
    return {g: record.copy_numbers.get(g) for g in genes}


# ---------- case_files ----------

async def add_case_file(db: aiosqlite.Connection, file: CaseFile) -> int:
    cur = await db.execute(
        """
        INSERT INTO case_files
            (case_id, file_type, file_path, series_id, sequence_index, metadata_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            file.case_id,
            file.file_type,
            file.file_path,
            file.series_id,
            file.sequence_index,
            _dumps(file.metadata),
            file.created_at or _now(),
        ),
    )
    await db.commit()
    return cur.lastrowid or 0


async def list_case_files(
    db: aiosqlite.Connection, case_id: str, *, file_type: str | None = None
) -> list[CaseFile]:
    if file_type:
        cur = await db.execute(
            "SELECT * FROM case_files WHERE case_id = ? AND file_type = ? "
            "ORDER BY series_id, sequence_index",
            (case_id, file_type),
        )
    else:
        cur = await db.execute(
            "SELECT * FROM case_files WHERE case_id = ? ORDER BY file_type, series_id, sequence_index",
            (case_id,),
        )
    rows = await cur.fetchall()
    return [
        CaseFile(
            file_id=r["file_id"],
            case_id=r["case_id"],
            file_type=r["file_type"],
            file_path=r["file_path"],
            series_id=r["series_id"],
            sequence_index=r["sequence_index"],
            metadata=_loads(r["metadata_json"]),
            created_at=r["created_at"],
        )
        for r in rows
    ]


# ---------- agent_outputs ----------

async def save_agent_output(db: aiosqlite.Connection, output: AgentOutput) -> int:
    cur = await db.execute(
        """
        INSERT INTO agent_outputs
            (case_id, agent_name, run_id, output_json, status, error_message,
             duration_ms, tokens_used, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            output.case_id,
            output.agent_name,
            output.run_id,
            json.dumps(output.output),
            output.status,
            output.error_message,
            output.duration_ms,
            output.tokens_used,
            output.created_at or _now(),
        ),
    )
    await db.commit()
    return cur.lastrowid or 0


async def get_latest_agent_output(
    db: aiosqlite.Connection, case_id: str, agent_name: str
) -> AgentOutput | None:
    cur = await db.execute(
        """
        SELECT output_id, case_id, agent_name, run_id, output_json, status,
               error_message, duration_ms, tokens_used, created_at
        FROM agent_outputs
        WHERE case_id = ? AND agent_name = ?
        ORDER BY output_id DESC LIMIT 1
        """,
        (case_id, agent_name),
    )
    row = await cur.fetchone()
    if not row:
        return None
    return AgentOutput(
        output_id=row["output_id"],
        case_id=row["case_id"],
        agent_name=row["agent_name"],
        run_id=row["run_id"],
        output=json.loads(row["output_json"]),
        status=row["status"],
        error_message=row["error_message"],
        duration_ms=row["duration_ms"],
        tokens_used=row["tokens_used"],
        created_at=row["created_at"],
    )


async def list_agent_outputs_for_run(
    db: aiosqlite.Connection, run_id: str
) -> list[AgentOutput]:
    cur = await db.execute(
        """
        SELECT output_id, case_id, agent_name, run_id, output_json, status,
               error_message, duration_ms, tokens_used, created_at
        FROM agent_outputs WHERE run_id = ? ORDER BY output_id
        """,
        (run_id,),
    )
    rows = await cur.fetchall()
    return [
        AgentOutput(
            output_id=r["output_id"],
            case_id=r["case_id"],
            agent_name=r["agent_name"],
            run_id=r["run_id"],
            output=json.loads(r["output_json"]),
            status=r["status"],
            error_message=r["error_message"],
            duration_ms=r["duration_ms"],
            tokens_used=r["tokens_used"],
            created_at=r["created_at"],
        )
        for r in rows
    ]


# ---------- sessions ----------

async def create_session(db: aiosqlite.Connection, session: Session) -> None:
    await db.execute(
        """
        INSERT INTO sessions (session_id, case_id, started_at, ended_at, status)
        VALUES (?, ?, ?, ?, ?)
        """,
        (session.session_id, session.case_id, session.started_at, session.ended_at, session.status),
    )
    await db.commit()


async def get_session(db: aiosqlite.Connection, session_id: str) -> Session | None:
    cur = await db.execute(
        "SELECT session_id, case_id, started_at, ended_at, status FROM sessions WHERE session_id = ?",
        (session_id,),
    )
    row = await cur.fetchone()
    if not row:
        return None
    return Session(
        session_id=row["session_id"],
        case_id=row["case_id"],
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        status=row["status"],
    )


async def update_session_status(
    db: aiosqlite.Connection, session_id: str, status: str, ended_at: str | None = None
) -> None:
    await db.execute(
        "UPDATE sessions SET status = ?, ended_at = COALESCE(?, ended_at) WHERE session_id = ?",
        (status, ended_at, session_id),
    )
    await db.commit()


# ---------- transcripts ----------

async def add_transcript(db: aiosqlite.Connection, transcript: Transcript) -> int:
    cur = await db.execute(
        """
        INSERT INTO transcripts (session_id, speaker, text, timestamp_ms, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            transcript.session_id,
            transcript.speaker,
            transcript.text,
            transcript.timestamp_ms,
            transcript.created_at or _now(),
        ),
    )
    await db.commit()
    return cur.lastrowid or 0


async def list_transcripts(db: aiosqlite.Connection, session_id: str) -> list[Transcript]:
    cur = await db.execute(
        "SELECT * FROM transcripts WHERE session_id = ? ORDER BY timestamp_ms",
        (session_id,),
    )
    rows = await cur.fetchall()
    return [
        Transcript(
            transcript_id=r["transcript_id"],
            session_id=r["session_id"],
            speaker=r["speaker"],
            text=r["text"],
            timestamp_ms=r["timestamp_ms"],
            created_at=r["created_at"],
        )
        for r in rows
    ]


# ---------- recommendations ----------

async def save_recommendation(db: aiosqlite.Connection, rec: Recommendation) -> int:
    cur = await db.execute(
        """
        INSERT INTO recommendations (session_id, content_json, confirmed_at, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (rec.session_id, json.dumps(rec.content), rec.confirmed_at, rec.created_at or _now()),
    )
    await db.commit()
    return cur.lastrowid or 0


async def confirm_recommendation(
    db: aiosqlite.Connection, recommendation_id: int, confirmed_at: str | None = None
) -> None:
    await db.execute(
        "UPDATE recommendations SET confirmed_at = ? WHERE recommendation_id = ?",
        (confirmed_at or _now(), recommendation_id),
    )
    await db.commit()


# ---------- actions ----------

async def add_action(db: aiosqlite.Connection, action: Action) -> int:
    cur = await db.execute(
        """
        INSERT INTO actions
            (session_id, description, owner, due_date, status, created_at, completed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            action.session_id,
            action.description,
            action.owner,
            action.due_date,
            action.status,
            action.created_at or _now(),
            action.completed_at,
        ),
    )
    await db.commit()
    return cur.lastrowid or 0


async def list_actions(
    db: aiosqlite.Connection, session_id: str, *, status: str | None = None
) -> list[Action]:
    if status:
        cur = await db.execute(
            "SELECT * FROM actions WHERE session_id = ? AND status = ? ORDER BY action_id",
            (session_id, status),
        )
    else:
        cur = await db.execute(
            "SELECT * FROM actions WHERE session_id = ? ORDER BY action_id",
            (session_id,),
        )
    rows = await cur.fetchall()
    return [
        Action(
            action_id=r["action_id"],
            session_id=r["session_id"],
            description=r["description"],
            owner=r["owner"],
            due_date=r["due_date"],
            status=r["status"],
            created_at=r["created_at"],
            completed_at=r["completed_at"],
        )
        for r in rows
    ]


async def update_action_status(
    db: aiosqlite.Connection,
    action_id: int,
    status: str,
    completed_at: str | None = None,
) -> None:
    await db.execute(
        "UPDATE actions SET status = ?, completed_at = COALESCE(?, completed_at) WHERE action_id = ?",
        (status, completed_at, action_id),
    )
    await db.commit()


# ---------- gates ----------

async def record_gate(db: aiosqlite.Connection, gate: Gate) -> int:
    cur = await db.execute(
        """
        INSERT INTO gates (session_id, gate_name, approved_by, approved_at, notes)
        VALUES (?, ?, ?, ?, ?)
        """,
        (gate.session_id, gate.gate_name, gate.approved_by, gate.approved_at or _now(), gate.notes),
    )
    await db.commit()
    return cur.lastrowid or 0


async def list_gates(db: aiosqlite.Connection, session_id: str) -> list[Gate]:
    cur = await db.execute(
        "SELECT * FROM gates WHERE session_id = ? ORDER BY gate_id",
        (session_id,),
    )
    rows = await cur.fetchall()
    return [
        Gate(
            gate_id=r["gate_id"],
            session_id=r["session_id"],
            gate_name=r["gate_name"],
            approved_by=r["approved_by"],
            approved_at=r["approved_at"],
            notes=r["notes"],
        )
        for r in rows
    ]
