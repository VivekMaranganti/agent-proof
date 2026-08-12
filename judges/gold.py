"""Human-labeled gold dataset format and judge-vs-gold calibration.

A gold set is a small collection of human-assigned labels for specific
tasks, used to check whether an LLM judge's verdicts agree with a human
reviewer applying the same rubric. One gold set calibrates one judge
dimension (e.g. policy correctness vs. response quality) — see
judges/rubrics/gold_labeling_guide.md for how a human should assign labels.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from judges.llm import JudgeLabel, JudgeVerdict


class DuplicateGoldLabelError(ValueError):
    """Raised when a gold set contains more than one label for the same task_id."""


@dataclass(frozen=True)
class GoldLabel:
    task_id: str
    label: JudgeLabel
    rationale: str
    labeler: str
    labeled_at: datetime


def gold_label_to_dict(gold: GoldLabel) -> dict[str, Any]:
    return {
        "task_id": gold.task_id,
        "label": gold.label,
        "rationale": gold.rationale,
        "labeler": gold.labeler,
        "labeled_at": gold.labeled_at.isoformat(),
    }


def gold_label_from_dict(data: dict[str, Any]) -> GoldLabel:
    return GoldLabel(
        task_id=data["task_id"],
        label=data["label"],
        rationale=data["rationale"],
        labeler=data["labeler"],
        labeled_at=datetime.fromisoformat(data["labeled_at"]),
    )


def save_gold_labels(labels: Iterable[GoldLabel], path: str | Path) -> None:
    labels = tuple(labels)
    _index_by_task_id(labels)  # raises on duplicate task_id before writing
    payload = [gold_label_to_dict(label) for label in labels]
    Path(path).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def load_gold_labels(path: str | Path) -> tuple[GoldLabel, ...]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    labels = tuple(gold_label_from_dict(item) for item in payload)
    _index_by_task_id(labels)  # raises on duplicate task_id before returning
    return labels


def _index_by_task_id(labels: Iterable[GoldLabel]) -> dict[str, GoldLabel]:
    index: dict[str, GoldLabel] = {}
    for label in labels:
        if label.task_id in index:
            raise DuplicateGoldLabelError(f"Duplicate gold label for task: {label.task_id}")
        index[label.task_id] = label
    return index


@dataclass(frozen=True)
class GoldComparison:
    task_id: str
    judge_name: str
    judge_label: JudgeLabel
    gold_label: JudgeLabel
    agrees: bool


def compare_verdicts_to_gold(
    verdicts: Iterable[JudgeVerdict], gold_labels: Iterable[GoldLabel]
) -> tuple[GoldComparison, ...]:
    """Pair each verdict with its gold label by task_id.

    Verdicts for a task_id with no gold label are silently skipped: the gold
    set is expected to cover only a subset of the full benchmark suite.
    """

    gold_by_task_id = _index_by_task_id(gold_labels)
    comparisons = []
    for verdict in verdicts:
        gold = gold_by_task_id.get(verdict.task_id)
        if gold is None:
            continue
        comparisons.append(
            GoldComparison(
                task_id=verdict.task_id,
                judge_name=verdict.judge_name,
                judge_label=verdict.label,
                gold_label=gold.label,
                agrees=verdict.label == gold.label,
            )
        )
    return tuple(comparisons)


@dataclass(frozen=True)
class GoldAgreementReport:
    judge_name: str
    comparisons: tuple[GoldComparison, ...]
    agreement_rate: float


def summarize_gold_agreement(
    judge_name: str, comparisons: Iterable[GoldComparison]
) -> GoldAgreementReport:
    relevant = tuple(comparison for comparison in comparisons if comparison.judge_name == judge_name)
    if not relevant:
        raise ValueError(f"No gold comparisons found for judge: {judge_name}")

    agreement_rate = sum(1 for comparison in relevant if comparison.agrees) / len(relevant)
    return GoldAgreementReport(judge_name=judge_name, comparisons=relevant, agreement_rate=agreement_rate)
