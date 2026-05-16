"""Shared agent base class.

Subclasses implement only `run()`. The framework handles:
- loading the case so subclasses can assume it exists,
- timing + structured audit logging,
- validating subclass output against its declared Pydantic schema,
- persisting the result (success or error) to `agent_outputs`.

This is the single point where all 13 agents agree on lifecycle, so getting it
right means each agent file becomes a thin specialist implementation.
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
from src.agents.types import AgentOutputValidationError, CaseNotFoundError, ModelTier
from src.db import repository as repo
from src.db.models import AgentOutput, Case
from src.logging_setup import get_logger, log_agent_run

TOutput = TypeVar("TOutput", bound=BaseModel)


class BaseAgent(ABC, Generic[TOutput]):
    """Inherit, set the three ClassVars, and implement `run()`.

    Example:

        class CaseCompilerOutput(BaseModel):
            missing_fields: list[str]
            ready_for_review: bool

        class CaseCompiler(BaseAgent[CaseCompilerOutput]):
            name = "CaseCompiler"
            model_tier = "flash"
            output_schema = CaseCompilerOutput

            async def run(self, db, case, *, run_id):
                ...
                return CaseCompilerOutput(missing_fields=[...], ready_for_review=True)
    """

    # ClassVars — set by subclasses.
    name: ClassVar[str]
    model_tier: ClassVar[ModelTier]
    output_schema: ClassVar[type[BaseModel]]

    def __init__(self, gemini: GeminiClient | None = None) -> None:
        self.gemini: GeminiClient = gemini or get_gemini_client()
        self.logger = get_logger(f"agent.{self.name}")

    @abstractmethod
    async def run(self, db: aiosqlite.Connection, case: Case, *, run_id: str) -> TOutput:
        """Subclass implementation. The case is already loaded; return a typed output."""

    async def execute(
        self,
        db: aiosqlite.Connection,
        case_id: str,
        *,
        run_id: str | None = None,
    ) -> TOutput:
        """Load case, run subclass, validate, persist, log. Returns the typed output.

        On success: writes one row to `agent_outputs` with status='success'.
        On error: writes one row with status='error' (output_json={}) and re-raises.
        """
        run_id = run_id or str(uuid.uuid4())
        start = time.perf_counter()

        case = await repo.get_case(db, case_id)
        if case is None:
            raise CaseNotFoundError(f"case {case_id} not found")

        try:
            raw = await self.run(db, case, run_id=run_id)
        except Exception as e:
            duration_ms = int((time.perf_counter() - start) * 1000)
            await self._persist_error(db, case_id, run_id, duration_ms, e)
            log_agent_run(
                self.logger,
                case_id=case_id,
                agent_name=self.name,
                duration_ms=duration_ms,
                status="error",
                error=str(e),
            )
            raise

        # Validate. Subclasses should already return the right type, but enforce here
        # so a malformed return slips into a clean ValidationError rather than a DB
        # crash three steps later.
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
                f"{self.name} returned an output that does not match {self.output_schema.__name__}: {ve}"
            )
            await self._persist_error(db, case_id, run_id, duration_ms, wrapped)
            log_agent_run(
                self.logger,
                case_id=case_id,
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
                case_id=case_id,
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
            case_id=case_id,
            agent_name=self.name,
            duration_ms=duration_ms,
            status="success",
            tokens_used=tokens_used,
        )
        return validated  # type: ignore[return-value]

    # ---------- helpers for subclasses ----------

    async def call_gemini(
        self,
        *,
        prompt: str,
        system_instruction: str | None = None,
        response_schema: type[BaseModel] | None = None,
        image_paths: list[str] | None = None,
    ):
        """Convenience wrapper. Tracks tokens consumed during this `execute()` run."""
        resp = await self.gemini.generate(
            model_tier=self.model_tier,
            prompt=prompt,
            system_instruction=system_instruction,
            response_schema=response_schema,
            image_paths=image_paths,
        )
        self._pending_tokens += resp.tokens_used
        return resp

    # ---------- internals ----------

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        # Catch typos at class-definition time rather than at first execute().
        for required in ("name", "model_tier", "output_schema"):
            if not hasattr(cls, required) or getattr(cls, required) is BaseAgent.__dict__.get(required):
                # Allow further-nested abstract subclasses.
                if getattr(cls, "__abstractmethods__", None):
                    continue
                raise TypeError(f"{cls.__name__} must set ClassVar `{required}`")

    _pending_tokens: int = 0  # accumulator reset per `execute()` call

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
