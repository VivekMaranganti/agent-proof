"""Pluggable model backend for the runner.

The runner is written against this Protocol, not any particular LLM SDK, since
AgentVersion.model can name any backend a version wants to evaluate. ScriptedModelClient
is the deterministic implementation used by runner tests; a real provider-backed client
can implement the same Protocol without the runner changing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ToolCallRequest:
    call_id: str
    service: str
    operation: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelReply:
    finish_reason: str
    content: str | None = None
    tool_calls: tuple[ToolCallRequest, ...] = ()
    input_tokens: int = 0
    output_tokens: int = 0


class TransientModelError(Exception):
    """Raised by a ModelClient for a retryable failure (rate limit, timeout, etc.)."""


class ModelClient(Protocol):
    async def complete(
        self, *, messages: list[dict[str, Any]], model: str, params: dict[str, Any]
    ) -> ModelReply: ...


class ScriptedModelClient:
    """Replays a fixed sequence of ModelReply/TransientModelError values.

    Lets runner tests exercise multi-step tool-calling loops and the retry path without
    a live model backend, while staying deterministic and seed-independent.
    """

    def __init__(self, script: list[ModelReply | TransientModelError]) -> None:
        self._script = list(script)
        self._calls = 0

    @property
    def calls_made(self) -> int:
        return self._calls

    async def complete(
        self, *, messages: list[dict[str, Any]], model: str, params: dict[str, Any]
    ) -> ModelReply:
        if self._calls >= len(self._script):
            raise AssertionError("ScriptedModelClient script exhausted")
        item = self._script[self._calls]
        self._calls += 1
        if isinstance(item, TransientModelError):
            raise item
        return item
