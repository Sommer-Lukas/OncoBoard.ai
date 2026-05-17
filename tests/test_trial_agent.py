"""TrialAgent — happy path against realistic mocked ClinicalTrials.gov v2
and PubMed responses, plus the v2 payload parser and the request headers.
"""
import json
import re

import pytest

from src.agents.gemini_client import MockGeminiClient
from src.agents.TrialAgent import TrialAgent, TrialOutput
from src.db import repository as repo
from src.db.models import Case

_NOW = "2026-05-17T00:00:00+00:00"

# A realistic ClinicalTrials.gov v2 /studies response.
_CT_V2_RESPONSE = {
    "studies": [
        {
            "protocolSection": {
                "identificationModule": {
                    "nctId": "NCT01234567",
                    "briefTitle": "Trastuzumab Deruxtecan in HER2+ Breast Cancer",
                },
                "statusModule": {"overallStatus": "RECRUITING"},
                "designModule": {"phases": ["PHASE2"]},
                "eligibilityModule": {
                    "eligibilityCriteria": "Inclusion: HER2-positive (IHC 3+). "
                    "Exclusion: prior anti-HER2 therapy in metastatic setting."
                },
                "descriptionModule": {
                    "briefSummary": "Evaluates T-DXd in HER2-positive disease."
                },
            }
        }
    ],
    "nextPageToken": "tok",
}

_ESEARCH = {"esearchresult": {"idlist": ["40000001"]}}
_ESUMMARY = {
    "result": {
        "40000001": {"title": "T-DXd phase II results", "source": "J Clin Oncol"}
    }
}

_GEMINI_JSON = json.dumps({
    "case_id": "TO-BE-OVERWRITTEN",
    "search_criteria": {},
    "trials_retrieved": 0,
    "matched_trials": [
        {
            "nct_id": "NCT01234567",
            "title": "Trastuzumab Deruxtecan in HER2+ Breast Cancer",
            "phase": "PHASE2",
            "overall_status": "RECRUITING",
            "eligibility_delta": "Patient is HER2+ IHC 3+ and treatment-naive in "
            "metastatic setting — appears eligible; confirm staging.",
            "brief_summary": "Evaluates T-DXd in HER2-positive disease.",
        }
    ],
    "pubmed_references": [],
    "agent_notes": "One recruiting HER2+ trial retrieved.",
})


async def _her2_case(db) -> str:
    await repo.upsert_case(db, Case(
        case_id="TCGA-TRIAL-01",
        age_at_diagnosis=49,
        er_status="Negative", pr_status="Negative", her2_status="Positive",
        molecular_subtype="HER2-enriched", ajcc_stage="Stage IIB",
        created_at=_NOW, updated_at=_NOW,
    ))
    return "TCGA-TRIAL-01"


def test_extract_trial_summaries_parses_v2_payload():
    agent = TrialAgent(gemini=MockGeminiClient())
    summaries = agent._extract_trial_summaries(_CT_V2_RESPONSE["studies"])
    assert len(summaries) == 1
    s = summaries[0]
    assert s["nct_id"] == "NCT01234567"
    assert s["title"].startswith("Trastuzumab Deruxtecan")
    assert s["phase"] == "PHASE2"
    assert s["overall_status"] == "RECRUITING"
    assert "HER2-positive" in s["eligibility_criteria"]
    assert s["brief_summary"].startswith("Evaluates T-DXd")


async def test_trial_agent_happy_path(db, httpx_mock):
    httpx_mock.add_response(
        url=re.compile(r".*/api/v2/studies\?.*"), method="GET", json=_CT_V2_RESPONSE
    )
    httpx_mock.add_response(
        url=re.compile(r".*esearch\.fcgi.*"), method="GET", json=_ESEARCH
    )
    httpx_mock.add_response(
        url=re.compile(r".*esummary\.fcgi.*"), method="GET", json=_ESUMMARY
    )

    case_id = await _her2_case(db)
    mock = MockGeminiClient()
    mock.queue(_GEMINI_JSON, tokens_used=256)

    out = await TrialAgent(gemini=mock).execute(db, case_id)

    assert isinstance(out, TrialOutput)
    assert out.case_id == case_id                       # forced by the agent
    assert out.trials_retrieved == 1                    # from parsed v2 payload
    assert len(out.matched_trials) == 1
    assert out.matched_trials[0].nct_id == "NCT01234567"
    # pubmed_references empty in the model output -> agent backfills from esummary
    assert [r.pmid for r in out.pubmed_references] == ["40000001"]
    assert out.pubmed_references[0].title == "T-DXd phase II results"
    assert out.search_criteria["her2_status"] == "Positive"

    # Persisted as a successful agent_output row.
    row = await repo.get_latest_agent_output(db, case_id, "TrialAgent")
    assert row.status == "success" and row.tokens_used == 256


async def test_trial_agent_sends_identifying_user_agent(db, httpx_mock):
    httpx_mock.add_response(url=re.compile(r".*/api/v2/studies\?.*"), json=_CT_V2_RESPONSE)
    httpx_mock.add_response(url=re.compile(r".*esearch\.fcgi.*"), json=_ESEARCH)
    httpx_mock.add_response(url=re.compile(r".*esummary\.fcgi.*"), json=_ESUMMARY)

    case_id = await _her2_case(db)
    mock = MockGeminiClient()
    mock.queue(_GEMINI_JSON, tokens_used=10)
    await TrialAgent(gemini=mock).execute(db, case_id)

    reqs = httpx_mock.get_requests()
    assert reqs, "expected outbound HTTP requests"
    ct_req = next(r for r in reqs if "/api/v2/studies" in str(r.url))
    assert ct_req.headers["user-agent"].startswith("OncoBoard.ai/")
    # The legacy v1 `fields` param must no longer be sent.
    assert "fields=" not in str(ct_req.url)


async def test_trial_agent_degrades_when_ctgov_unavailable(db, httpx_mock):
    httpx_mock.add_response(url=re.compile(r".*/api/v2/studies\?.*"), status_code=403)
    httpx_mock.add_response(url=re.compile(r".*esearch\.fcgi.*"), json={"esearchresult": {"idlist": []}})

    case_id = await _her2_case(db)
    mock = MockGeminiClient()
    mock.queue(json.dumps({
        "case_id": "x", "search_criteria": {}, "trials_retrieved": 0,
        "matched_trials": [], "pubmed_references": [],
        "agent_notes": "No trials retrieved (ClinicalTrials.gov unavailable).",
    }), tokens_used=5)

    out = await TrialAgent(gemini=mock).execute(db, case_id)
    assert out.trials_retrieved == 0
    assert out.matched_trials == []
    row = await repo.get_latest_agent_output(db, case_id, "TrialAgent")
    assert row.status == "success"  # graceful degradation, not an error
