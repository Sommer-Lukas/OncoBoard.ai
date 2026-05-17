"""SummaryAgent — synthesizes the CaseCompiler bundle into a one-page narrative.

Depends on CaseCompiler having already run in the same pipeline. It reads the
latest CaseCompiler output from `agent_outputs`, prompts Gemini with a strict
JSON response schema, and returns a structured narrative.
"""
from __future__ import annotations

import json

import aiosqlite
from pydantic import BaseModel, ValidationError

from src.agents.base import BaseAgent
from src.agents.types import AgentError
from src.db import repository as repo
from src.db.models import Case

_SYSTEM = (
    "You are a breast cancer tumor board coordinator. Given a compiled case "
    "bundle, write a concise, factual one-page clinical narrative for the board. "
    "Do not make treatment recommendations — surface information only. "
    "Respond strictly as JSON matching the provided schema."
)


class SummaryOutput(BaseModel):
    case_id: str
    narrative: str
    key_points: list[str]
    data_gaps_flagged: list[str]


class SummaryAgent(BaseAgent[SummaryOutput]):
    name = "SummaryAgent"
    model_tier = "flash"
    output_schema = SummaryOutput

    async def run(
        self, db: aiosqlite.Connection, case: Case, *, run_id: str
    ) -> SummaryOutput:
        compiled = await repo.get_latest_agent_output(db, case.case_id, "CaseCompiler")
        if compiled is None or compiled.status != "success":
            raise AgentError(
                "SummaryAgent requires a successful CaseCompiler output; "
                "run the pre-meeting pipeline so CaseCompiler executes first"
            )

        prompt = (
            "Compiled case bundle (JSON):\n"
            f"{json.dumps(compiled.output, indent=2)}\n\n"
            "Produce: a `narrative` (one page, plain clinical prose), "
            "`key_points` (3-6 bullet strings), and `data_gaps_flagged` "
            "(echo the human-relevant gaps from the bundle)."
        )

        resp = await self.call_gemini(
            prompt=prompt,
            system_instruction=_SYSTEM,
            response_schema=SummaryOutput,
        )

        try:
            payload = json.loads(resp.text)
        except json.JSONDecodeError as e:
            raise AgentError(
                f"SummaryAgent could not parse Gemini response as JSON: {e}"
            ) from e

        # Force the case_id rather than trusting the model to echo it.
        payload["case_id"] = case.case_id
        try:
            return SummaryOutput.model_validate(payload)
        except ValidationError as e:
            raise AgentError(
                f"Gemini response did not match SummaryOutput schema: {e}"
            ) from e
