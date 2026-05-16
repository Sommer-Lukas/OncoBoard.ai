"""Session-aware agent base class.

During-meeting and post-meeting agents operate on a Session rather than a bare
Case because their inputs (transcripts, decisions) are session-scoped. This
base mirrors BaseAgent's lifecycle exactly — load, time, validate, persist,
log — but the primary unit is a session_id.

Subclasses implement only `run(db, session, case, *, run_id)`. The framework
handles loading both the session and its linked case, validation, and audit
persistence to `agent_outputs` (keyed by case_id for consistency with pre-
meeting outputs).
"""
from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import ClassVar, Generic, TypeVar

import aiosqlite
from pydantic import BaseModel, ValidationError

from src.agents.gemini_client import GeminiClient, get_gemini_client
from src.agents.types import (
    AgentOutputValidationError,
    CaseNotFoundError,
    GeminiResponse,
    ModelTier,
    SessionNotFoundError,
)
from src.db import repository as repo
from src.db.models import AgentOutput, Case, Session
from src.logging_setup import get_logger, log_agent_run

TOutput = TypeVar("TOutput", bound=BaseModel)


class SessionBaseAgent(ABC, Generic[TOutput]):
    """Inherit, set name/model_tier/output_schema, implement run().

    Example:

        class MyOutput(BaseModel):
            session_id: str
            result: str

        class MyAgent(SessionBaseAgent[MyOutput]):
            name = "MyAgent"
            model_tier = "flash"
            output_schema = MyOutput

            async def run(self, db, session, case, *, run_id):
                ...
                return MyOutput(session_id=session.session_id, result="...")
    """

    name: ClassVar[str]
    model_tier: ClassVar[ModelTier]
    output_schema: ClassVar[type[BaseModel]]

    def __init__(self, gemini: GeminiClient | None = None) -> None:
        self.gemini: GeminiClient = gemini or get_gemini_client()
        self.logger = get_logger(f"agent.{self.name}")

    @abstractmethod
    async def run(
        self, db: aiosqlite.Connection, session: Session, case: Case, *, run_id: str
    ) -> TOutput:
        """Subclass implementation. Session and case are already loaded."""

    async def execute(
        self,
        db: aiosqlite.Connection,
        session_id: str,
        *,
        run_id: str | None = None,
    ) -> TOutput:
        """Load session+case, run subclass, validate, persist, log.

        Saves to agent_outputs with case_id from the session so all agent
        outputs for a case are co-located in the same table regardless of phase.
        """
        run_id = run_id or str(uuid.uuid4())
        start = time.perf_counter()

        session = await repo.get_session(db, session_id)
        if session is None:
            raise SessionNotFoundError(f"session {session_id} not found")

        case = await repo.get_case(db, session.case_id)
        if case is None:
            raise CaseNotFoundError(
                f"case {session.case_id} not found for session {session_id}"
            )

        try:
            raw = await self.run(db, session, case, run_id=run_id)
        except Exception as e:
            duration_ms = int((time.perf_counter() - start) * 1000)
            await self._persist_error(db, session.case_id, run_id, duration_ms, e)
            log_agent_run(
                self.logger,
                case_id=session.case_id,
                agent_name=self.name,
                duration_ms=duration_ms,
                status="error",
                error=str(e),
            )
            raise

        try:
            if isinstance(raw, self.output_schema):
                validated = raw
            else:
                validated = self.output_schema.model_validate(
                    raw.model_dump() if isinstance(raw, BaseModel) else raw
                )
        except ValidationError as ve:
            duration_ms = int((time.perf_counter() - start) * 1000)
            wrapped = AgentOutputValidationError(
                f"{self.name} returned an output that does not match "
                f"{self.output_schema.__name__}: {ve}"
            )
            await self._persist_error(db, session.case_id, run_id, duration_ms, wrapped)
            log_agent_run(
                self.logger,
                case_id=session.case_id,
                agent_name=self.name,
                duration_ms=duration_ms,
                status="error",
                error=str(wrapped),
            )
            raise wrapped from ve

        duration_ms = int((time.perf_counter() - start) * 1000)
        tokens_used = self._consume_tokens()

        await repo.save_agent_output(
            db,
            AgentOutput(
                case_id=session.case_id,
                agent_name=self.name,
                run_id=run_id,
                output=validated.model_dump(),
                status="success",
                duration_ms=duration_ms,
                tokens_used=tokens_used,
                created_at=_now(),
            ),
        )
        log_agent_run(
            self.logger,
            case_id=session.case_id,
            agent_name=self.name,
            duration_ms=duration_ms,
            status="success",
            tokens_used=tokens_used,
        )
        return validated  # type: ignore[return-value]

    async def call_gemini(
        self,
        *,
        prompt: str,
        system_instruction: str | None = None,
        response_schema: type[BaseModel] | None = None,
        image_paths: list[str] | None = None,
        audio_data: bytes | None = None,
        audio_mime_type: str = "audio/wav",
    ) -> GeminiResponse:
        """Convenience wrapper. Tracks tokens consumed during this execute() run."""
        resp = await self.gemini.generate(
            model_tier=self.model_tier,
            prompt=prompt,
            system_instruction=system_instruction,
            response_schema=response_schema,
            image_paths=image_paths,
            audio_data=audio_data,
            audio_mime_type=audio_mime_type,
        )
        self._pending_tokens += resp.tokens_used
        return resp

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        for required in ("name", "model_tier", "output_schema"):
            if not hasattr(cls, required) or getattr(cls, required) is SessionBaseAgent.__dict__.get(required):
                if getattr(cls, "__abstractmethods__", None):
                    continue
                raise TypeError(f"{cls.__name__} must set ClassVar `{required}`")

    _pending_tokens: int = 0

    def _consume_tokens(self) -> int:
        n = self._pending_tokens
        self._pending_tokens = 0
        return n

    async def _persist_error(
        self,
        db: aiosqlite.Connection,
        case_id: str,
        run_id: str,
        duration_ms: int,
        err: Exception,
    ) -> None:
        await repo.save_agent_output(
            db,
            AgentOutput(
                case_id=case_id,
                agent_name=self.name,
                run_id=run_id,
                output={},
                status="error",
                error_message=str(err),
                duration_ms=duration_ms,
                tokens_used=self._consume_tokens() or None,
                created_at=_now(),
            ),
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
