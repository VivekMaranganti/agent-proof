"""Validation for adversarial benchmark mutations."""

from __future__ import annotations

from typing import Mapping

from benchmark.schema import AdversarialVariant, BenchmarkTask, ForbiddenAction

VALID_SERVICE_OPERATIONS: dict[str, frozenset[str]] = {
    "customer": frozenset({"get_customer"}),
    "order": frozenset({"get_order"}),
    "policy": frozenset({"check_refund_policy"}),
    "refund": frozenset({"create_refund"}),
    "ticket": frozenset({"update_ticket"}),
}

_ID_ARGUMENT_TO_STATE_COLLECTION = {
    "customer_id": "customers",
    "order_id": "orders",
    "ticket_id": "tickets",
}

# Mutations that must not change the underlying success contract, only the
# wording or surrounding detail of the task input.
CONTRACT_PRESERVING_MUTATIONS = frozenset(
    {"typo_injection", "distractor_information", "conflicting_detail"}
)


def validate_variant(
    variant: AdversarialVariant,
    parent_tasks_by_id: Mapping[str, BenchmarkTask],
    existing_task_ids: frozenset[str],
) -> bool:
    """Check that a generated adversarial variant is well-formed and reproducible."""

    if not variant.mutation_type or not variant.parent_task_id:
        return False

    parent = parent_tasks_by_id.get(variant.parent_task_id)
    if parent is None:
        return False

    task = variant.task
    if task.task_id in existing_task_ids:
        return False

    for action in (*task.expected_actions, *task.forbidden_actions):
        allowed_operations = VALID_SERVICE_OPERATIONS.get(action.service)
        if allowed_operations is None or action.operation not in allowed_operations:
            return False

    for expected in task.expected_actions:
        if not _referenced_ids_exist(expected.arguments, task.initial_state):
            return False

    if variant.mutation_type in CONTRACT_PRESERVING_MUTATIONS:
        if task.expected_actions != parent.expected_actions:
            return False
        if _forbidden_signatures(task.forbidden_actions) != _forbidden_signatures(parent.forbidden_actions):
            return False

    return True


def _referenced_ids_exist(arguments: Mapping[str, object], initial_state: Mapping[str, object]) -> bool:
    for key, collection_name in _ID_ARGUMENT_TO_STATE_COLLECTION.items():
        if key in arguments and arguments[key] not in initial_state.get(collection_name, {}):
            return False
    return True


def _forbidden_signatures(
    forbidden_actions: tuple[ForbiddenAction, ...]
) -> frozenset[tuple[str, str, tuple[tuple[str, object], ...]]]:
    return frozenset(
        (action.service, action.operation, tuple(sorted(action.arguments.items())))
        for action in forbidden_actions
    )
