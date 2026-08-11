"""JSON serialization and content-hashed suite snapshots for benchmark tasks."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from benchmark.schema import (
    AdversarialVariant,
    BenchmarkTask,
    Difficulty,
    ExpectedAction,
    ForbiddenAction,
)


class SuiteIntegrityError(ValueError):
    """Raised when a loaded suite snapshot's content hash doesn't match its tasks."""


def task_to_dict(task: BenchmarkTask) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "input": task.input,
        "initial_state": task.initial_state,
        "expected_actions": [_expected_action_to_dict(action) for action in task.expected_actions],
        "forbidden_actions": [_forbidden_action_to_dict(action) for action in task.forbidden_actions],
        "expected_final_state": task.expected_final_state,
        "tags": list(task.tags),
        "difficulty": task.difficulty.value,
    }


def task_from_dict(data: dict[str, Any]) -> BenchmarkTask:
    return BenchmarkTask(
        task_id=data["task_id"],
        input=data["input"],
        initial_state=data["initial_state"],
        expected_actions=tuple(
            ExpectedAction(action["service"], action["operation"], action.get("arguments", {}))
            for action in data["expected_actions"]
        ),
        forbidden_actions=tuple(
            ForbiddenAction(
                action["service"], action["operation"], action["reason"], action.get("arguments", {})
            )
            for action in data["forbidden_actions"]
        ),
        expected_final_state=data["expected_final_state"],
        tags=tuple(data["tags"]),
        difficulty=Difficulty(data["difficulty"]),
    )


def _expected_action_to_dict(action: ExpectedAction) -> dict[str, Any]:
    return {"service": action.service, "operation": action.operation, "arguments": action.arguments}


def _forbidden_action_to_dict(action: ForbiddenAction) -> dict[str, Any]:
    return {
        "service": action.service,
        "operation": action.operation,
        "reason": action.reason,
        "arguments": action.arguments,
    }


def task_to_json(task: BenchmarkTask) -> str:
    return json.dumps(task_to_dict(task), sort_keys=True)


def task_from_json(payload: str) -> BenchmarkTask:
    return task_from_dict(json.loads(payload))


def variant_to_dict(variant: AdversarialVariant) -> dict[str, Any]:
    return {
        "task": task_to_dict(variant.task),
        "parent_task_id": variant.parent_task_id,
        "mutation_type": variant.mutation_type,
        "random_seed": variant.random_seed,
        "validator_result": variant.validator_result,
    }


def variant_from_dict(data: dict[str, Any]) -> AdversarialVariant:
    return AdversarialVariant(
        task=task_from_dict(data["task"]),
        parent_task_id=data["parent_task_id"],
        mutation_type=data["mutation_type"],
        random_seed=data["random_seed"],
        validator_result=data["validator_result"],
    )


@dataclass(frozen=True)
class SuiteSnapshot:
    """An immutable, content-hashed set of benchmark tasks."""

    tasks: tuple[BenchmarkTask, ...]
    content_hash: str


def compute_content_hash(tasks: Iterable[BenchmarkTask]) -> str:
    canonical = json.dumps([task_to_dict(task) for task in tasks], sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def snapshot_suite(tasks: Iterable[BenchmarkTask]) -> SuiteSnapshot:
    frozen_tasks = tuple(tasks)
    return SuiteSnapshot(tasks=frozen_tasks, content_hash=compute_content_hash(frozen_tasks))


def save_suite_snapshot(snapshot: SuiteSnapshot, path: str | Path) -> None:
    payload = {
        "content_hash": snapshot.content_hash,
        "tasks": [task_to_dict(task) for task in snapshot.tasks],
    }
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def load_suite_snapshot(path: str | Path) -> SuiteSnapshot:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    tasks = tuple(task_from_dict(task_data) for task_data in payload["tasks"])
    expected_hash = payload["content_hash"]
    actual_hash = compute_content_hash(tasks)
    if actual_hash != expected_hash:
        raise SuiteIntegrityError(
            f"Suite snapshot at {path} failed its integrity check: "
            f"expected {expected_hash}, computed {actual_hash}"
        )
    return SuiteSnapshot(tasks=tasks, content_hash=actual_hash)
