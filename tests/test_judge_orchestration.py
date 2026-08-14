from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.schemas import AgentVersion
from benchmark.tasks import CUSTOMER_REFUND_WITHIN_POLICY
from judges.llm import POLICY_JUDGE, RESPONSE_QUALITY_JUDGE
from judges.orchestration import run_judges, select_judges
from runner.model_client import ModelReply, ScriptedModelClient, ToolCallRequest
from runner.runner import run_task


class QueuedModelCaller:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)

    def __call__(self, prompt: str) -> str:
        return self._responses.pop(0)


def _version() -> AgentVersion:
    return AgentVersion(
        name="test-agent",
        git_sha="abc1234",
        model="test-model",
        system_prompt="You are a support agent.",
        tool_schema_hash="hash1234",
        config={},
        created_at=datetime.now(UTC),
    )


def test_select_judges_includes_response_quality_when_a_final_response_exists() -> None:
    judges = select_judges("Your refund has been issued.")

    assert judges == (POLICY_JUDGE, RESPONSE_QUALITY_JUDGE)


def test_select_judges_only_includes_policy_when_there_is_no_final_response() -> None:
    assert select_judges(None) == (POLICY_JUDGE,)
    assert select_judges("") == (POLICY_JUDGE,)


async def test_run_judges_produces_a_verdict_from_each_selected_judge() -> None:
    model = ScriptedModelClient(
        [
            ModelReply(
                finish_reason="tool_calls",
                tool_calls=(ToolCallRequest("c1", "customer", "get_customer", {"customer_id": "CUST-001"}),),
            ),
            ModelReply(finish_reason="stop", content="Your refund has been issued."),
        ]
    )
    result = await run_task(_version(), CUSTOMER_REFUND_WITHIN_POLICY, model, execution_id=uuid4())

    caller = QueuedModelCaller(
        [
            "LABEL: pass\nCONFIDENCE: 0.8\nRATIONALE: Identity was checked first.",
            "LABEL: pass\nCONFIDENCE: 0.9\nRATIONALE: Clear and complete reply.",
        ]
    )

    verdicts = run_judges(CUSTOMER_REFUND_WITHIN_POLICY, result, caller)

    assert [verdict.judge_name for verdict in verdicts] == ["policy_judge", "response_quality_judge"]
    assert all(verdict.task_id == CUSTOMER_REFUND_WITHIN_POLICY.task_id for verdict in verdicts)


async def test_run_judges_skips_response_quality_when_the_agent_never_answered() -> None:
    reply = ModelReply(
        finish_reason="tool_calls",
        tool_calls=(ToolCallRequest("c1", "order", "get_order", {"order_id": "ORD-1001"}),),
    )
    model = ScriptedModelClient([reply, reply])
    result = await run_task(_version(), CUSTOMER_REFUND_WITHIN_POLICY, model, execution_id=uuid4(), max_steps=2)
    assert result.max_steps_exceeded is True
    assert result.final_output is None

    caller = QueuedModelCaller(["LABEL: uncertain\nCONFIDENCE: 0.3\nRATIONALE: Ran out of steps before resolving."])

    verdicts = run_judges(CUSTOMER_REFUND_WITHIN_POLICY, result, caller)

    assert len(verdicts) == 1
    assert verdicts[0].judge_name == "policy_judge"
