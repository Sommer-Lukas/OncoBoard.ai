"""Happy-path coverage for the parallel pre-meeting agents.

These were never asserted before: test_pipeline_api deliberately makes all
five fail validation, so their success output went untested. Each agent
follows the same shape (build prompt -> call_gemini -> json -> validate),
so a queued valid payload + persistence check is the meaningful assertion.
"""
import json

from src.agents.GuidelineAgent import GuidelineAgent, GuidelineOutput
from src.agents.gemini_client import MockGeminiClient
from src.agents.HistoryCaseAgent import HistoryCaseAgent, HistoryCaseOutput
from src.agents.PathologyAgent import PathologyAgent, PathologyOutput
from src.agents.RadiologyAgent import BiRadsFindings, RadiologyAgent
from src.db import repository as repo
from src.db.connection import connect
from src.db.models import Case

_NOW = "2026-05-17T00:00:00+00:00"


def _case(case_id="TCGA-PM-01", **ov) -> Case:
    base = dict(
        case_id=case_id, age_at_diagnosis=55,
        er_status="Positive", pr_status="Positive", her2_status="Negative",
        molecular_subtype="Luminal A", ajcc_stage="Stage IIA",
        ajcc_t="T2", ajcc_n="N0", ajcc_m="M0",
        histological_type="Infiltrating Ductal Carcinoma",
        created_at=_NOW, updated_at=_NOW,
    )
    base.update(ov)
    return Case(**base)


# ── RadiologyAgent ───────────────────────────────────────────────────────────

_BIRADS = json.dumps({
    "case_id": "x",
    "overall_birads_category": "BI-RADS 4B — Suspicious",
    "breast_density": "ACR C — Heterogeneously dense",
    "mass_findings": ["Irregular spiculated mass, upper outer quadrant"],
    "calcification_findings": ["Fine pleomorphic calcifications, segmental"],
    "associated_features": ["Skin thickening"],
    "comparison_with_prior": None,
    "radiologist_impression": "Findings suspicious for malignancy.",
    "imaging_modalities_reviewed": [],
    "data_gaps": ["No prior imaging available for comparison"],
})


async def test_radiology_agent_happy_path(db):
    await repo.upsert_case(db, _case())
    mock = MockGeminiClient()
    mock.queue(_BIRADS, tokens_used=180)

    out = await RadiologyAgent(gemini=mock).execute(db, "TCGA-PM-01")
    assert isinstance(out, BiRadsFindings)
    assert out.case_id == "TCGA-PM-01"
    assert out.overall_birads_category.startswith("BI-RADS 4B")
    # No files on disk -> text-only fallback (image_paths None).
    assert mock.calls[0]["model_tier"] == "vision"

    row = await repo.get_latest_agent_output(db, "TCGA-PM-01", "RadiologyAgent")
    assert row.status == "success" and row.tokens_used == 180


# ── PathologyAgent ───────────────────────────────────────────────────────────

_PATHOLOGY = json.dumps({
    "case_id": "x",
    "ihc_profile": {"ER": "Positive", "PR": "Positive", "HER2": "3+ (positive)"},
    "molecular_subtype_interpretation": "Luminal B (HER2-positive).",
    "driver_alterations": ["ERBB2 amplification — therapeutically actionable"],
    "prognostic_markers": ["High MYC copy number"],
    "synoptic_summary": "Invasive ductal carcinoma, ER+/PR+/HER2+, ERBB2 amplified.",
    "pathologist_comment": "HER2 amplification corroborated by CNV.",
    "data_gaps": [],
})


async def test_pathology_agent_uses_cnv_thresholds(seeded_db):
    # SYN-002 is HER2+ with synthetic CNV ERBB2=5.0 -> amplification rule fires.
    mock = MockGeminiClient()
    mock.queue(_PATHOLOGY, tokens_used=300)
    async with connect() as db:
        out = await PathologyAgent(gemini=mock).execute(db, "SYN-002")

    assert isinstance(out, PathologyOutput)
    assert out.case_id == "SYN-002"
    # The rule-based pre-classification (ERBB2 >= 2.5) must reach the prompt.
    assert "ERBB2 amplification" in mock.calls[0]["prompt"]
    assert mock.calls[0]["model_tier"] == "pro"

    async with connect() as db:
        row = await repo.get_latest_agent_output(db, "SYN-002", "PathologyAgent")
    assert row.status == "success" and row.tokens_used == 300


# ── GuidelineAgent ───────────────────────────────────────────────────────────

_GUIDELINE = json.dumps({
    "case_id": "x",
    "matched_guideline": "NCCN Breast Cancer v2.2025",
    "guideline_pathway": "HR+/HER2- Early Stage, Postmenopausal",
    "recommendation_category": "Preferred",
    "systemic_therapy_options": ["Adjuvant chemotherapy if high genomic risk"],
    "endocrine_therapy_options": ["Aromatase inhibitor x5y", "Tamoxifen"],
    "radiation_considerations": "Whole breast RT after lumpectomy.",
    "surgery_considerations": "Breast-conserving surgery appropriate.",
    "evidence_level": "Category 1",
    "protocol_rationale": "Stage IIA HR+/HER2- aligns with the endocrine pathway.",
    "data_gaps": ["Recurrence-risk genomic assay (Oncotype DX) not available"],
})


async def test_guideline_agent_happy_path(db):
    await repo.upsert_case(db, _case())
    mock = MockGeminiClient()
    mock.queue(_GUIDELINE, tokens_used=240)

    out = await GuidelineAgent(gemini=mock).execute(db, "TCGA-PM-01")
    assert isinstance(out, GuidelineOutput)
    assert out.case_id == "TCGA-PM-01"
    assert out.evidence_level == "Category 1"
    assert out.matched_guideline.startswith("NCCN")
    # Pure prompt agent — patient stage must be in the prompt.
    assert "Stage IIA" in mock.calls[0]["prompt"]

    row = await repo.get_latest_agent_output(db, "TCGA-PM-01", "GuidelineAgent")
    assert row.status == "success" and row.tokens_used == 240


# ── HistoryCaseAgent ─────────────────────────────────────────────────────────

_HISTORY = json.dumps({
    "case_id": "x",
    "analogous_cases": [
        {
            "case_id": "SYN-002",
            "similarity_rationale": "Same histology, adjacent stage.",
            "receptor_match": "Both hormone-receptor positive",
            "stage_match": "Adjacent AJCC stage",
            "treatment_summary": "Multi-agent chemo + endocrine",
            "outcome_note": "Alive, with tumor",
        }
    ],
    "search_basis": "SQL profile match on molecular_subtype + AJCC stage",
    "agent_notes": "Selected the closest analogue from seeded cohort.",
})


async def test_history_case_agent_happy_path(seeded_db):
    mock = MockGeminiClient()
    mock.queue(_HISTORY, tokens_used=260)
    async with connect() as db:
        out = await HistoryCaseAgent(gemini=mock).execute(db, "SYN-001")

    assert isinstance(out, HistoryCaseOutput)
    assert out.case_id == "SYN-001"
    assert out.analogous_cases[0].case_id == "SYN-002"
    # Candidate set must exclude the target case itself.
    assert "SYN-001" not in mock.calls[0]["prompt"].split("Candidate analogous")[1]

    async with connect() as db:
        row = await repo.get_latest_agent_output(db, "SYN-001", "HistoryCaseAgent")
    assert row.status == "success"


async def test_history_case_agent_no_candidates_skips_gemini(db):
    # Only the target case in the DB -> deterministic empty result, no LLM call.
    await repo.upsert_case(db, _case("LONELY-01"))
    mock = MockGeminiClient()
    out = await HistoryCaseAgent(gemini=mock).execute(db, "LONELY-01")

    assert out.analogous_cases == []
    assert mock.calls == []  # short-circuited before any Gemini call
    row = await repo.get_latest_agent_output(db, "LONELY-01", "HistoryCaseAgent")
    assert row.status == "success"
