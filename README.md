<p align="center">
  <img src="docs/assets/cover.png" alt="OncoBoard.ai" width="300" />
</p>

<h1 align="center">OncoBoard.ai</h1>

<p align="center"><em>AI that prepares. Experts that decide. Patients that win.</em></p>

<p align="center">
  <img alt="Python 3.11+" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white">
  <img alt="SQLite" src="https://img.shields.io/badge/SQLite-003B57?logo=sqlite&logoColor=white">
  <img alt="Google Gemini" src="https://img.shields.io/badge/Google_Gemini-8E75B2?logo=google&logoColor=white">
  <img alt="Vue.js 3" src="https://img.shields.io/badge/Vue.js_3-4FC08D?logo=vuedotjs&logoColor=white">
  <img alt="License MIT" src="https://img.shields.io/badge/License-MIT-yellow.svg">
  <img alt="Status" src="https://img.shields.io/badge/Status-Research%20Prototype-orange">
</p>

---

## What this is

Breast cancer tumor boards are where multidisciplinary specialists decide treatment for each patient — and they typically take **eight hours of preparation per case**. OncoBoard.ai runs a coordinated team of AI agents that compiles the case, surfaces guidelines, finds matching trials, retrieves analogous past cases, transcribes the meeting, and drafts the note.

**Clinicians make every decision.** The agents just remove the eight hours of busywork.

> **From 8 hours to 90 seconds.**

---

## How it works

Three phases, fourteen specialist agents, three explicit human gates that are hard stops in the pipeline.

### 1. Pre-Meeting — seven agents run in parallel
Before the board convenes, agents pull the patient record, interpret the imaging in BI-RADS language, read the genomic + biopsy data, match NCCN/ESMO guidelines, find recruiting clinical trials, retrieve analogous past cases by semantic similarity, and synthesize everything into a one-page case narrative.
**→ Human Gate 1: Review & Approve.**

### 2. During Meeting — live capture
The display agent formats the prepared case for the room in real time. A transcription agent turns live audio into a speaker-tagged transcript. A recommendation agent reads the transcript stream and captures decision moments as the consensus emerges.
**→ Human Gate 2: Consensus Confirmed.**

### 3. Post-Meeting — note + action items
A note-draft agent produces a structured tumor board note ready for EHR entry. An action-dispatch agent extracts follow-ups, assigns owners, and sets due dates. A follow-up agent tracks completion and escalates overdue items. A scheduling agent flags cases needing re-presentation.
**→ Human Gate 3: Approve Note.**

---

## Agent roster

| Phase | Agent | Model | Role |
|---|---|---|---|
| Pre | `CaseCompiler` | Flash | Pulls records, flags missing data |
| Pre | `RadiologyAgent` | Vision | Imaging findings in BI-RADS |
| Pre | `PathologyAgent` | Pro | Biopsy + genomic interpretation (CAP synoptic format) |
| Pre | `GuidelineAgent` | Pro | NCCN / ESMO protocol match |
| Pre | `TrialAgent` | Flash | ClinicalTrials.gov + PubMed eligibility match |
| Pre | `HistoryCaseAgent` | Pro + embeddings | Analogous past cases by semantic similarity |
| Pre | `SummaryAgent` | Flash | One-page clinical narrative |
| Live | `DisplayAgent` | (formatting only) | Real-time case display to the room |
| Live | `TranscriptionAgent` | Flash | Speaker-tagged transcript |
| Live | `RecommendationAgent` | Pro | Decision-moment capture |
| Post | `NoteDraftAgent` | Pro | Tumor board note |
| Post | `ActionDispatchAgent` | Flash | Action items + owners + due dates |
| Post | `FollowUpAgent` | Flash | Overdue-item tracking |
| Post | `SchedulingAgent` | Flash | Re-presentation flagging |

---

## Quickstart

```powershell
git clone https://github.com/RaneemK-commits/OncoBoard.ai.git
cd OncoBoard.ai

# Virtualenv + deps
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt

# Environment
cp .env.example .env       # fill GEMINI_API_KEY, or set GEMINI_MOCK=1 for offline dev

# Initialize the DB and seed with synthetic data (4 hand-crafted cases, instant)
.\.venv\Scripts\python.exe -m src.db.init_db
.\.venv\Scripts\python.exe -m src.data.seed_synthetic

# OR seed the real TCGA-BRCA dataset (~1,097 cases, needs Kaggle CSVs in data/raw/)
.\.venv\Scripts\python.exe -m src.data.seed_tcga

# Run the API
uvicorn src.main:app --reload
# GET http://localhost:8000/health -> {"status":"ok"}
```

Dataset download instructions: [`src/data/README.md`](src/data/README.md).

---

## Project structure

```
src/
  agents/          # Agent framework: BaseAgent, GeminiClient, MockGeminiClient
  api/             # FastAPI routes (Stage 5)
  data/            # Seed scripts + synthetic fixtures + subtype classifier
  db/              # Schema, Pydantic models, repository (all raw SQL lives here)
  config.py        # pydantic-settings Settings
  logging_setup.py # JSON structured logger
  main.py          # FastAPI app factory
docs/
  BUILD_LOG.md     # Stage-by-stage history with smoke-test commands
  assets/          # Cover art and other static images
scripts/           # One-off smoke tests per stage
frontend/          # Vue.js 3 app (separate workstream)
ARCHITECTURE.md    # System diagram + components + key decisions
CLAUDE.md          # Project conventions for AI collaborators
Branding.md        # Design tokens — colors, typography, spacing
```

---

## Build status

| Stage | Theme | Status |
|---|---|---|
| 1 | Backend foundation (config, logging, FastAPI app) | ✅ |
| 2 | DB layer (schema, models, repository, init) | ✅ |
| 3 | Data seeding (synthetic + TCGA-BRCA) | ✅ |
| 4 | Agent framework (BaseAgent + MockGeminiClient) | ✅ |
| 5 | Vertical slice: CaseCompiler + SummaryAgent + SSE route | ⏳ |
| 6 | Test infrastructure (pytest + mocked Gemini) | ⏳ |

Full stage-by-stage detail — file lists, decisions, smoke-test commands — in [`docs/BUILD_LOG.md`](docs/BUILD_LOG.md).

---

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| API | FastAPI + Server-Sent Events | Agent output is strictly server → client; SSE avoids WebSocket complexity |
| DB | SQLite (aiosqlite) | Fixed ~1,000-case research corpus; trivially deployable; one-line switch to Postgres if it scales |
| LLM | Google Gemini (Pro / Flash / Vision) | Tiered per agent — Pro for clinical interpretation, Flash for structured extraction |
| Frontend | Vue.js 3 + Pinia | Three views map 1:1 to the three pipeline phases |
| Data | TCGA-BRCA (Kaggle) | Public research dataset — ~1,097 patients with clinical + genomic + imaging |

Trade-offs documented in [`ARCHITECTURE.md`](ARCHITECTURE.md) §4.

---

## Important: this is a research prototype

OncoBoard.ai is **not** clinical software. It has no HIPAA infrastructure, no real EHR integration, no DICOM/PACS connectivity, no authentication, and no audit logging beyond development-grade tracing. The genomic data is research-grade — not clinical-grade (e.g. Foundation Medicine FoundationOne CDx). The history-case lookup runs against the same public dataset, not a hospital's own prior decisions.

**Do not use with real patient data.** The full limitations list is in [`ARCHITECTURE.md`](ARCHITECTURE.md) §5.

---

## Documentation

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — System diagram, components, key decisions, limitations
- [`docs/BUILD_LOG.md`](docs/BUILD_LOG.md) — What's landed, when, why, how to verify
- [`src/data/README.md`](src/data/README.md) — Dataset download + seed instructions
- [`Branding.md`](Branding.md) — Design tokens (colors, typography, spacing) for the frontend
- [`CLAUDE.md`](CLAUDE.md) — Conventions for AI collaborators contributing to this codebase

---

## License

MIT — see [`LICENSE`](LICENSE).
