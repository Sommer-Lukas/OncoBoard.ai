"""Gemini client wrapper.

Exposes a single async `generate()` method that returns a typed `GeminiResponse`.
A real client talks to google-genai; a mock client returns canned responses for
tests and dev (toggled by `GEMINI_MOCK=1`).

Token usage is surfaced on the response so the agent base class can persist it
to `agent_outputs.tokens_used` for cost tracking.
"""
from __future__ import annotations

import asyncio
import logging
from collections import deque
from typing import Any, Protocol, runtime_checkable

from src.agents.types import GeminiResponse, ModelTier
from src.config import Settings, get_settings

logger = logging.getLogger(__name__)


@runtime_checkable
class GeminiClient(Protocol):
    async def generate(
        self,
        *,
        model_tier: ModelTier,
        prompt: str,
        system_instruction: str | None = None,
        response_schema: type[Any] | None = None,
        image_paths: list[str] | None = None,
        audio_data: bytes | None = None,
        audio_mime_type: str = "audio/wav",
    ) -> GeminiResponse: ...


# ---------- Real client ----------

class RealGeminiClient:
    """Thin wrapper around google-genai's async client.

    Retries transient failures with exponential backoff. Surfaces total token
    count from response.usage_metadata so callers can persist it for audit.
    """

    def __init__(
        self,
        model_pro: str,
        model_flash: str,
        model_vision: str,
        *,
        api_key: str = "",
        project: str = "",
        location: str = "us-central1",
        max_retries: int = 2,
        base_backoff_s: float = 0.5,
    ) -> None:
        from google import genai

        if api_key:
            self._client = genai.Client(api_key=api_key)
        else:
            self._client = genai.Client(vertexai=True, project=project, location=location)
        self._models: dict[ModelTier, str] = {
            "pro": model_pro,
            "flash": model_flash,
            "vision": model_vision,
        }
        self._max_retries = max_retries
        self._base_backoff_s = base_backoff_s

    async def generate(
        self,
        *,
        model_tier: ModelTier,
        prompt: str,
        system_instruction: str | None = None,
        response_schema: type[Any] | None = None,
        image_paths: list[str] | None = None,
        audio_data: bytes | None = None,
        audio_mime_type: str = "audio/wav",
    ) -> GeminiResponse:
        from google.genai import types as genai_types

        model = self._models[model_tier]
        config_kwargs: dict[str, Any] = {}
        if system_instruction is not None:
            config_kwargs["system_instruction"] = system_instruction
        if response_schema is not None:
            config_kwargs["response_mime_type"] = "application/json"
            config_kwargs["response_schema"] = response_schema
            # Gemini 2.5 thinking tokens can contaminate resp.text and break
            # json.loads in callers. Set budget_tokens=0 for structured output.
            config_kwargs["thinking_config"] = genai_types.ThinkingConfig(
                thinking_budget=0
            )
        config = genai_types.GenerateContentConfig(**config_kwargs) if config_kwargs else None

        if image_paths or audio_data is not None:
            parts: list[Any] = []
            if audio_data is not None:
                parts.append(genai_types.Part.from_bytes(data=audio_data, mime_type=audio_mime_type))
            if image_paths:
                for path in image_paths:
                    try:
                        with open(path, "rb") as fh:
                            data = fh.read()
                        mime = "image/jpeg" if str(path).lower().endswith((".jpg", ".jpeg")) else "image/png"
                        parts.append(genai_types.Part.from_bytes(data=data, mime_type=mime))
                    except OSError:
                        pass
            parts.append(genai_types.Part.from_text(text=prompt))
            contents: Any = genai_types.Content(role="user", parts=parts)
        else:
            contents = prompt

        attempt = 0
        while True:
            try:
                resp = await self._client.aio.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config,
                )
                return GeminiResponse(
                    text=resp.text or "",
                    tokens_used=int(getattr(resp.usage_metadata, "total_token_count", 0) or 0),
                )
            except Exception as e:
                if attempt >= self._max_retries:
                    raise
                backoff = self._base_backoff_s * (2 ** attempt)
                logger.warning(
                    "gemini_retry",
                    extra={"extra_fields": {
                        "event": "gemini_retry",
                        "model_tier": model_tier,
                        "attempt": attempt + 1,
                        "backoff_s": backoff,
                        "error": str(e),
                    }},
                )
                await asyncio.sleep(backoff)
                attempt += 1


# ---------- Mock client ----------

class MockGeminiClient:
    """In-memory canned-response client for tests and offline dev.

    Queue responses in FIFO order with `.queue(text, tokens_used=...)`. When the
    queue is empty, `default_response` is returned (or an empty `{}` JSON if
    none was set). Every `generate()` call is recorded on `.calls` so tests can
    assert on what was sent.
    """

    def __init__(self, *, default_response: GeminiResponse | None = None) -> None:
        self._queue: deque[GeminiResponse] = deque()
        self.default_response: GeminiResponse = default_response or GeminiResponse(
            text="{}", tokens_used=0
        )
        self.calls: list[dict[str, Any]] = []

    def queue(self, text: str, *, tokens_used: int = 0) -> None:
        self._queue.append(GeminiResponse(text=text, tokens_used=tokens_used))

    def reset(self) -> None:
        self._queue.clear()
        self.calls.clear()

    async def generate(
        self,
        *,
        model_tier: ModelTier,
        prompt: str,
        system_instruction: str | None = None,
        response_schema: type[Any] | None = None,
        image_paths: list[str] | None = None,
        audio_data: bytes | None = None,
        audio_mime_type: str = "audio/wav",
    ) -> GeminiResponse:
        self.calls.append(
            {
                "model_tier": model_tier,
                "prompt": prompt,
                "system_instruction": system_instruction,
                "response_schema": response_schema.__name__ if response_schema else None,
                "image_paths": image_paths,
                "has_audio": audio_data is not None,
                "audio_mime_type": audio_mime_type if audio_data is not None else None,
            }
        )
        if self._queue:
            return self._queue.popleft()
        return self.default_response


# ---------- Factory ----------

_singleton: GeminiClient | None = None


def get_gemini_client(settings: Settings | None = None) -> GeminiClient:
    """Return a process-wide GeminiClient. Honors GEMINI_MOCK at construction time."""
    global _singleton
    if _singleton is not None:
        return _singleton
    s = settings or get_settings()
    if s.gemini_mock:
        _singleton = MockGeminiClient()
    else:
        _singleton = RealGeminiClient(
            model_pro=s.gemini_model_pro,
            model_flash=s.gemini_model_flash,
            model_vision=s.gemini_model_vision,
            api_key=s.gemini_api_key,
            project=s.gemini_project,
            location=s.gemini_location,
        )
    return _singleton


def reset_gemini_client() -> None:
    """Drop the cached client. Test-only — call between cases that need a fresh mock."""
    global _singleton
    _singleton = None
