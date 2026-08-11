"""Traced proxy around the deterministic support-tool environment.

Every invocation is recorded as a tool_call step followed by either a tool_result or
an error step, so the resulting trace is a complete record of what the agent did
regardless of whether the call succeeded.
"""

from __future__ import annotations

import time
from typing import Any

from app.trace import ErrorPayload, ToolCallPayload, ToolResultPayload, Trace, TraceStep
from tool_environment import SupportToolEnvironment
from tool_environment.errors import ToolEnvironmentError

_SERVICE_ATTRS = {"customer", "order", "policy", "refund", "ticket"}


class UnknownToolError(Exception):
    """Raised when the agent requests a service/operation the environment doesn't expose."""


class TracedToolProxy:
    def __init__(self, environment: SupportToolEnvironment, trace: Trace) -> None:
        self._environment = environment
        self._trace = trace

    def invoke(self, call_id: str, service: str, operation: str, arguments: dict[str, Any]) -> TraceStep:
        call_step = self._trace.append(
            ToolCallPayload(call_id=call_id, service=service, operation=operation, arguments=arguments)
        )
        start = time.perf_counter()
        try:
            method = self._resolve(service, operation)
            result = method(**arguments)
        except (ToolEnvironmentError, UnknownToolError, TypeError) as error:
            duration_ms = int((time.perf_counter() - start) * 1000)
            return self._trace.append(
                ErrorPayload(error_type=type(error).__name__, message=str(error)),
                parent_step_id=call_step.id,
                duration_ms=duration_ms,
            )
        duration_ms = int((time.perf_counter() - start) * 1000)
        return self._trace.append(
            ToolResultPayload(call_id=call_id, result=result),
            parent_step_id=call_step.id,
            duration_ms=duration_ms,
        )

    def _resolve(self, service: str, operation: str):
        if service not in _SERVICE_ATTRS:
            raise UnknownToolError(f"unknown service: {service}")
        target = getattr(self._environment, service)
        method = getattr(target, operation, None)
        if method is None or not callable(method):
            raise UnknownToolError(f"unknown operation: {service}.{operation}")
        return method
