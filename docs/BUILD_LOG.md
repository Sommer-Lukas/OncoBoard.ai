# OncoBoard.ai — Build Log

Chronological record of what's landed on the backend, what decisions were made, and how each stage was verified. Read this if you're joining the project mid-build or trying to understand why something is the way it is.

The build plan that drives these stages lives in `~/.claude/plans/hazy-snacking-wave.md` (local to the author's machine). Mirror at a glance:

| Stage | Theme | Status |
|---|---|---|
| 1 | Backend foundation (config, logging, FastAPI app) | ✅ landed |
| 2 | DB layer (schema, models, repository, init) | ✅ landed |
| — | Reconcile ARCHITECTURE.md with the real dataset | ✅ landed |
| 3 | Data seeding (synthetic + TCGA-BRCA) | ✅ landed |
| 4 | Agent framework (BaseAgent + MockGeminiClient) | ⏳ next |
| 5 | Vertical slice: CaseCompiler + SummaryAgent + SSE route | ⏳ pending |
| 6 | Test infrastructure (pytest + mocked Gemini) | ⏳ pending |

> **How to add an entry:** append a new `## Stage N — Title` section at the bottom following the template at the end of this file. Keep entries short — link to the commit for code, document only the *why* and *what changed*.

---

## Stage 1 — Backend foundation
- **Branch:** `feature/backend-foundation`
- **Commit:** `6ce76dd`
- **Landed:** 2026-05-14
- **PR:** https://github.com/RaneemK-commits/OncoBoard.ai/pull/new/feature/backend-foundation

### What landed
| File | Purpose |
|---|---|
| `requirements.txt` | Added `pydantic`, `pydantic-settings`, `aiosqlite`, `pytest`, `pytest-asyncio`, `pytest-httpx` |
| `.env.example` | Template for `GEMINI_API_KEY`, model IDs, `DB_PATH`, `LOG_LEVEL`, `GEMINI_MOCK`, ClinicalTrials.gov + PubMed base URLs |
| `pyproject.toml` | Pytest config (`testpaths=tests`, `asyncio_mode=auto`) |
| `src/config.py` | `Settings` via `pydantic-settings`; single cached `get_settings()` accessor |
| `src/logging_setup.py` | JSON structured logger + `log_agent_run()` helper for the clinical audit trail (case_id, agent_name, duration_ms, tokens_used, status) |
| `src/main.py` | `create_app()` FastAPI factory; mounts `/health` route |
| `src/{__init__,api/__init__,agents/__init__,db/__init__,data/__init__}.py` | Package markers |

### Decisions worth knowing
- **`pydantic-settings` over `os.getenv`** — typed, validates at startup, one source of truth for env. Cached via `lru_cache(1)` so settings reads are free everywhere.
- **JSON logging from day one** — every agent run emits a structured audit log. Clinical traceability is a non-negotiable requirement per `ARCHITECTURE.md` §5.
- **`aiosqlite`** — FastAPI is async; sync SQLite would block the event loop when seven pre-meeting agents fan out in parallel.
- **`GEMINI_MOCK` env flag** — Stage 4 will gate a `MockGeminiClient` on this so tests and dev never burn API quota.

### Verify locally
```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
cp .env.example .env   # fill GEMINI_API_KEY when ready
.\.venv\Scripts\python.exe -c "from src.main import create_app; create_app()"
uvicorn src.main:app --reload
# GET http://localhost:8000/health -> {"status":"ok"}
```

### Unblocks
- Every later stage. Nothing else can run until `Settings`, the FastAPI factory, and the venv exist.

---

## Stage 2 — DB layer
- **Branch:** `feature/backend-foundation` (continues from Stage 1)
- **Commit:** `eaa5c0e`
- **Landed:** 2026-05-14
- **PR:** same as Stage 1

### What landed
| File | Purpose |
|---|---|
| `src/db/schema.sql` | DDL for 9 tables — designed against the *real* TCGA-BRCA columns, not the architecture doc's assumptions |
| `src/db/models.py` | Pydantic v2 models per table; JSON columns surface as typed dicts |
| `src/db/connection.py` | `aiosqlite` context manager (FK enforcement on) + `get_db()` FastAPI dependency |
| `src/db/repository.py` | ~30 typed async CRUD helpers; the **only** file allowed to contain raw SQL |
| `src/db/init_db.py` | Idempotent initializer (`python -m src.db.init_db`) |
| `scripts/smoke_stage2.py` | End-to-end roundtrip of all 9 tables + FK cascade |

### Tables
`cases`, `case_genomics`, `case_files`, `agent_outputs`, `sessions`, `transcripts`, `recommendations`, `actions`, `gates`.

### Decisions worth knowing
- **`case_id` = full TCGA barcode** (e.g. `TCGA-AO-A03M`). Single PK across every table.
- **CNV stored as a per-case JSON blob** in `case_genomics.copy_numbers_json` (~59K genes). Column-per-gene would have been unworkable. Repo helper `get_gene_copy_numbers(case_id, ["TP53","BRCA1",...])` lets agents pull only the genes they need.
- **`molecular_subtype` populated at seed time**, not by `PathologyAgent`. The dataset doesn't ship a pre-classified column, but downstream agents need to filter on subtype before `PathologyAgent` finishes — so it's a deterministic seed-time computation, not an agent output.
- **`source_treatment_json` + `source_demographic_json`** preserve the full raw CSV rows. Agents can reach uncommon TCGA fields without us pre-modeling all 80+ demographic columns.
- **`agent_outputs` is append-only**, indexed on `(case_id, agent_name)` and `run_id`. Every agent invocation = one row. Audit trail for free.
- **`.gitignore`** extended to exclude `data/raw/` and `data/processed/`.

### Verify locally
```powershell
.\.venv\Scripts\python.exe -m src.db.init_db
.\.venv\Scripts\python.exe scripts\smoke_stage2.py
# Expected final line: "SMOKE TEST PASSED"
```

The smoke test exercises every CRUD helper, every JSON-column roundtrip, and confirms FK cascade on case delete.

### Unblocks
- Stage 3 (seed scripts need the repository layer).
- Stage 4 (`BaseAgent.execute()` persists to `agent_outputs`).

---

## Reconcile ARCHITECTURE.md with the actual TCGA-BRCA dataset
- **Branch:** `feature/backend-foundation`
- **Commit:** `8a73a42`
- **Landed:** 2026-05-14

Two statements in the original `ARCHITECTURE.md` didn't match the dataset once we inspected it during the Stage 2 schema work. Fixed in the same branch so the docs and schema agree:

1. **"Vision data is preprocessed into 256×256 tiles with stain normalization"** → the dataset already ships pre-tiled JPEG patches per MRI series. We ingest only file paths into `case_files`; there is no separate tiling step.
2. **"molecular subtype is pre-classified"** → it isn't. We derive it deterministically at seed time from ER/PR/HER2 IHC, and `PathologyAgent` references the seed-time subtype rather than asserting it.

Also noted: `source_treatment_json` / `source_demographic_json` preserve the raw rows, so agents can reach rare TCGA fields without us pre-modeling every column.

---

## Stage 3 — Data seeding
- **Branch:** `feature/data-seeding` (cut from `feature/backend-foundation`)
- **Commit:** `06c97c5`
- **Landed:** 2026-05-14
- **PR:** https://github.com/RaneemK-commits/OncoBoard.ai/pull/new/feature/data-seeding

### What landed
| File | Purpose |
|---|---|
| `src/data/subtype.py` | Rule-based ER/PR/HER2 → molecular subtype classifier |
| `src/data/fixtures/synthetic_cases.json` | 4 hand-crafted cases (`SYN-001..004`) covering all 4 subtypes, each with a small CNV blob |
| `src/data/seed_synthetic.py` | Loads the fixture via the repository layer; idempotent; CLI |
| `src/data/seed_tcga.py` | Real loader: Treatment → `cases`, Demographic joined as JSON, CNV_RAW → genomics blob (`CNV_` prefix stripped). Optional `--images-dir` registers MRI patch paths |
| `src/data/README.md` | Download + run instructions |
| `scripts/smoke_stage3.py` | Verifies classifier rules + both seed paths + idempotency + cross-table lookups |

### Subtype classifier rules (Ki67 unavailable in TCGA-BRCA)
| HR (ER+ or PR+) | HER2 | Subtype |
|---|---|---|
| − | − | Triple Negative |
| − | + | HER2-enriched |
| + | − | Luminal A |
| + | + | Luminal B |
| any field missing/equivocal | — | `None` (Unknown) |

### Observed seed (current `data/raw/`)
| Metric | Value |
|---|---|
| Cases loaded (Clinical_Treatment_Data.csv) | 1,097 |
| Cases with CNV genomics (CNV_RAW.csv) | 125 |
| Full seed runtime | ~14s |

**Subtype distribution:**
| Subtype | Count | % |
|---|---|---|
| Luminal A | 445 | 40.6% |
| Luminal B | 126 | 11.5% |
| Triple Negative | 118 | 10.8% |
| HER2-enriched | 38 | 3.5% |
| Unknown | 370 | 33.7% |

The 370 Unknown cases is faithful to the source — that's how many TCGA-BRCA patients have missing or "Equivocal" receptor data in `er_status_by_ihc` / `pr_status_by_ihc` / `her2_status_by_ihc`.

### Decisions worth knowing
- **Treatment CSV is the case-of-record**, not Demographic. Treatment has clean `*_by_ihc` receptor columns (≈1,097 patients); Demographic has receptor info buried in pipe-delimited `follow_ups_molecular_tests_*` lists (≈122 patients). Joining gives us breadth + cleanliness.
- **Drug one-hots flattened into `treatments_json.drugs`** — deduped case-insensitively because TCGA has e.g. `Drug_TAMOXIFEN`, `Drug_Tamoxifen`, `Drug_tamoxifen` as separate columns for the same drug. Free-text variants are out, canonical names are in.
- **CNV `CNV_` prefix stripped** at seed time — agents look up `TP53`, not `CNV_TP53`.
- **Image-path registration is opt-in** via `--images-dir`. 250K+ patches; we don't want them in SQLite by default. The schema supports them; the seed doesn't pull them unless asked.

### Verify locally
```powershell
.\.venv\Scripts\python.exe -m src.data.seed_synthetic
# -> "seeded 4 synthetic cases"

.\.venv\Scripts\python.exe -m src.data.seed_tcga
# -> case/genomics counts + subtype distribution

.\.venv\Scripts\python.exe scripts\smoke_stage3.py
# Expected final line: "SMOKE TEST PASSED"
```

### Unblocks
- Stage 5 vertical slice: `CaseCompiler` needs real (or synthetic) cases to compile from.
- All seven pre-meeting agents: their inputs (receptor status, stage, treatments, genomics, image paths) all come from these tables.

---

## Up next — Stage 4
**Agent framework.** A single `src/agents/base.py` with `BaseAgent` (typed inputs, typed outputs via Pydantic, persistence to `agent_outputs`, structured logging, retry) and `src/agents/gemini_client.py` (Gemini SDK wrapper + `MockGeminiClient` toggled by `GEMINI_MOCK=1`). Once that lands, the remaining 12 agents are template work.

---

## Entry template

```markdown
## Stage N — Title
- **Branch:** `feature/...`
- **Commit:** `<short SHA>`
- **Landed:** YYYY-MM-DD
- **PR:** <link>

### What landed
| File | Purpose |
|---|---|
| ... | ... |

### Decisions worth knowing
- ...

### Verify locally
```powershell
...
```

### Unblocks
- ...
```
