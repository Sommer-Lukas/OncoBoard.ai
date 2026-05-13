# CLAUDE.md — OncoBoard.ai

## What This Is
Multi-agent AI system for breast cancer tumor boards. Agents handle all prep and follow-up. Clinicians make every decision.

## Stack
- Python, SQLite, Vue.js 3, Gemini API

## The Three Phases

### Pre-Meeting
Agents run in parallel before the board convenes:
- **CaseCompiler** — pulls records, flags missing data
- **SummaryAgent** — structured clinical case narrative
- **RadiologyAgent** — imaging findings in radiologist language (BI-RADS)
- **PathologyAgent** — biopsy/genomic interpretation in CAP synoptic format
- **GuidelineAgent** — NCCN/ESMO protocol match for stage + receptor status
- **TrialAgent** — active breast cancer trial eligibility match + evidence retrieval
  - ClinicalTrials.gov API for open trials (filter: breast cancer, recruiting)
  - NCBI PubMed E-utilities API for supporting literature (`esearch` + `efetch`)
  - Match on: receptor status (ER/PR/HER2), stage, prior treatments, age
  - Output: trial ID + phase + eligibility delta + top 2–3 PubMed PMIDs as evidence
- **HistoryCaseAgent** — analogous past cases from local DB

### During Meeting
- **DisplayAgent** — serves formatted case to the room in real time
- **TranscriptionAgent** — live audio → structured transcript with speaker tags
- **RecommendationAgent** — captures decision moments from transcript stream

### Post-Meeting
- **NoteDraftAgent** — drafts tumor board note from transcript + decisions
- **ActionDispatchAgent** — parses action items, assigns owners, writes to DB
- **FollowUpAgent** — tracks completion, escalates overdue items
- **SchedulingAgent** — flags cases needing re-presentation

## Agent Rules
1. Each agent has a specialist persona — RadiologyAgent speaks like a radiologist, PathologyAgent uses pathologist language
2. Agents surface information; they never output a final clinical recommendation
3. Structured output only — typed dicts, not raw strings
4. All DB writes go through a single models layer, never raw SQL in agents

## Dataset
Kaggle: `breast-cancer-vision-and-genomic-fusion-ml-ready`
Genomic columns → PathologyAgent + TrialAgent
Imaging columns → RadiologyAgent
Seed into SQLite once on setup; agents always query DB, never raw CSV
