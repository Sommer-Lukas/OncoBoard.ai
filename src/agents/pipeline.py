"""Pre-meeting pipeline runner.

Stage 5 vertical slice: CaseCompiler then SummaryAgent, under one shared
`run_id`. Yields a structured event after each agent so an SSE route can
stream progress to the frontend. This is the template the remaining
pre-meeting agents will plug into.
"""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass
from typing import Any, AsyncIterator

import aiosqlite

from src.agents.case_compiler import CaseCompiler
from src.agents.gemini_client import GeminiClient
from src.agents.summary_agent import SummaryAgent
from src.agents.types import AgentError
from src.logging_setup import get_logger

logger = get_logger(__name__)


@dataclass
class PipelineEvent:
    event: str          # "agent" | "pipeline"
    agent: str | None   # agent name, or None for pipeline-level events
    status: str         # "running" | "done" | "error" | "complete"
    run_id: str
    data: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


async def run_pre_meeting(
    db: aiosqlite.Connection,
    case_id: str,
    *,
    gemini: GeminiClient | None = None,
) -> AsyncIterator[PipelineEvent]:
    """Execute the pre-meeting slice, yielding progress events.

    Ordering is deterministic and hardcoded (SummaryAgent depends on
    CaseCompiler) — see ARCHITECTURE.md "Hardcoded orchestration".
    """
    run_id = str(uuid.uuid4())
    agents = [CaseCompiler(gemini=gemini), SummaryAgent(gemini=gemini)]

    logger.info(
        "pipeline_start",
        extra={"extra_fields": {
            "event": "pipeline_start", "case_id": case_id, "run_id": run_id,
        }},
    )

    for agent in agents:
        yield PipelineEvent("agent", agent.name, "running", run_id)
        try:
            output = await agent.execute(db, case_id, run_id=run_id)
        except AgentError as e:
            yield PipelineEvent(
                "agent", agent.name, "error", run_id, {"error": str(e)}
            )
            yield PipelineEvent(
                "pipeline", None, "error", run_id,
                {"failed_agent": agent.name, "error": str(e)},
            )
            return
        yield PipelineEvent(
            "agent", agent.name, "done", run_id, output.model_dump()
        )

    logger.info(
        "pipeline_complete",
        extra={"extra_fields": {
            "event": "pipeline_complete", "case_id": case_id, "run_id": run_id,
        }},
    )
    yield PipelineEvent("pipeline", None, "complete", run_id, {"case_id": case_id})
