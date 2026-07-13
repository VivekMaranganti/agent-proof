"""Constraint-preserving adversarial task mutations."""

from __future__ import annotations

import random
from dataclasses import replace

from benchmark.schema import AdversarialVariant, BenchmarkTask


TYPO_REPLACEMENTS = {
    "Customer": "Custmer",
    "damaged": "damagd",
    "refund": "refnd",
    "ticket": "tcket",
}


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
