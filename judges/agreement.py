"""Agreement and disagreement analysis across multiple judge verdicts.

Per the project's evaluation principle that judge disagreement should be
surfaced rather than averaged away, this reports consensus (or the lack of
it) instead of collapsing multiple verdicts into a single opaque score.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from itertools import combinations
from typing import Iterable

from judges.llm import JudgeVerdict


@dataclass(frozen=True)
class AgreementReport:
    task_id: str
    verdicts: tuple[JudgeVerdict, ...]
    consensus_label: str | None
    agreement_rate: float
    disagreement: bool


def summarize_agreement(
    task_id: str,
    verdicts: tuple[JudgeVerdict, ...],
    disagreement_threshold: float = 1.0,
) -> AgreementReport:
    """Summarize a task's judge verdicts.

    `consensus_label` is the plurality label, or None on an exact tie.
    `disagreement` is True whenever the plurality's share of verdicts falls
    below `disagreement_threshold` (default: flag anything short of
    unanimous, since even one dissenting judge is signal worth surfacing).
    """

    if not verdicts:
        raise ValueError("summarize_agreement requires at least one verdict")

    label_counts = Counter(verdict.label for verdict in verdicts)
    max_count = max(label_counts.values())
    top_labels = [label for label, count in label_counts.items() if count == max_count]
    consensus_label = top_labels[0] if len(top_labels) == 1 else None
    agreement_rate = max_count / len(verdicts)

    return AgreementReport(
        task_id=task_id,
        verdicts=verdicts,
        consensus_label=consensus_label,
        agreement_rate=agreement_rate,
        disagreement=agreement_rate < disagreement_threshold,
    )


def pairwise_agreement_rate(verdicts: tuple[JudgeVerdict, ...]) -> float:
    """Fraction of judge pairs that assigned the same label."""

    if len(verdicts) < 2:
        return 1.0
    pairs = list(combinations(verdicts, 2))
    agreeing = sum(1 for first, second in pairs if first.label == second.label)
    return agreeing / len(pairs)


def flag_disagreements(reports: Iterable[AgreementReport]) -> tuple[AgreementReport, ...]:
    """Return only the reports flagged for disagreement, for review queues."""

    return tuple(report for report in reports if report.disagreement)
