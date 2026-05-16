from dataclasses import dataclass
from typing import Literal

ModelTier = Literal["pro", "flash", "vision"]


@dataclass(frozen=True)
class GeminiResponse:
    text: str
    tokens_used: int


class AgentError(Exception):
    """Base class for agent-layer failures."""


class CaseNotFoundError(AgentError):
    pass


class SessionNotFoundError(AgentError):
    pass


class AgentOutputValidationError(AgentError):
    """Raised when an agent's raw output cannot be coerced into its declared schema."""
