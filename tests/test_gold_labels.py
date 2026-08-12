from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from benchmark.tasks import SEED_TASKS
from judges.gold import (
    DuplicateGoldLabelError,
    GoldLabel,
    compare_verdicts_to_gold,
    gold_label_from_dict,
    gold_label_to_dict,
    load_gold_labels,
    save_gold_labels,
    summarize_gold_agreement,
)
from judges.llm import POLICY_JUDGE, JudgeVerdict

GOLD_SEED_PATH = Path(__file__).resolve().parent.parent / "judges" / "gold" / "policy_judge_seed.json"


class QueuedModelCaller:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)

    def __call__(self, prompt: str) -> str:
        return self._responses.pop(0)


def _gold(task_id: str = "task-1", label: str = "pass") -> GoldLabel:
    return GoldLabel(
        task_id=task_id, label=label, rationale="r", labeler="tester", labeled_at=datetime(2026, 1, 1, tzinfo=UTC)
    )


def _verdict(task_id: str, judge_name: str, label: str) -> JudgeVerdict:
    return JudgeVerdict(
        task_id=task_id, judge_name=judge_name, rubric_version="1", label=label, confidence=0.9, rationale="r"
    )


def test_gold_label_round_trips_through_dict() -> None:
    gold = _gold()

    assert gold_label_from_dict(gold_label_to_dict(gold)) == gold


def test_save_and_load_gold_labels_round_trip(tmp_path) -> None:
    labels = (_gold("task-1", "pass"), _gold("task-2", "fail"))
    path = tmp_path / "gold.json"

    save_gold_labels(labels, path)
    reloaded = load_gold_labels(path)

    assert reloaded == labels


def test_save_gold_labels_rejects_a_duplicate_task_id(tmp_path) -> None:
    labels = (_gold("task-1", "pass"), _gold("task-1", "fail"))

    with pytest.raises(DuplicateGoldLabelError):
        save_gold_labels(labels, tmp_path / "gold.json")


def test_load_gold_labels_rejects_a_duplicate_task_id(tmp_path) -> None:
    path = tmp_path / "gold.json"
    path.write_text(
        "["
        '{"task_id": "task-1", "label": "pass", "rationale": "r", "labeler": "t", "labeled_at": "2026-01-01T00:00:00+00:00"},'
        '{"task_id": "task-1", "label": "fail", "rationale": "r2", "labeler": "t", "labeled_at": "2026-01-01T00:00:00+00:00"}'
        "]",
        encoding="utf-8",
    )

    with pytest.raises(DuplicateGoldLabelError):
        load_gold_labels(path)


def test_compare_verdicts_to_gold_pairs_by_task_id_and_skips_unmatched() -> None:
    gold = (_gold("task-1", "pass"), _gold("task-2", "fail"))
    verdicts = (
        _verdict("task-1", "policy_judge", "pass"),
        _verdict("task-2", "policy_judge", "pass"),
        _verdict("task-unmatched", "policy_judge", "pass"),
    )

    comparisons = compare_verdicts_to_gold(verdicts, gold)

    assert len(comparisons) == 2
    assert comparisons[0].agrees is True
    assert comparisons[1].agrees is False


def test_summarize_gold_agreement_computes_the_agreement_rate() -> None:
    gold = (_gold("task-1", "pass"), _gold("task-2", "fail"), _gold("task-3", "pass"))
    verdicts = (
        _verdict("task-1", "policy_judge", "pass"),
        _verdict("task-2", "policy_judge", "pass"),
        _verdict("task-3", "policy_judge", "pass"),
    )

    comparisons = compare_verdicts_to_gold(verdicts, gold)
    report = summarize_gold_agreement("policy_judge", comparisons)

    assert report.agreement_rate == pytest.approx(2 / 3)


def test_summarize_gold_agreement_raises_when_the_judge_has_no_comparisons() -> None:
    comparisons = (
        _comparison_for("policy_judge"),
    )

    with pytest.raises(ValueError):
        summarize_gold_agreement("response_quality_judge", comparisons)


def _comparison_for(judge_name: str):
    gold = (_gold("task-1", "pass"),)
    verdicts = (_verdict("task-1", judge_name, "pass"),)
    return compare_verdicts_to_gold(verdicts, gold)[0]


def test_policy_judge_can_be_scored_against_the_seeded_gold_set_end_to_end() -> None:
    gold_labels = load_gold_labels(GOLD_SEED_PATH)
    tasks_by_id = {task.task_id: task for task in SEED_TASKS}
    assert all(gold.task_id in tasks_by_id for gold in gold_labels)

    # Script an agreeing verdict for every gold task except the last, which
    # deliberately disagrees to exercise the disagreement path too.
    responses = ["LABEL: pass\nCONFIDENCE: 0.9\nRATIONALE: matches policy."] * (len(gold_labels) - 1)
    responses.append("LABEL: fail\nCONFIDENCE: 0.6\nRATIONALE: looked wrong to the judge.")
    caller = QueuedModelCaller(responses)

    verdicts = tuple(
        POLICY_JUDGE.evaluate(tasks_by_id[gold.task_id], (), None, caller) for gold in gold_labels
    )

    comparisons = compare_verdicts_to_gold(verdicts, gold_labels)
    report = summarize_gold_agreement("policy_judge", comparisons)

    assert len(comparisons) == len(gold_labels)
    assert report.agreement_rate == pytest.approx((len(gold_labels) - 1) / len(gold_labels))
