import pytest

from judges.agreement import flag_disagreements, pairwise_agreement_rate, summarize_agreement
from judges.llm import JudgeVerdict


def _verdict(judge_name: str, label: str) -> JudgeVerdict:
    return JudgeVerdict(
        judge_name=judge_name, rubric_version="1", label=label, confidence=0.9, rationale="r"
    )


def test_summarize_agreement_reports_full_consensus() -> None:
    verdicts = (_verdict("a", "pass"), _verdict("b", "pass"), _verdict("c", "pass"))

    report = summarize_agreement("task-1", verdicts)

    assert report.consensus_label == "pass"
    assert report.agreement_rate == 1.0
    assert report.disagreement is False


def test_summarize_agreement_flags_a_split_verdict() -> None:
    verdicts = (_verdict("a", "pass"), _verdict("b", "fail"))

    report = summarize_agreement("task-2", verdicts)

    assert report.consensus_label is None
    assert report.agreement_rate == 0.5
    assert report.disagreement is True


def test_summarize_agreement_reports_a_plurality_consensus_but_still_flags_it() -> None:
    verdicts = (_verdict("a", "pass"), _verdict("b", "pass"), _verdict("c", "fail"))

    report = summarize_agreement("task-3", verdicts)

    assert report.consensus_label == "pass"
    assert report.disagreement is True


def test_summarize_agreement_rejects_empty_verdicts() -> None:
    with pytest.raises(ValueError):
        summarize_agreement("task-4", ())


def test_pairwise_agreement_rate_for_full_consensus() -> None:
    verdicts = (_verdict("a", "pass"), _verdict("b", "pass"), _verdict("c", "pass"))

    assert pairwise_agreement_rate(verdicts) == 1.0


def test_pairwise_agreement_rate_for_a_single_verdict() -> None:
    assert pairwise_agreement_rate((_verdict("a", "pass"),)) == 1.0


def test_pairwise_agreement_rate_for_a_split_verdict() -> None:
    verdicts = (_verdict("a", "pass"), _verdict("b", "fail"))

    assert pairwise_agreement_rate(verdicts) == 0.0


def test_flag_disagreements_filters_to_only_disagreeing_reports() -> None:
    consensus = summarize_agreement("task-consensus", (_verdict("a", "pass"), _verdict("b", "pass")))
    split = summarize_agreement("task-split", (_verdict("a", "pass"), _verdict("b", "fail")))

    flagged = flag_disagreements((consensus, split))

    assert flagged == (split,)
