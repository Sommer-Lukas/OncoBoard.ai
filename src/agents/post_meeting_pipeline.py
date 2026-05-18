"""Post-meeting pipeline runner.

Execution order (ARCHITECTURE.md §2, after Human Gate 2):
  Phase A — NoteDraftAgent ‖ ActionDispatchAgent   (parallel; both read the
            confirmed RecommendationAgent output)
  Phase B — FollowUpAgent ‖ SchedulingAgent         (parallel; both read the
            `actions` ActionDispatchAgent just wrote)

Phase B runs only after Phase A completes so FollowUp/Scheduling see the
dispatched actions. Per-agent failures are non-fatal (mirrors the
pre-meeting parallel block); NoteDraftAgent's output feeds Human Gate 3.

Yields PipelineEvent so an SSE route can stream progress.
"""
from __future__ import annotations

import asyncio
import uuid
from typing import AsyncIterator

import asyncpg

from src.agents.ActionDispatchAgent import ActionDispatchAgent
from src.agents.FollowUpAgent import FollowUpAgent
from src.agents.gemini_client import GeminiClient
from src.agents.NoteDraftAgent import NoteDraftAgent
from src.agents.pipeline import PipelineEvent
from src.agents.SchedulingAgent import SchedulingAgent
from src.agents.session_base import SessionBaseAgent
from src.logging_setup import get_logger

logger = get_logger(__name__)


async def _run_parallel(
    agents: list[SessionBaseAgent],
    db: asyncpg.Connection,
    session_id: str,
    run_id: str,
) -> AsyncIterator[PipelineEvent]:
    for agent in agents:
        yield PipelineEvent("agent", agent.name, "running", run_id)
    results = await asyncio.gather(
        *[a.execute(db, session_id, run_id=run_id) for a in agents],
        return_exceptions=True,
    )
    for agent, result in zip(agents, results):
        if isinstance(result, BaseException):
            yield PipelineEvent("agent", agent.name, "error", run_id, {"error": str(result)})
        else:
            yield PipelineEvent("agent", agent.name, "done", run_id, result.model_dump())


async def run_post_meeting(
    db: asyncpg.Connection,
    session_id: str,
    *,
    gemini: GeminiClient | None = None,
) -> AsyncIterator[PipelineEvent]:
    run_id = str(uuid.uuid4())
    logger.info(
        "post_meeting_start",
        extra={"extra_fields": {
            "event": "post_meeting_start", "session_id": session_id, "run_id": run_id,
        }},
    )

    # Phase A — note draft + action dispatch (both depend on the recommendation)
    async for ev in _run_parallel(
        [NoteDraftAgent(gemini=gemini), ActionDispatchAgent(gemini=gemini)],
        db, session_id, run_id,
    ):
        yield ev

    # Phase B — follow-up + scheduling (depend on dispatched actions)
    async for ev in _run_parallel(
        [FollowUpAgent(gemini=gemini), SchedulingAgent(gemini=gemini)],
        db, session_id, run_id,
    ):
        yield ev

    logger.info(
        "post_meeting_complete",
        extra={"extra_fields": {
            "event": "post_meeting_complete", "session_id": session_id, "run_id": run_id,
        }},
    )
    yield PipelineEvent("pipeline", None, "complete", run_id, {"session_id": session_id})
