from benchmark.schema import Difficulty
from benchmark.tasks import SEED_TASKS


def test_seed_task_ids_are_unique() -> None:
    task_ids = [task.task_id for task in SEED_TASKS]

    assert len(task_ids) == len(set(task_ids))


def test_seed_tasks_have_required_metadata() -> None:
    for task in SEED_TASKS:
        assert task.input
        assert task.initial_state
        assert task.expected_actions
        assert task.tags
        assert task.difficulty in Difficulty


def test_seed_tasks_cover_core_refund_policy_cases() -> None:
    all_tags = {tag for task in SEED_TASKS for tag in task.tags}

    assert "within_policy" in all_tags
    assert "outside_policy" in all_tags
    assert "boundary_value" in all_tags
    assert "identity_mismatch" in all_tags
    assert "duplicate_refund" in all_tags
