"""Core benchmark task contracts for deterministic agent evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Difficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


@dataclass(frozen=True)
class ExpectedAction:
    """A required tool call shape for deterministic contract scoring."""

    service: str
    operation: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ForbiddenAction:
    """A tool call shape that must not appear in a valid run."""

    service: str
    operation: str
    reason: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BenchmarkTask:
    """A reproducible customer-support task and its success contract."""

    task_id: str
    input: str
    initial_state: dict[str, Any]
    expected_actions: tuple[ExpectedAction, ...]
    forbidden_actions: tuple[ForbiddenAction, ...]
    expected_final_state: dict[str, Any]
    tags: tuple[str, ...]
    difficulty: Difficulty


@dataclass(frozen=True)
class AdversarialVariant:
    """Lineage and validation metadata for a generated task variant."""

    task: BenchmarkTask
    parent_task_id: str
    mutation_type: str
    random_seed: int
    validator_result: bool
