import pytest

from benchmark.tasks import CUSTOMER_REFUND_WITHIN_POLICY
from judges.contracts import ToolCall
from judges.llm import POLICY_JUDGE, RESPONSE_QUALITY_JUDGE, JudgeResponseError, parse_judge_response


class FakeModelCaller:
    def __init__(self, response: str) -> None:
        self.response = response
        self.last_prompt: str | None = None

    def __call__(self, prompt: str) -> str:
        self.last_prompt = prompt
        return self.response


def test_parse_judge_response_extracts_all_fields() -> None:
    label, confidence, rationale = parse_judge_response(
        "LABEL: pass\nCONFIDENCE: 0.9\nRATIONALE: The agent verified ownership before refunding."
    )

    assert label == "pass"
    assert confidence == 0.9
    assert rationale == "The agent verified ownership before refunding."


def test_parse_judge_response_rejects_missing_fields() -> None:
    with pytest.raises(JudgeResponseError):
        parse_judge_response("LABEL: pass\nCONFIDENCE: 0.9")


def test_parse_judge_response_rejects_out_of_range_confidence() -> None:
    with pytest.raises(JudgeResponseError):
        parse_judge_response("LABEL: pass\nCONFIDENCE: 1.5\nRATIONALE: too confident")


def test_parse_judge_response_rejects_an_invalid_label() -> None:
    with pytest.raises(JudgeResponseError):
        parse_judge_response("LABEL: maybe\nCONFIDENCE: 0.5\nRATIONALE: unsure")


def test_judge_evaluate_returns_a_verdict_built_from_the_model_response() -> None:
    caller = FakeModelCaller("LABEL: pass\nCONFIDENCE: 0.8\nRATIONALE: Looks correct.")
    calls = (ToolCall("customer", "get_customer", {"customer_id": "CUST-001"}),)

    verdict = POLICY_JUDGE.evaluate(
        CUSTOMER_REFUND_WITHIN_POLICY, calls, "Your refund has been issued.", caller
    )

    assert verdict.judge_name == "policy_judge"
    assert verdict.label == "pass"
    assert verdict.confidence == 0.8
    assert verdict.rationale == "Looks correct."
    assert verdict.rubric_version == "1"


def test_judge_prompt_includes_task_input_tool_calls_and_final_response() -> None:
    caller = FakeModelCaller("LABEL: pass\nCONFIDENCE: 1.0\nRATIONALE: ok")
    calls = (ToolCall("refund", "create_refund", {"order_id": "ORD-1001", "amount_cents": 4200}),)

    POLICY_JUDGE.evaluate(CUSTOMER_REFUND_WITHIN_POLICY, calls, "Refund issued.", caller)

    assert caller.last_prompt is not None
    assert CUSTOMER_REFUND_WITHIN_POLICY.input in caller.last_prompt
    assert "refund.create_refund" in caller.last_prompt
    assert "Refund issued." in caller.last_prompt


def test_judge_prompt_handles_a_missing_final_response() -> None:
    caller = FakeModelCaller("LABEL: uncertain\nCONFIDENCE: 0.4\nRATIONALE: no response given")

    RESPONSE_QUALITY_JUDGE.evaluate(CUSTOMER_REFUND_WITHIN_POLICY, (), None, caller)

    assert caller.last_prompt is not None
    assert "no final response provided" in caller.last_prompt


def test_policy_and_response_quality_judges_use_distinct_rubrics() -> None:
    assert POLICY_JUDGE.rubric != RESPONSE_QUALITY_JUDGE.rubric
    assert POLICY_JUDGE.name != RESPONSE_QUALITY_JUDGE.name


def test_judge_raises_when_the_model_response_is_unparseable() -> None:
    caller = FakeModelCaller("I think this looks fine overall.")

    with pytest.raises(JudgeResponseError):
        POLICY_JUDGE.evaluate(CUSTOMER_REFUND_WITHIN_POLICY, (), None, caller)
