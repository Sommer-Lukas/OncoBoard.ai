"""Typed async CRUD against Postgres. All raw SQL in the project lives here."""
import json
from datetime import datetime, timezone
from typing import Any

import asyncpg

from src.utils.patient_names import fake_name
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


def _row_to_case(row: asyncpg.Record) -> Case:
    return Case(
        case_id=row["case_id"],
        patient_name=fake_name(row["case_id"]),
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


async def upsert_case(db: asyncpg.Connection, case: Case) -> None:
    now = _now()
    await db.execute(
        f"""
        INSERT INTO cases ({CASE_COLUMNS}) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14,
            $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27, $28
        )
        ON CONFLICT(case_id) DO UPDATE SET
            age_at_diagnosis=EXCLUDED.age_at_diagnosis,
            gender=EXCLUDED.gender,
            race=EXCLUDED.race,
            ethnicity=EXCLUDED.ethnicity,
            vital_status=EXCLUDED.vital_status,
            tumor_status=EXCLUDED.tumor_status,
            menopause_status=EXCLUDED.menopause_status,
            ajcc_stage=EXCLUDED.ajcc_stage,
            ajcc_t=EXCLUDED.ajcc_t,
            ajcc_n=EXCLUDED.ajcc_n,
            ajcc_m=EXCLUDED.ajcc_m,
            histological_type=EXCLUDED.histological_type,
            anatomic_subdivision=EXCLUDED.anatomic_subdivision,
            margin_status=EXCLUDED.margin_status,
            surgical_procedure=EXCLUDED.surgical_procedure,
            lymph_nodes_examined=EXCLUDED.lymph_nodes_examined,
            er_status=EXCLUDED.er_status,
            pr_status=EXCLUDED.pr_status,
            her2_status=EXCLUDED.her2_status,
            her2_ihc_score=EXCLUDED.her2_ihc_score,
            molecular_subtype=EXCLUDED.molecular_subtype,
            treatments_json=EXCLUDED.treatments_json,
            last_contact_days_to=EXCLUDED.last_contact_days_to,
            source_treatment_json=EXCLUDED.source_treatment_json,
            source_demographic_json=EXCLUDED.source_demographic_json,
            updated_at=EXCLUDED.updated_at
        """,
        case.case_id,
        case.age_at_diagnosis,
        case.gender,
        case.race,
        case.ethnicity,
        case.vital_status,
        case.tumor_status,
        case.menopause_status,
        case.ajcc_stage,
        case.ajcc_t,
        case.ajcc_n,
        case.ajcc_m,
        case.histological_type,
        case.anatomic_subdivision,
        case.margin_status,
        case.surgical_procedure,
        case.lymph_nodes_examined,
        case.er_status,
        case.pr_status,
        case.her2_status,
        case.her2_ihc_score,
        case.molecular_subtype,
        _dumps(case.treatments),
        case.last_contact_days_to,
        _dumps(case.source_treatment),
        _dumps(case.source_demographic),
        case.created_at or now,
        now,
    )


async def get_case(db: asyncpg.Connection, case_id: str) -> Case | None:
    row = await db.fetchrow(
        f"SELECT {CASE_COLUMNS} FROM cases WHERE case_id = $1", case_id
    )
    return _row_to_case(row) if row else None


async def list_cases(
    db: asyncpg.Connection,
    *,
    limit: int = 100,
    offset: int = 0,
    molecular_subtype: str | None = None,
    has_data: bool = False,
) -> list[Case]:
    conditions: list[str] = []
    params: list[object] = []
    p = 0

    if molecular_subtype:
        p += 1
        conditions.append(f"molecular_subtype = ${p}")
        params.append(molecular_subtype)
    if has_data:
        conditions.append("case_id IN (SELECT case_id FROM case_genomics)")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.extend([limit, offset])
    rows = await db.fetch(
        f"SELECT {CASE_COLUMNS} FROM cases {where} ORDER BY case_id LIMIT ${p + 1} OFFSET ${p + 2}",
        *params,
    )
    return [_row_to_case(r) for r in rows]


async def count_cases(db: asyncpg.Connection) -> int:
    row = await db.fetchrow("SELECT COUNT(*) AS n FROM cases")
    return int(row["n"]) if row else 0


# ---------- case_genomics ----------

async def upsert_genomics(db: asyncpg.Connection, genomics: CaseGenomics) -> None:
    await db.execute(
        """
        INSERT INTO case_genomics (case_id, source, copy_numbers_json, created_at)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT(case_id, source) DO UPDATE SET
            copy_numbers_json = EXCLUDED.copy_numbers_json,
            created_at = EXCLUDED.created_at
        """,
        genomics.case_id,
        genomics.source,
        json.dumps(genomics.copy_numbers),
        genomics.created_at or _now(),
    )


async def get_genomics(
    db: asyncpg.Connection, case_id: str, source: str = "CNV_RAW"
) -> CaseGenomics | None:
    row = await db.fetchrow(
        "SELECT genomics_id, case_id, source, copy_numbers_json, created_at "
        "FROM case_genomics WHERE case_id = $1 AND source = $2",
        case_id,
        source,
    )
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
    db: asyncpg.Connection, case_id: str
) -> CaseGenomics | None:
    """Return genomics for a case regardless of source (CNV_RAW, synthetic, ...).

    Most callers shouldn't care which source produced the copy-number data;
    pinning a source means synthetic-seeded cases look like they have none.
    Picks the most recent row if a case somehow has multiple sources.
    """
    row = await db.fetchrow(
        "SELECT genomics_id, case_id, source, copy_numbers_json, created_at "
        "FROM case_genomics WHERE case_id = $1 ORDER BY created_at DESC, genomics_id DESC "
        "LIMIT 1",
        case_id,
    )
    if not row:
        return None
    return CaseGenomics(
        genomics_id=row["genomics_id"],
        case_id=row["case_id"],
        source=row["source"],
        copy_numbers=json.loads(row["copy_numbers_json"]),
        created_at=row["created_at"],
    )


async def has_genomics(db: asyncpg.Connection, case_id: str) -> bool:
    row = await db.fetchrow(
        "SELECT 1 FROM case_genomics WHERE case_id = $1 LIMIT 1", case_id
    )
    return row is not None


async def get_gene_copy_numbers(
    db: asyncpg.Connection, case_id: str, genes: list[str], source: str = "CNV_RAW"
) -> dict[str, float | None]:
    """Convenience: pull just a few genes for an agent without loading 59K of them."""
    record = await get_genomics(db, case_id, source)
    if not record:
        return {g: None for g in genes}
    return {g: record.copy_numbers.get(g) for g in genes}


# ---------- case_files ----------

async def add_case_file(db: asyncpg.Connection, file: CaseFile) -> int:
    file_id = await db.fetchval(
        """
        INSERT INTO case_files
            (case_id, file_type, file_path, series_id, sequence_index, metadata_json, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING file_id
        """,
        file.case_id,
        file.file_type,
        file.file_path,
        file.series_id,
        file.sequence_index,
        _dumps(file.metadata),
        file.created_at or _now(),
    )
    return file_id or 0


async def list_case_files(
    db: asyncpg.Connection, case_id: str, *, file_type: str | None = None
) -> list[CaseFile]:
    if file_type:
        rows = await db.fetch(
            "SELECT file_id, case_id, file_type, file_path, series_id, sequence_index, "
            "metadata_json, created_at FROM case_files "
            "WHERE case_id = $1 AND file_type = $2 "
            "ORDER BY series_id, sequence_index",
            case_id,
            file_type,
        )
    else:
        rows = await db.fetch(
            "SELECT file_id, case_id, file_type, file_path, series_id, sequence_index, "
            "metadata_json, created_at FROM case_files "
            "WHERE case_id = $1 ORDER BY file_type, series_id, sequence_index",
            case_id,
        )
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

async def save_agent_output(db: asyncpg.Connection, output: AgentOutput) -> int:
    output_id = await db.fetchval(
        """
        INSERT INTO agent_outputs
            (case_id, agent_name, run_id, output_json, status, error_message,
             duration_ms, tokens_used, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        RETURNING output_id
        """,
        output.case_id,
        output.agent_name,
        output.run_id,
        json.dumps(output.output),
        output.status,
        output.error_message,
        output.duration_ms,
        output.tokens_used,
        output.created_at or _now(),
    )
    return output_id or 0


async def get_latest_agent_output(
    db: asyncpg.Connection, case_id: str, agent_name: str
) -> AgentOutput | None:
    row = await db.fetchrow(
        """
        SELECT output_id, case_id, agent_name, run_id, output_json, status,
               error_message, duration_ms, tokens_used, created_at
        FROM agent_outputs
        WHERE case_id = $1 AND agent_name = $2
        ORDER BY output_id DESC LIMIT 1
        """,
        case_id,
        agent_name,
    )
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
    db: asyncpg.Connection, run_id: str
) -> list[AgentOutput]:
    rows = await db.fetch(
        """
        SELECT output_id, case_id, agent_name, run_id, output_json, status,
               error_message, duration_ms, tokens_used, created_at
        FROM agent_outputs WHERE run_id = $1 ORDER BY output_id
        """,
        run_id,
    )
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

async def create_session(db: asyncpg.Connection, session: Session) -> None:
    await db.execute(
        """
        INSERT INTO sessions (session_id, case_id, started_at, ended_at, status)
        VALUES ($1, $2, $3, $4, $5)
        """,
        session.session_id,
        session.case_id,
        session.started_at,
        session.ended_at,
        session.status,
    )


async def get_session(db: asyncpg.Connection, session_id: str) -> Session | None:
    row = await db.fetchrow(
        "SELECT session_id, case_id, started_at, ended_at, status FROM sessions WHERE session_id = $1",
        session_id,
    )
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
    db: asyncpg.Connection, session_id: str, status: str, ended_at: str | None = None
) -> None:
    await db.execute(
        "UPDATE sessions SET status = $1, ended_at = COALESCE($2, ended_at) WHERE session_id = $3",
        status,
        ended_at,
        session_id,
    )


# ---------- transcripts ----------

async def add_transcript(db: asyncpg.Connection, transcript: Transcript) -> int:
    transcript_id = await db.fetchval(
        """
        INSERT INTO transcripts (session_id, speaker, text, timestamp_ms, created_at)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING transcript_id
        """,
        transcript.session_id,
        transcript.speaker,
        transcript.text,
        transcript.timestamp_ms,
        transcript.created_at or _now(),
    )
    return transcript_id or 0


async def list_transcripts(db: asyncpg.Connection, session_id: str) -> list[Transcript]:
    rows = await db.fetch(
        "SELECT transcript_id, session_id, speaker, text, timestamp_ms, created_at "
        "FROM transcripts WHERE session_id = $1 ORDER BY timestamp_ms",
        session_id,
    )
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

async def save_recommendation(db: asyncpg.Connection, rec: Recommendation) -> int:
    recommendation_id = await db.fetchval(
        """
        INSERT INTO recommendations (session_id, content_json, confirmed_at, created_at)
        VALUES ($1, $2, $3, $4)
        RETURNING recommendation_id
        """,
        rec.session_id,
        json.dumps(rec.content),
        rec.confirmed_at,
        rec.created_at or _now(),
    )
    return recommendation_id or 0


async def confirm_recommendation(
    db: asyncpg.Connection, recommendation_id: int, confirmed_at: str | None = None
) -> None:
    await db.execute(
        "UPDATE recommendations SET confirmed_at = $1 WHERE recommendation_id = $2",
        confirmed_at or _now(),
        recommendation_id,
    )


# ---------- actions ----------

async def add_action(db: asyncpg.Connection, action: Action) -> int:
    action_id = await db.fetchval(
        """
        INSERT INTO actions
            (session_id, description, owner, due_date, status, created_at, completed_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING action_id
        """,
        action.session_id,
        action.description,
        action.owner,
        action.due_date,
        action.status,
        action.created_at or _now(),
        action.completed_at,
    )
    return action_id or 0


async def list_actions(
    db: asyncpg.Connection, session_id: str, *, status: str | None = None
) -> list[Action]:
    if status:
        rows = await db.fetch(
            "SELECT action_id, session_id, description, owner, due_date, status, "
            "created_at, completed_at FROM actions "
            "WHERE session_id = $1 AND status = $2 ORDER BY action_id",
            session_id,
            status,
        )
    else:
        rows = await db.fetch(
            "SELECT action_id, session_id, description, owner, due_date, status, "
            "created_at, completed_at FROM actions "
            "WHERE session_id = $1 ORDER BY action_id",
            session_id,
        )
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
    db: asyncpg.Connection,
    action_id: int,
    status: str,
    completed_at: str | None = None,
) -> None:
    await db.execute(
        "UPDATE actions SET status = $1, completed_at = COALESCE($2, completed_at) WHERE action_id = $3",
        status,
        completed_at,
        action_id,
    )


# ---------- gates ----------

async def record_gate(db: asyncpg.Connection, gate: Gate) -> int:
    gate_id = await db.fetchval(
        """
        INSERT INTO gates (session_id, gate_name, approved_by, approved_at, notes)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING gate_id
        """,
        gate.session_id,
        gate.gate_name,
        gate.approved_by,
        gate.approved_at or _now(),
        gate.notes,
    )
    return gate_id or 0


async def list_gates(db: asyncpg.Connection, session_id: str) -> list[Gate]:
    rows = await db.fetch(
        "SELECT gate_id, session_id, gate_name, approved_by, approved_at, notes "
        "FROM gates WHERE session_id = $1 ORDER BY gate_id",
        session_id,
    )
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
