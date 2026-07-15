"""Constraint-preserving adversarial task mutations."""

from __future__ import annotations

import random
import re
from dataclasses import replace

from benchmark.schema import AdversarialVariant, BenchmarkTask, ForbiddenAction


TYPO_REPLACEMENTS = {
    "Customer": "Custmer",
    "damaged": "damagd",
    "refund": "refnd",
    "ticket": "tcket",
}

DISTRACTOR_SENTENCES = (
    "The customer also mentioned they are considering buying a gift card.",
    "The customer's package was delivered by a regional carrier this time.",
    "The customer asked whether the company offers a loyalty program.",
    "The customer noted that their cat knocked over the delivery box.",
)

_DOLLAR_AMOUNT_PATTERN = re.compile(r"\$(\d+)\.(\d{2})")
_CUSTOMER_MENTION_PATTERN = re.compile(r"Customer (CUST-\d+)")


def inject_typos(task: BenchmarkTask, random_seed: int) -> AdversarialVariant:
    """Create a deterministic typo variant without changing the task contract."""

    rng = random.Random(random_seed)
    candidates = [word for word in TYPO_REPLACEMENTS if word in task.input]
    if not candidates:
        return AdversarialVariant(task, task.task_id, "typo_injection", random_seed, False)

    word = rng.choice(candidates)
    mutated = replace(
        task,
        task_id=f"{task.task_id}__typo_{random_seed}",
        input=task.input.replace(word, TYPO_REPLACEMENTS[word], 1),
        tags=task.tags + ("adversarial", "typo_injection"),
    )
    return AdversarialVariant(mutated, task.task_id, "typo_injection", random_seed, True)


def inject_distractor_information(task: BenchmarkTask, random_seed: int) -> AdversarialVariant:
    """Append an irrelevant, contract-preserving sentence to the task input."""

    rng = random.Random(random_seed)
    sentence = rng.choice(DISTRACTOR_SENTENCES)
    mutated = replace(
        task,
        task_id=f"{task.task_id}__distractor_{random_seed}",
        input=f"{task.input} {sentence}",
        tags=task.tags + ("adversarial", "distractor_information"),
    )
    return AdversarialVariant(mutated, task.task_id, "distractor_information", random_seed, True)


def inject_conflicting_detail(task: BenchmarkTask, random_seed: int) -> AdversarialVariant:
    """Restate a dollar amount incorrectly in the input while ground-truth state is unchanged.

    Tests whether the agent trusts tool state over an unreliable customer-reported figure.
    """

    match = _DOLLAR_AMOUNT_PATTERN.search(task.input)
    if not match:
        return AdversarialVariant(task, task.task_id, "conflicting_detail", random_seed, False)

    rng = random.Random(random_seed)
    actual_cents = int(match.group(1)) * 100 + int(match.group(2))
    conflicting_cents = actual_cents + rng.randint(1, 500)
    conflicting_amount = f"${conflicting_cents // 100}.{conflicting_cents % 100:02d}"

    mutated = replace(
        task,
        task_id=f"{task.task_id}__conflict_{random_seed}",
        input=task.input.replace(match.group(0), conflicting_amount, 1),
        tags=task.tags + ("adversarial", "conflicting_detail"),
    )
    return AdversarialVariant(mutated, task.task_id, "conflicting_detail", random_seed, True)


def create_missing_customer_information_variant(task: BenchmarkTask, random_seed: int) -> AdversarialVariant:
    """Strip the explicit customer identity from the input, forcing inference from the order.

    Adds a forbidden action guarding against guessing a decoy customer id.
    """

    match = _CUSTOMER_MENTION_PATTERN.search(task.input)
    if not match:
        return AdversarialVariant(task, task.task_id, "missing_customer_information", random_seed, False)

    rng = random.Random(random_seed)
    decoy_customer_id = f"CUST-{900 + rng.randint(0, 99)}"

    mutated = replace(
        task,
        task_id=f"{task.task_id}__missing_customer_{random_seed}",
        input=task.input.replace(match.group(0), "A shopper", 1),
        forbidden_actions=task.forbidden_actions
        + (
            ForbiddenAction(
                "customer",
                "get_customer",
                "Customer identity was not provided in the request; the agent must infer it from the order.",
                {"customer_id": decoy_customer_id},
            ),
        ),
        tags=task.tags + ("adversarial", "missing_customer_information"),
    )
    return AdversarialVariant(mutated, task.task_id, "missing_customer_information", random_seed, True)


def create_boundary_refund_amount_variant(task: BenchmarkTask, random_seed: int) -> AdversarialVariant:
    """Shift a full-refund task's order total to a new boundary value.

    Only applies to tasks whose expected refund amount equals the order total.
    """

    refund_action = next(
        (action for action in task.expected_actions if action.service == "refund" and action.operation == "create_refund"),
        None,
    )
    order_id = refund_action.arguments.get("order_id") if refund_action else None
    orders = task.initial_state.get("orders", {})
    if refund_action is None or order_id not in orders:
        return AdversarialVariant(task, task.task_id, "boundary_refund_amount", random_seed, False)

    order = orders[order_id]
    original_total = order["total_cents"]
    if refund_action.arguments.get("amount_cents") != original_total:
        return AdversarialVariant(task, task.task_id, "boundary_refund_amount", random_seed, False)

    rng = random.Random(random_seed)
    new_total = original_total + rng.randint(1, 200)

    mutated_orders = {**orders, order_id: {**order, "total_cents": new_total}}
    mutated_state = {**task.initial_state, "orders": mutated_orders}

    mutated_expected_actions = tuple(
        replace(action, arguments={**action.arguments, "amount_cents": new_total})
        if action is refund_action
        else action
        for action in task.expected_actions
    )
    mutated_forbidden_actions = tuple(
        replace(action, arguments={**action.arguments, "amount_cents": new_total + 1})
        if action.service == "refund"
        and action.arguments.get("order_id") == order_id
        and action.arguments.get("amount_cents") == original_total + 1
        else action
        for action in task.forbidden_actions
    )

    mutated_final_state = dict(task.expected_final_state)
    refunds = mutated_final_state.get("refunds", {})
    if order_id in refunds:
        mutated_final_state = {
            **mutated_final_state,
            "refunds": {**refunds, order_id: {**refunds[order_id], "amount_cents": new_total}},
        }

    mutated = replace(
        task,
        task_id=f"{task.task_id}__boundary_{random_seed}",
        initial_state=mutated_state,
        expected_actions=mutated_expected_actions,
        forbidden_actions=mutated_forbidden_actions,
        expected_final_state=mutated_final_state,
        tags=task.tags + ("adversarial", "boundary_refund_amount"),
    )
    return AdversarialVariant(mutated, task.task_id, "boundary_refund_amount", random_seed, True)


MUTATIONS = (
    inject_typos,
    inject_distractor_information,
    inject_conflicting_detail,
    create_missing_customer_information_variant,
    create_boundary_refund_amount_variant,
)
