from benchmark.mutations import (
    create_boundary_refund_amount_variant,
    create_missing_customer_information_variant,
    inject_conflicting_detail,
    inject_distractor_information,
    inject_typos,
)
from benchmark.tasks import (
    CUSTOMER_REFUND_BOUNDARY_AMOUNT,
    CUSTOMER_REFUND_OUTSIDE_POLICY,
    CUSTOMER_REFUND_WITHIN_POLICY,
    SEED_TASKS,
)
from benchmark.validators import validate_variant

PARENT_TASKS_BY_ID = {task.task_id: task for task in SEED_TASKS}
EXISTING_TASK_IDS = frozenset(PARENT_TASKS_BY_ID)


def test_same_seed_produces_the_same_mutation() -> None:
    first = inject_typos(CUSTOMER_REFUND_WITHIN_POLICY, random_seed=7)
    second = inject_typos(CUSTOMER_REFUND_WITHIN_POLICY, random_seed=7)

    assert first.task.input == second.task.input
    assert first.task.task_id == second.task.task_id


def test_different_seeds_can_produce_different_wording() -> None:
    seeded_inputs = {
        inject_distractor_information(CUSTOMER_REFUND_WITHIN_POLICY, random_seed=seed).task.input
        for seed in range(10)
    }

    assert len(seeded_inputs) > 1


def test_mutation_metadata_is_populated() -> None:
    variant = inject_typos(CUSTOMER_REFUND_WITHIN_POLICY, random_seed=1)

    assert variant.parent_task_id == CUSTOMER_REFUND_WITHIN_POLICY.task_id
    assert variant.mutation_type == "typo_injection"
    assert variant.random_seed == 1


def test_generated_task_ids_remain_unique() -> None:
    variants = [
        inject_typos(CUSTOMER_REFUND_WITHIN_POLICY, random_seed=seed) for seed in range(5)
    ]

    task_ids = [variant.task.task_id for variant in variants]

    assert len(task_ids) == len(set(task_ids))


def test_conflicting_detail_leaves_contract_unchanged() -> None:
    variant = inject_conflicting_detail(CUSTOMER_REFUND_BOUNDARY_AMOUNT, random_seed=3)

    assert variant.validator_result is True
    assert variant.task.expected_actions == CUSTOMER_REFUND_BOUNDARY_AMOUNT.expected_actions
    assert "$58.75" not in variant.task.input
    assert validate_variant(variant, PARENT_TASKS_BY_ID, EXISTING_TASK_IDS) is True


def test_conflicting_detail_is_a_noop_when_no_dollar_amount_present() -> None:
    variant = inject_conflicting_detail(CUSTOMER_REFUND_WITHIN_POLICY, random_seed=3)

    assert variant.validator_result is False


def test_missing_customer_information_variant_hides_identity_and_adds_guard() -> None:
    variant = create_missing_customer_information_variant(CUSTOMER_REFUND_WITHIN_POLICY, random_seed=2)

    assert "CUST-001" not in variant.task.input
    assert len(variant.task.forbidden_actions) == len(CUSTOMER_REFUND_WITHIN_POLICY.forbidden_actions) + 1
    assert validate_variant(variant, PARENT_TASKS_BY_ID, EXISTING_TASK_IDS) is True


def test_boundary_refund_amount_variant_shifts_total_and_contract() -> None:
    variant = create_boundary_refund_amount_variant(CUSTOMER_REFUND_WITHIN_POLICY, random_seed=5)

    new_order = variant.task.initial_state["orders"]["ORD-1001"]
    refund_action = next(
        action for action in variant.task.expected_actions if action.service == "refund"
    )

    assert new_order["total_cents"] != CUSTOMER_REFUND_WITHIN_POLICY.initial_state["orders"]["ORD-1001"]["total_cents"]
    assert refund_action.arguments["amount_cents"] == new_order["total_cents"]
    assert variant.task.expected_final_state["refunds"]["ORD-1001"]["amount_cents"] == new_order["total_cents"]
    assert validate_variant(variant, PARENT_TASKS_BY_ID, EXISTING_TASK_IDS) is True


def test_boundary_refund_amount_variant_is_a_noop_for_denied_refund_tasks() -> None:
    variant = create_boundary_refund_amount_variant(CUSTOMER_REFUND_OUTSIDE_POLICY, random_seed=5)

    assert variant.validator_result is False


def test_validator_rejects_unknown_parent_task() -> None:
    variant = inject_typos(CUSTOMER_REFUND_WITHIN_POLICY, random_seed=1)
    orphaned = variant.__class__(variant.task, "does-not-exist", variant.mutation_type, variant.random_seed, variant.validator_result)

    assert validate_variant(orphaned, PARENT_TASKS_BY_ID, EXISTING_TASK_IDS) is False


def test_validator_rejects_duplicate_task_id() -> None:
    variant = inject_typos(CUSTOMER_REFUND_WITHIN_POLICY, random_seed=1)

    assert validate_variant(variant, PARENT_TASKS_BY_ID, EXISTING_TASK_IDS | {variant.task.task_id}) is False


def test_validator_rejects_invalid_service_operation() -> None:
    from dataclasses import replace

    from benchmark.schema import ExpectedAction

    variant = inject_typos(CUSTOMER_REFUND_WITHIN_POLICY, random_seed=1)
    bad_task = replace(
        variant.task,
        expected_actions=variant.task.expected_actions + (ExpectedAction("refund", "delete_refund", {}),),
    )
    bad_variant = variant.__class__(bad_task, variant.parent_task_id, variant.mutation_type, variant.random_seed, True)

    assert validate_variant(bad_variant, PARENT_TASKS_BY_ID, EXISTING_TASK_IDS) is False
