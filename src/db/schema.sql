-- OncoBoard.ai schema (PostgreSQL / Neon)
-- All raw SQL lives in src/db/. Agents must use repository.py, never touch the DB directly.
-- Designed against the TCGA-BRCA dataset:
--   Clinical_Treatment_Data.csv   -> cases (1097 patients, clean receptor columns)
--   Clinical_Demographic_Data.csv -> case_demographics_extra (richer TCGA fields)
--   CNV_RAW.csv                   -> case_genomics (CNV as JSON blob, ~59K genes)
--   MRI_and_SVS_Patches/...       -> case_files (Vercel Blob URL references)


-- One row per patient. Sourced primarily from Clinical_Treatment_Data.csv.
-- Receptor columns come from *_by_ihc fields. Molecular subtype is derived
-- at seed time from ER/PR/HER2 (rule-based: TNBC / HER2-enriched / Luminal A / Luminal B).
CREATE TABLE IF NOT EXISTS cases (
    case_id                  TEXT PRIMARY KEY,            -- TCGA-XX-XXXX barcode
    age_at_diagnosis         INTEGER,
    gender                   TEXT,
    race                     TEXT,
    ethnicity                TEXT,
    vital_status             TEXT,
    tumor_status             TEXT,
    menopause_status         TEXT,

    -- Staging (AJCC)
    ajcc_stage               TEXT,                        -- ajcc_pathologic_tumor_stage
    ajcc_t                   TEXT,                        -- ajcc_tumor_pathologic_pt
    ajcc_n                   TEXT,                        -- ajcc_nodes_pathologic_pn
    ajcc_m                   TEXT,                        -- ajcc_metastasis_pathologic_pm

    -- Pathology / location
    histological_type        TEXT,
    anatomic_subdivision     TEXT,
    margin_status            TEXT,
    surgical_procedure       TEXT,
    lymph_nodes_examined     INTEGER,

    -- Receptors (clinical-grade IHC from Treatment CSV)
    er_status                TEXT,                        -- er_status_by_ihc
    pr_status                TEXT,                        -- pr_status_by_ihc
    her2_status              TEXT,                        -- her2_status_by_ihc
    her2_ihc_score           TEXT,

    -- Derived at seed time
    molecular_subtype        TEXT,                        -- Luminal A | Luminal B | HER2-enriched | Triple Negative | Unknown

    -- Treatments stored as JSON (drug list extracted from one-hot Drug_* columns)
    treatments_json          TEXT,                        -- {"drugs": [...], "surgery": "...", ...}

    -- Followup
    last_contact_days_to     INTEGER,

    -- Full source rows for agents that need fields beyond the curated columns
    source_treatment_json    TEXT,                        -- entire Treatment CSV row as JSON
    source_demographic_json  TEXT,                        -- entire Demographic CSV row as JSON (nullable)

    created_at               TEXT NOT NULL,
    updated_at               TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cases_subtype ON cases(molecular_subtype);
CREATE INDEX IF NOT EXISTS idx_cases_stage   ON cases(ajcc_stage);


-- Genomic copy number variation. One row per (case, source) pair.
-- copy_numbers_json is a {gene_symbol: copy_number_float} dict (~59K entries
-- when sourced from CNV_RAW). Agents query specific genes via repository helpers.
CREATE TABLE IF NOT EXISTS case_genomics (
    genomics_id        SERIAL PRIMARY KEY,
    case_id            TEXT NOT NULL,
    source             TEXT NOT NULL,                     -- 'CNV_RAW' for now
    copy_numbers_json  TEXT NOT NULL,
    created_at         TEXT NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
    UNIQUE (case_id, source)
);

CREATE INDEX IF NOT EXISTS idx_genomics_case ON case_genomics(case_id);


-- Image file references. We never store image bytes - only Vercel Blob URLs.
-- One row per image (MRI patch, SVS patch). series_id groups patches from the
-- same MRI series; sequence_index is the img_NNNN position within that series.
CREATE TABLE IF NOT EXISTS case_files (
    file_id         SERIAL PRIMARY KEY,
    case_id         TEXT NOT NULL,
    file_type       TEXT NOT NULL,                        -- 'mri_patch' | 'svs_patch'
    file_path       TEXT NOT NULL,                        -- full Vercel Blob URL
    series_id       TEXT,
    sequence_index  INTEGER,
    metadata_json   TEXT,
    created_at      TEXT NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_case_files_case   ON case_files(case_id);
CREATE INDEX IF NOT EXISTS idx_case_files_type   ON case_files(file_type);
CREATE INDEX IF NOT EXISTS idx_case_files_series ON case_files(case_id, series_id);


-- One row per agent invocation. output_json is the typed agent result.
-- run_id groups all agent outputs from a single pipeline run on a case.
CREATE TABLE IF NOT EXISTS agent_outputs (
    output_id      SERIAL PRIMARY KEY,
    case_id        TEXT NOT NULL,
    agent_name     TEXT NOT NULL,
    run_id         TEXT NOT NULL,
    output_json    TEXT NOT NULL,
    status         TEXT NOT NULL,                         -- 'success' | 'error'
    error_message  TEXT,
    duration_ms    INTEGER,
    tokens_used    INTEGER,
    created_at     TEXT NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_agent_outputs_case_agent ON agent_outputs(case_id, agent_name);
CREATE INDEX IF NOT EXISTS idx_agent_outputs_run        ON agent_outputs(run_id);


-- A tumor board meeting on a specific case.
CREATE TABLE IF NOT EXISTS sessions (
    session_id  TEXT PRIMARY KEY,
    case_id     TEXT NOT NULL,
    started_at  TEXT NOT NULL,
    ended_at    TEXT,
    status      TEXT NOT NULL,                            -- 'pre_meeting' | 'in_meeting' | 'post_meeting' | 'completed'
    FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS transcripts (
    transcript_id  SERIAL PRIMARY KEY,
    session_id     TEXT NOT NULL,
    speaker        TEXT,
    text           TEXT NOT NULL,
    timestamp_ms   INTEGER NOT NULL,                      -- offset from session start
    created_at     TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_transcripts_session ON transcripts(session_id);


CREATE TABLE IF NOT EXISTS recommendations (
    recommendation_id  SERIAL PRIMARY KEY,
    session_id         TEXT NOT NULL,
    content_json       TEXT NOT NULL,
    confirmed_at       TEXT,                              -- set when Human Gate 2 passes
    created_at         TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS actions (
    action_id     SERIAL PRIMARY KEY,
    session_id    TEXT NOT NULL,
    description   TEXT NOT NULL,
    owner         TEXT,
    due_date      TEXT,
    status        TEXT NOT NULL,                          -- 'open' | 'in_progress' | 'completed' | 'overdue'
    created_at    TEXT NOT NULL,
    completed_at  TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_actions_session ON actions(session_id);
CREATE INDEX IF NOT EXISTS idx_actions_status  ON actions(status);


-- Human gate audit trail (Gate 1 = pre-meeting approval, Gate 2 = consensus
-- confirmed, Gate 3 = note approved). Required for clinical traceability.
CREATE TABLE IF NOT EXISTS gates (
    gate_id      SERIAL PRIMARY KEY,
    session_id   TEXT NOT NULL,
    gate_name    TEXT NOT NULL,                           -- 'pre_meeting_approval' | 'consensus_confirmed' | 'note_approved'
    approved_by  TEXT,
    approved_at  TEXT,
    notes        TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_gates_session ON gates(session_id);
