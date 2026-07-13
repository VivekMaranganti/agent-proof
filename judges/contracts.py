"""Deterministic scoring against benchmark task contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from benchmark.schema import BenchmarkTask


@dataclass(frozen=True)
class ToolCall:
    service: str
    operation: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ContractScore:
    passed: bool
    missing_expected_actions: tuple[str, ...]
    forbidden_actions_seen: tuple[str, ...]


def score_actions(task: BenchmarkTask, tool_calls: tuple[ToolCall, ...]) -> ContractScore:
    missing: list[str] = []
    forbidden_seen: list[str] = []

    for expected in task.expected_actions:
        if not any(
            call.service == expected.service
            and call.operation == expected.operation
            and expected.arguments.items() <= call.arguments.items()
            for call in tool_calls
        ):
            missing.append(f"{expected.service}.{expected.operation}")

    for forbidden in task.forbidden_actions:
        if any(
            call.service == forbidden.service
            and call.operation == forbidden.operation
            and forbidden.arguments.items() <= call.arguments.items()
            for call in tool_calls
        ):
            forbidden_seen.append(f"{forbidden.service}.{forbidden.operation}: {forbidden.reason}")

    return ContractScore(
        passed=not missing and not forbidden_seen,
        missing_expected_actions=tuple(missing),
        forbidden_actions_seen=tuple(forbidden_seen),
    )
