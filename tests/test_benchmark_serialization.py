import pytest

from benchmark.mutations import MUTATION_REGISTRY, apply_mutation, inject_typos
from benchmark.serialization import (
    SuiteIntegrityError,
    compute_content_hash,
    load_suite_snapshot,
    save_suite_snapshot,
    snapshot_suite,
    task_from_dict,
    task_from_json,
    task_to_dict,
    task_to_json,
    variant_from_dict,
    variant_to_dict,
)
from benchmark.tasks import CUSTOMER_REFUND_WITHIN_POLICY, SEED_TASKS


def test_task_round_trips_through_dict() -> None:
    restored = task_from_dict(task_to_dict(CUSTOMER_REFUND_WITHIN_POLICY))

    assert restored == CUSTOMER_REFUND_WITHIN_POLICY


def test_task_round_trips_through_json() -> None:
    restored = task_from_json(task_to_json(CUSTOMER_REFUND_WITHIN_POLICY))

    assert restored == CUSTOMER_REFUND_WITHIN_POLICY


def test_variant_round_trips_through_dict() -> None:
    variant = inject_typos(CUSTOMER_REFUND_WITHIN_POLICY, random_seed=1)

    restored = variant_from_dict(variant_to_dict(variant))

    assert restored == variant


def test_content_hash_is_stable_for_the_same_tasks() -> None:
    first = compute_content_hash(SEED_TASKS)
    second = compute_content_hash(SEED_TASKS)

    assert first == second


def test_content_hash_changes_when_a_task_changes() -> None:
    mutated = inject_typos(CUSTOMER_REFUND_WITHIN_POLICY, random_seed=1).task
    other_tasks = (mutated, *SEED_TASKS[1:])

    assert compute_content_hash(SEED_TASKS) != compute_content_hash(other_tasks)


def test_save_and_load_suite_snapshot_round_trips(tmp_path) -> None:
    snapshot = snapshot_suite(SEED_TASKS)
    path = tmp_path / "suite.json"

    save_suite_snapshot(snapshot, path)
    reloaded = load_suite_snapshot(path)

    assert reloaded.tasks == snapshot.tasks
    assert reloaded.content_hash == snapshot.content_hash


def test_load_suite_snapshot_detects_tampering(tmp_path) -> None:
    snapshot = snapshot_suite(SEED_TASKS)
    path = tmp_path / "suite.json"
    save_suite_snapshot(snapshot, path)

    tampered = path.read_text(encoding="utf-8").replace(
        CUSTOMER_REFUND_WITHIN_POLICY.task_id, "tampered-task-id"
    )
    path.write_text(tampered, encoding="utf-8")

    with pytest.raises(SuiteIntegrityError):
        load_suite_snapshot(path)


def test_mutation_registry_contains_every_mutation_type() -> None:
    expected_types = {
        "typo_injection",
        "distractor_information",
        "conflicting_detail",
        "missing_customer_information",
        "boundary_refund_amount",
    }

    assert set(MUTATION_REGISTRY) == expected_types


def test_apply_mutation_by_name_matches_calling_the_function_directly() -> None:
    direct = inject_typos(CUSTOMER_REFUND_WITHIN_POLICY, random_seed=3)
    by_name = apply_mutation("typo_injection", CUSTOMER_REFUND_WITHIN_POLICY, random_seed=3)

    assert by_name == direct


def test_apply_mutation_rejects_an_unknown_mutation_type() -> None:
    with pytest.raises(ValueError):
        apply_mutation("not_a_real_mutation", CUSTOMER_REFUND_WITHIN_POLICY, random_seed=1)
