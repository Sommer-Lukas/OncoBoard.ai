"""Pre-meeting pipeline runner.

Execution order (matches ARCHITECTURE.md §3):
  1. CaseCompiler       — sequential, no LLM, required (fatal on error)
  2. RadiologyAgent     ┐
     PathologyAgent     │ parallel — all five run concurrently with asyncio.gather
     GuidelineAgent     │ non-fatal: pipeline continues even if one fails
     TrialAgent         │
     HistoryCaseAgent   ┘
  3. SummaryAgent       — sequential, requires CaseCompiler output (fatal on error)

Yields a PipelineEvent after each state change so an SSE route can stream
progress to the frontend.
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import asdict, dataclass
from typing import Any, AsyncIterator

import aiosqlite

from src.agents.CaseCompiler import CaseCompiler
from src.agents.gemini_client import GeminiClient
from src.agents.GuidelineAgent import GuidelineAgent
from src.agents.HistoyCaseAgent import HistoryCaseAgent
from src.agents.PathologyAgent import PathologyAgent
from src.agents.RadiologyAgent import RadiologyAgent
from src.agents.SummaryAgent import SummaryAgent
from src.agents.TrialAgent import TrialAgent
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
    """Execute the full pre-meeting pipeline, yielding progress events.

    Ordering is deterministic and hardcoded — see ARCHITECTURE.md
    §4 "Hardcoded orchestration over LLM-as-router".
    """
    run_id = str(uuid.uuid4())

    logger.info(
        "pipeline_start",
        extra={"extra_fields": {
            "event": "pipeline_start", "case_id": case_id, "run_id": run_id,
        }},
    )

    # ── Step 1: CaseCompiler (sequential, required) ───────────────────────────
    compiler = CaseCompiler(gemini=gemini)
    yield PipelineEvent("agent", compiler.name, "running", run_id)
    try:
        compiler_output = await compiler.execute(db, case_id, run_id=run_id)
    except AgentError as e:
        yield PipelineEvent("agent", compiler.name, "error", run_id, {"error": str(e)})
        yield PipelineEvent(
            "pipeline", None, "error", run_id,
            {"failed_agent": compiler.name, "error": str(e)},
        )
        return
    yield PipelineEvent("agent", compiler.name, "done", run_id, compiler_output.model_dump())

    # ── Step 2: Parallel specialist agents ───────────────────────────────────
    parallel: list[RadiologyAgent | PathologyAgent | GuidelineAgent | TrialAgent | HistoryCaseAgent] = [
        RadiologyAgent(gemini=gemini),
        PathologyAgent(gemini=gemini),
        GuidelineAgent(gemini=gemini),
        TrialAgent(gemini=gemini),
        HistoryCaseAgent(gemini=gemini),
    ]

    for agent in parallel:
        yield PipelineEvent("agent", agent.name, "running", run_id)

    results = await asyncio.gather(
        *[agent.execute(db, case_id, run_id=run_id) for agent in parallel],
        return_exceptions=True,
    )

    for agent, result in zip(parallel, results):
        if isinstance(result, BaseException):
            yield PipelineEvent(
                "agent", agent.name, "error", run_id, {"error": str(result)}
            )
        else:
            yield PipelineEvent(
                "agent", agent.name, "done", run_id, result.model_dump()
            )

    # ── Step 3: SummaryAgent (sequential, depends on CaseCompiler) ───────────
    summary = SummaryAgent(gemini=gemini)
    yield PipelineEvent("agent", summary.name, "running", run_id)
    try:
        summary_output = await summary.execute(db, case_id, run_id=run_id)
    except AgentError as e:
        yield PipelineEvent("agent", summary.name, "error", run_id, {"error": str(e)})
        yield PipelineEvent(
            "pipeline", None, "error", run_id,
            {"failed_agent": summary.name, "error": str(e)},
        )
        return
    yield PipelineEvent("agent", summary.name, "done", run_id, summary_output.model_dump())

    logger.info(
        "pipeline_complete",
        extra={"extra_fields": {
            "event": "pipeline_complete", "case_id": case_id, "run_id": run_id,
        }},
    )
    yield PipelineEvent("pipeline", None, "complete", run_id, {"case_id": case_id})
