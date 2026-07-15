"""Deterministic scoring against benchmark task contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

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
    final_state_mismatches: tuple[str, ...]


def score_actions(
    task: BenchmarkTask,
    tool_calls: tuple[ToolCall, ...],
    final_state: Mapping[str, Any],
) -> ContractScore:
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

    final_state_mismatches = _diff_final_state(task.expected_final_state, final_state)

    return ContractScore(
        passed=not missing and not forbidden_seen and not final_state_mismatches,
        missing_expected_actions=tuple(missing),
        forbidden_actions_seen=tuple(forbidden_seen),
        final_state_mismatches=final_state_mismatches,
    )


def _diff_final_state(expected: Any, actual: Any, path: str = "") -> tuple[str, ...]:
    """Recursively check that `expected` is contained within `actual`.

    `actual` may have keys or sibling entities not present in `expected`; only
    the fields a task contract cares about are compared.
    """

    if isinstance(expected, dict):
        if not isinstance(actual, Mapping):
            return (f"{path or '<root>'}: expected an object, got {actual!r}",)

        mismatches: list[str] = []
        for key, value in expected.items():
            child_path = f"{path}.{key}" if path else str(key)
            if key not in actual:
                mismatches.append(f"{child_path}: missing from final state")
                continue
            mismatches.extend(_diff_final_state(value, actual[key], child_path))
        return tuple(mismatches)

    if expected != actual:
        return (f"{path}: expected {expected!r}, got {actual!r}",)

    return ()
