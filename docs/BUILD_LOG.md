# OncoBoard.ai — Build Log

Chronological record of what's landed on the backend, what decisions were made, and how each stage was verified. Read this if you're joining the project mid-build or trying to understand why something is the way it is.

The build plan that drives these stages lives in `~/.claude/plans/hazy-snacking-wave.md` (local to the author's machine). Mirror at a glance:

| Stage | Theme | Status |
|---|---|---|
| 1 | Backend foundation (config, logging, FastAPI app) | ✅ landed |
| 2 | DB layer (schema, models, repository, init) | ✅ landed |
| — | Reconcile ARCHITECTURE.md with the real dataset | ✅ landed |
| 3 | Data seeding (synthetic + TCGA-BRCA) | ✅ landed |
| 4 | Agent framework (BaseAgent + MockGeminiClient) | ✅ landed |
| 5 | Vertical slice: CaseCompiler + SummaryAgent + SSE route | ✅ landed |
| 6 | Test infrastructure (pytest + mocked Gemini) | ✅ landed |
| — | Post-plan: CI on push, full agent roster, post-meeting phase | ✅ landed |

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
.\.venv\Scripts\python.exe -m pytest tests/test_repository.py -q
```
> Originally verified via `scripts/smoke_stage2.py`; consolidated into the pytest suite in Stage 6. Exercises every CRUD helper, every JSON-column roundtrip, and FK cascade on case delete.

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

.\.venv\Scripts\python.exe -m pytest tests/test_subtype.py tests/test_seed_synthetic.py -q
```
> Originally verified via `scripts/smoke_stage3.py`; consolidated into the pytest suite in Stage 6.

### Unblocks
- Stage 5 vertical slice: `CaseCompiler` needs real (or synthetic) cases to compile from.
- All seven pre-meeting agents: their inputs (receptor status, stage, treatments, genomics, image paths) all come from these tables.

---

## Stage 4 — Agent framework
- **Branch:** `feature/agent-framework` (cut from `feature/data-seeding`)
- **Commit:** `d7e6b96`
- **Landed:** 2026-05-14
- **PR:** https://github.com/RaneemK-commits/OncoBoard.ai/pull/new/feature/agent-framework

### What landed
| File | Purpose |
|---|---|
| `src/agents/types.py` | `ModelTier` literal, `GeminiResponse` dataclass, `AgentError` / `CaseNotFoundError` / `AgentOutputValidationError` |
| `src/agents/gemini_client.py` | `GeminiClient` Protocol; `RealGeminiClient` (async google-genai with retry+backoff and structured-output support); `MockGeminiClient` (FIFO queue + `.calls` recorder); `get_gemini_client()` factory honoring `GEMINI_MOCK` and missing API key |
| `src/agents/base.py` | `BaseAgent[TOutput]` abstract class. Subclasses set `name` / `model_tier` / `output_schema` and implement `run()`. The framework loads the case, validates output, persists to `agent_outputs` (success or error), and logs duration + tokens |
| `scripts/smoke_stage4.py` | 7 checks: ClassVar enforcement, happy path, missing case, schema mismatch, subclass exception, mock call recording, run_id grouping |

### Decisions worth knowing
- **One lifecycle, owned by `BaseAgent.execute()`.** Subclasses cannot accidentally skip persistence or logging — the wrapper handles both. This is the single point where all 13 agents will agree on lifecycle, so getting it right means each agent file becomes a thin specialist implementation.
- **Errors are first-class.** Any subclass exception or schema-validation failure writes a `status='error'` row to `agent_outputs` (with the error message) before re-raising. Audit trail never loses a run.
- **ClassVar omissions fail at class-definition time** via `__init_subclass__`, not at first `execute()`. Faster feedback for agent authors.
- **Tokens accumulate per `execute()`.** Agents that call Gemini multiple times in one run get a single `tokens_used` total persisted. `BaseAgent.call_gemini()` is the helper that drives the accumulator.
- **`MockGeminiClient` is injectable per-agent** (`Agent(gemini=mock)`), so tests don't need monkeypatching. The mock records every call on `.calls` for assertions.
- **No real Gemini call is required to build agents.** `GEMINI_MOCK=1` (or an empty API key) routes everything through the mock, letting dev and CI run without API quota.

### Verify locally
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_agents.py -q
```
> Originally verified via `scripts/smoke_stage4.py`; consolidated into the pytest suite in Stage 6.

### Unblocks
- Stage 5 vertical slice — `CaseCompiler` and `SummaryAgent` are now just two thin `BaseAgent` subclasses plus an SSE route.
- The remaining 11 pre/during/post-meeting agents are template work.

---

## Stage 5 — Pre-meeting vertical slice
- **Branch:** `feature/stage-5-vertical-slice` (cut from `master`)
- **Commit:** `15be644` (squash-merged via PR #10)
- **Landed:** 2026-05-15
- **PR:** https://github.com/RaneemK-commits/OncoBoard.ai/pull/10

### What landed
| File | Purpose |
|---|---|
| `src/agents/case_compiler.py` | DB-only agent: assembles clinical bundle + genomics summary (notable breast-cancer gene panel) + file inventory; flags critical/warning data gaps; sets `ready_for_review` |
| `src/agents/summary_agent.py` | Consumes the latest CaseCompiler output, prompts Gemini with a strict JSON response schema, returns a structured one-page narrative. Hard-fails if CaseCompiler hasn't run |
| `src/agents/pipeline.py` | `run_pre_meeting()` — runs both agents under one shared `run_id`, yields `PipelineEvent`s for SSE. Hardcoded order per ARCHITECTURE.md |
| `src/api/pipeline.py` | `POST /cases/{id}/pre-meeting/run` → `StreamingResponse` `text/event-stream`; 404 on missing case; opens its own DB connection for the stream lifetime |
| `src/main.py` | Mounts pipeline router; widened CORS to allow `POST` (was GET-only) |
| `src/db/repository.py` | New `get_genomics_any()` — source-agnostic lookup |
| `scripts/smoke_stage5.py` | 3-phase end-to-end test |
| `scripts/db_status.py` | sqlite-only DB inspector for setup debugging |

### Decisions worth knowing
- **Read-only case endpoints were already delivered** by a teammate in `src/api/cases.py` (incl. `/agents/{name}/latest`), so this slice is agents + pipeline + SSE only — not the full original plan.
- **`src/api/pipeline.py` opens its own DB connection inside the stream generator.** The request-scoped `get_db()` connection is torn down when the handler returns — before SSE finishes streaming — so relying on it would break mid-stream.
- **Flat `src/api/` convention** (not nested `src/api/routes/`) to match the teammate's existing `cases.py`.
- **CORS was GET-only** before this — the SSE route is `POST`, so the browser preflight would have blocked the frontend. Fixed here.

### Bugs caught during the slice
- **CaseCompiler genomics blind spot:** it called `repo.get_genomics()` which defaults to `source="CNV_RAW"`, so every synthetic-seeded case (`source="synthetic"`) reported "no genomics." Fixed with the source-agnostic `get_genomics_any()`.

### Verify locally
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_pipeline_api.py -q
```
> Originally verified via `scripts/smoke_stage5.py`; consolidated into the pytest suite in Stage 6.
Or run it live: `uvicorn src.main:app` then `POST /cases/SYN-002/pre-meeting/run` and watch the SSE events stream.

### Unblocks
- The remaining 11 agents (pre/during/post-meeting) are now template work against `BaseAgent` + the pipeline runner pattern.
- Stage 6 (test infrastructure) — the smoke tests become the seed for the pytest suite.

---

## Stage 6 — Test infrastructure
- **Branch:** `feature/stage-6-test-infra` (cut from `master`)
- **Landed:** 2026-05-15
- **PR:** #13

### What landed
| File | Purpose |
|---|---|
| `tests/conftest.py` | Shared fixtures: isolated temp DB (`DB_PATH` + cache clear + schema init), `seeded_db` (4 synthetic cases), `mock_gemini`, httpx ASGI `client`. Forces `GEMINI_MOCK=1` + empty API key |
| `tests/test_subtype.py` | Classifier rules (parametrized) — pure unit, no DB |
| `tests/test_repository.py` | CRUD roundtrips, JSON columns, `get_genomics_any`, FK cascade |
| `tests/test_seed_synthetic.py` | Seed coverage, idempotency, genomics blob lookup |
| `tests/test_agents.py` | BaseAgent lifecycle (ClassVar enforcement, error/success persistence, tokens, run_id) + CaseCompiler + SummaryAgent |
| `tests/test_pipeline_api.py` | Pipeline event order/run_id, SSE route over httpx (200 stream + 404), failure propagation, read-only endpoints, /health |

### Decisions worth knowing
- **38 tests, ~2.7s, zero API calls.** Everything runs through `MockGeminiClient`; CI needs no `GEMINI_API_KEY`.
- **Function-scoped isolation.** Each test gets its own temp SQLite file via `tmp_path` + `monkeypatch`; the memoized `get_settings` cache and Gemini client singleton are cleared before *and* after each test.
- **Smoke scripts deleted.** `scripts/smoke_stage2-5.py` are fully superseded — keeping duplicate test logic in two places invites drift. `scripts/db_status.py` stays (it's a diagnostic, not a test). Per-stage "Verify locally" blocks above now point at the equivalent `pytest` module.

### Verify locally
```powershell
.\.venv\Scripts\python.exe -m pytest -q
# Expected: "38 passed"
```

### Unblocks
- The pipeline extension (remaining 11 agents) now lands on a tested foundation — new agents add test modules instead of accumulating untested surface.

---

## Post-plan work — full 14-agent pipeline + hardening

The original 6-stage plan delivered the foundation through a working vertical
slice. Everything below landed after, completing the system to all 14 agents
across the three phases plus the human gates. The pre/during-meeting agents
and the Vue frontend were largely contributed by a teammate (Lukas); the
items below are the backend completion + hardening done here.

### CI on push — PR #14
GitHub Actions runs `pytest -q` (Ubuntu, Python 3.13, pip-cached) on every
push and on PRs to master. Fully mocked suite — no `GEMINI_API_KEY` or
secrets. It caught a real mid-stream regression within a day.

### Module-naming consistency — PRs #16, #17
Standardized agent modules to PascalCase (matching the majority in
`src/agents/`) and fixed the `HistoyCaseAgent.py` → `HistoryCaseAgent.py`
filename typo (the class was always spelled correctly; only the file +
its one import were wrong). `git mv`, history preserved, no behavior change.

### TrialAgent ClinicalTrials.gov v2 robustness — PR #18
Added an identifying `User-Agent` + `Accept` header (the default
`python-httpx` UA gets 403'd by CT.gov's edge, silently returning zero
trials for every patient) and dropped the brittle legacy `fields` param.
Added `tests/test_trial_agent.py` against a realistic mocked v2 payload —
the agent's success path had never been exercised before.

### Test-coverage backfill — PRs #19, #20
Happy-path coverage for the 5 parallel pre-meeting agents (previously only
their error path was tested, since `test_pipeline_api` deliberately fails
them all) and full route coverage for `src/api/meeting.py` (session
create, transcribe SSE, audio upload, recommend, status patch).

### Post-meeting phase — PR #21
The final 4 agents + orchestration + human gates. See the dedicated entry
below.

---

## Post-meeting phase
- **Branch:** `feature/post-meeting-phase`
- **Commit:** `b2b2289` (PR #21)
- **Landed:** 2026-05-17

### What landed
| File | Purpose |
|---|---|
| `src/agents/NoteDraftAgent.py` | Pro. Transcript + confirmed RecommendationAgent output → structured `TumorBoardNote` for EHR entry |
| `src/agents/ActionDispatchAgent.py` | Flash. Parses the recommendation into action items, writes each to the `actions` table, returns persisted ids |
| `src/agents/FollowUpAgent.py` | Flash. Deterministic overdue detection (due_date vs today) over `actions`; Gemini only authors the escalation note |
| `src/agents/SchedulingAgent.py` | Flash. Flags whether the case needs re-presentation at a future board |
| `src/agents/post_meeting_pipeline.py` | Phase A `NoteDraft‖ActionDispatch`, then Phase B `FollowUp‖Scheduling`; per-agent failures non-fatal |
| `src/api/post_meeting.py` | `gate2/confirm` (Human Gate 2), `post-meeting/run` (SSE), `gate3/approve` (Human Gate 3) |
| `tests/test_post_meeting.py` | 9 tests: agent happy paths, recommendation prereq, deterministic overdue, pipeline order, Gate-2 enforcement, full gate2→SSE→gate3 flow, 404s |

### Decisions worth knowing
- **Human Gate 2 is a hard stop.** `POST /sessions/{id}/post-meeting/run` returns **409** unless a `consensus_confirmed` gate row exists for the session — enforces ARCHITECTURE.md §2 ("post-meeting agents never run before Human Gate 2") at the API boundary, not just by convention.
- **Phase B depends on Phase A's writes.** FollowUp/Scheduling read the `actions` ActionDispatch writes, so the two phases are sequential even though agents within each phase fan out in parallel.
- **Confirmed recommendation read via `get_latest_agent_output`** — no `repository.py` change needed; avoids adding a `get_recommendation` helper.
- **FollowUp overdue logic is deterministic**, not model-authored — date math over the actions table is fed to Gemini, which only writes the escalation narrative. Keeps the overdue facts testable and trustworthy.
- **Parallel-agent tests use a schema-routing fake Gemini** (returns the payload matching the requested `response_schema`), so `asyncio.gather` scheduling can't make them flaky.

### Verify locally
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_post_meeting.py -q
```

### State
All 14 agents implemented across pre/during/post-meeting + 3 human gates.
**78 tests, CI-gated.** Backend is feature-complete.

---

## Up next
Backend is feature-complete and fully tested. Only remaining item: the
untracked `assets/agents/*.png` icon set (frontend art — needs a
deliberate commit if the Vue app uses it). Optional polish: make
`BaseAgent.model_tier` optional for the deterministic agents
(CaseCompiler/DisplayAgent) so they don't declare an unused tier.

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
