"""ClinicalContextAgent — conversational RAG agent.

Not a BaseAgent subclass: it is stateless and multi-turn rather than a
one-shot pipeline step. It builds a rich system prompt from all available
DB context for a case (clinical record, agent outputs, transcripts, actions)
and answers clinician questions via Gemini Pro.

Conversation history is supplied by the caller on every request (client-side
state). The agent never writes to the DB.
"""
from __future__ import annotations

import json
from typing import Literal

import aiosqlite

from src.agents.gemini_client import GeminiClient, get_gemini_client
from src.db import repository as repo

Phase = Literal["pre", "mid", "post"]

AGENT_NAMES = [
    "CaseCompiler",
    "SummaryAgent",
    "RadiologyAgent",
    "PathologyAgent",
    "GuidelineAgent",
    "TrialAgent",
    "HistoryCaseAgent",
    "NoteDraftAgent",
    "ActionDispatchAgent",
    "FollowUpAgent",
    "SchedulingAgent",
]

SYSTEM_PREAMBLE = """\
You are a clinical decision-support assistant embedded in OncoBoard.ai, a \
multidisciplinary breast cancer tumor board system. You have access to all \
available data for the patient currently under discussion. Your role is to \
answer questions from clinicians — oncologists, radiologists, pathologists, \
surgeons, and coordinators — clearly and concisely, grounding every answer \
in the patient context provided below.

Rules:
- Never fabricate clinical data. If information is not in the context, say so.
- Never make a final clinical recommendation or treatment decision; surface \
  relevant information and flag uncertainty.
- Keep answers focused and clinically precise.
- Use appropriate medical language for a specialist audience.
- If asked about something outside this patient's data, say you can only \
  answer questions about the current case.
"""


class ClinicalContextAgent:
    """Stateless conversational RAG. One instance is fine to reuse across requests."""

    def __init__(self, gemini: GeminiClient | None = None) -> None:
        self.gemini = gemini or get_gemini_client()

    async def chat(
        self,
        db: aiosqlite.Connection,
        case_id: str,
        messages: list[dict],  # [{"role": "user"|"assistant", "content": str}, ...]
        phase: Phase = "pre",
    ) -> str:
        context = await self._build_context(db, case_id, phase)
        prompt = self._build_prompt(context, messages)
        resp = await self.gemini.generate(
            model_tier="pro",
            prompt=prompt,
            system_instruction=SYSTEM_PREAMBLE,
        )
        return resp.text.strip()

    # ── private ───────────────────────────────────────────────────────────────

    async def _build_context(self, db: aiosqlite.Connection, case_id: str, phase: Phase) -> str:
        parts: list[str] = []

        # Clinical record
        case = await repo.get_case(db, case_id)
        if case:
            parts.append(_section("PATIENT RECORD", _format_case(case)))

        # Agent outputs (all that exist for this case)
        for agent_name in AGENT_NAMES:
            output = await repo.get_latest_agent_output(db, case_id, agent_name)
            if output and output.output:
                parts.append(_section(f"AGENT OUTPUT — {agent_name}", json.dumps(output.output, indent=2)))

        # Mid/post: session transcripts
        if phase in ("mid", "post"):
            # Find the most recent session for this case
            cur = await db.execute(
                "SELECT session_id FROM sessions WHERE case_id = ? ORDER BY started_at DESC LIMIT 1",
                (case_id,),
            )
            row = await cur.fetchone()
            if row:
                session_id = row["session_id"]
                transcripts = await repo.list_transcripts(db, session_id)
                if transcripts:
                    lines = [f"[{t.timestamp_ms // 1000}s] {t.speaker}: {t.text}" for t in transcripts]
                    parts.append(_section("MEETING TRANSCRIPT", "\n".join(lines)))

        # Post: actions
        if phase == "post":
            cur = await db.execute(
                "SELECT a.owner, a.description, a.due_date, a.status FROM actions a JOIN sessions s ON a.session_id = s.session_id WHERE s.case_id = ? ORDER BY a.created_at",
                (case_id,),
            )
            rows = await cur.fetchall()
            if rows:
                action_lines = [
                    f"- [{r['status']}] {r['description']} → {r['owner']} (due {r['due_date']})"
                    for r in rows
                ]
                parts.append(_section("OPEN ACTIONS", "\n".join(action_lines)))

        return "\n\n".join(parts) if parts else "No case data available yet."

    @staticmethod
    def _build_prompt(context: str, messages: list[dict]) -> str:
        history_parts: list[str] = []
        for m in messages[:-1]:  # all but the last (which is the new user question)
            role = "Clinician" if m["role"] == "user" else "Assistant"
            history_parts.append(f"{role}: {m['content']}")

        history_block = "\n".join(history_parts)
        user_question = messages[-1]["content"] if messages else ""

        sections = [f"=== PATIENT CONTEXT ===\n{context}"]
        if history_block:
            sections.append(f"=== CONVERSATION HISTORY ===\n{history_block}")
        sections.append(f"=== CLINICIAN QUESTION ===\n{user_question}")
        return "\n\n".join(sections)


# ── formatting helpers ────────────────────────────────────────────────────────

def _section(title: str, body: str) -> str:
    return f"--- {title} ---\n{body}"


def _format_case(case) -> str:
    fields = {
        "Case ID": case.case_id,
        "Age at diagnosis": case.age_at_diagnosis,
        "AJCC Stage": case.ajcc_stage,
        "T/N/M": f"{case.ajcc_t}/{case.ajcc_n}/{case.ajcc_m}",
        "Histological type": case.histological_type,
        "ER status": case.er_status,
        "PR status": case.pr_status,
        "HER2 status": case.her2_status,
        "Molecular subtype": case.molecular_subtype,
        "Menopause status": case.menopause_status,
        "Surgical procedure": case.surgical_procedure,
        "Margin status": case.margin_status,
        "Lymph nodes examined": case.lymph_nodes_examined,
        "Vital status": case.vital_status,
    }
    return "\n".join(f"{k}: {v}" for k, v in fields.items() if v is not None)
