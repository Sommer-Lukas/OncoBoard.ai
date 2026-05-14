from typing import Any

from pydantic import BaseModel, ConfigDict


class _ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Case(_ORMModel):
    case_id: str
    age_at_diagnosis: int | None = None
    gender: str | None = None
    race: str | None = None
    ethnicity: str | None = None
    vital_status: str | None = None
    tumor_status: str | None = None
    menopause_status: str | None = None

    ajcc_stage: str | None = None
    ajcc_t: str | None = None
    ajcc_n: str | None = None
    ajcc_m: str | None = None

    histological_type: str | None = None
    anatomic_subdivision: str | None = None
    margin_status: str | None = None
    surgical_procedure: str | None = None
    lymph_nodes_examined: int | None = None

    er_status: str | None = None
    pr_status: str | None = None
    her2_status: str | None = None
    her2_ihc_score: str | None = None

    molecular_subtype: str | None = None

    treatments: dict[str, Any] | None = None
    last_contact_days_to: int | None = None

    source_treatment: dict[str, Any] | None = None
    source_demographic: dict[str, Any] | None = None

    created_at: str
    updated_at: str


class CaseGenomics(_ORMModel):
    genomics_id: int | None = None
    case_id: str
    source: str
    copy_numbers: dict[str, float]
    created_at: str


class CaseFile(_ORMModel):
    file_id: int | None = None
    case_id: str
    file_type: str
    file_path: str
    series_id: str | None = None
    sequence_index: int | None = None
    metadata: dict[str, Any] | None = None
    created_at: str


class AgentOutput(_ORMModel):
    output_id: int | None = None
    case_id: str
    agent_name: str
    run_id: str
    output: dict[str, Any]
    status: str
    error_message: str | None = None
    duration_ms: int | None = None
    tokens_used: int | None = None
    created_at: str


class Session(_ORMModel):
    session_id: str
    case_id: str
    started_at: str
    ended_at: str | None = None
    status: str


class Transcript(_ORMModel):
    transcript_id: int | None = None
    session_id: str
    speaker: str | None = None
    text: str
    timestamp_ms: int
    created_at: str


class Recommendation(_ORMModel):
    recommendation_id: int | None = None
    session_id: str
    content: dict[str, Any]
    confirmed_at: str | None = None
    created_at: str


class Action(_ORMModel):
    action_id: int | None = None
    session_id: str
    description: str
    owner: str | None = None
    due_date: str | None = None
    status: str
    created_at: str
    completed_at: str | None = None


class Gate(_ORMModel):
    gate_id: int | None = None
    session_id: str
    gate_name: str
    approved_by: str | None = None
    approved_at: str | None = None
    notes: str | None = None
