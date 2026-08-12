"""Covers the TaskExecutionResult shaping on top of judges.contracts.score_run.

Contract-check correctness itself (missing/forbidden actions, final-state diffing) is
covered by tests/test_contract_scoring.py and tests/test_run_scoring.py; this file only
checks the status/passed mapping into the platform's execution result contract.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.execution_scoring import score_execution
from app.schemas import AgentVersion
from benchmark.tasks import CUSTOMER_REFUND_WITHIN_POLICY
from runner.model_client import ModelReply, ScriptedModelClient, ToolCallRequest
from runner.runner import run_task


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


async def test_passed_contract_score_maps_to_passed_execution_result() -> None:
    model = ScriptedModelClient(
        [
            ModelReply(
                finish_reason="tool_calls",
                tool_calls=(ToolCallRequest("c1", "customer", "get_customer", {"customer_id": "CUST-001"}),),
            ),
            ModelReply(
                finish_reason="tool_calls",
                tool_calls=(ToolCallRequest("c2", "order", "get_order", {"order_id": "ORD-1001"}),),
            ),
            ModelReply(
                finish_reason="tool_calls",
                tool_calls=(ToolCallRequest("c3", "policy", "check_refund_policy", {"order_id": "ORD-1001"}),),
            ),
            ModelReply(
                finish_reason="tool_calls",
                tool_calls=(
                    ToolCallRequest(
                        "c4",
                        "refund",
                        "create_refund",
                        {
                            "order_id": "ORD-1001",
                            "requesting_customer_id": "CUST-001",
                            "amount_cents": 4200,
                            "reason": "damaged_item",
                        },
                    ),
                ),
            ),
            ModelReply(
                finish_reason="tool_calls",
                tool_calls=(
                    ToolCallRequest("c5", "ticket", "update_ticket", {"ticket_id": "TICK-9001", "status": "resolved"}),
                ),
            ),
            ModelReply(finish_reason="stop", content="Refund issued."),
        ]
    )

    result = await run_task(_version(), CUSTOMER_REFUND_WITHIN_POLICY, model)
    execution_result, contract_score = score_execution(CUSTOMER_REFUND_WITHIN_POLICY, result)

    assert contract_score.passed is True
    assert execution_result.status == "passed"
    assert execution_result.passed is True
    assert execution_result.final_output == "Refund issued."


async def test_failed_contract_score_maps_to_failed_execution_result() -> None:
    model = ScriptedModelClient(
        [
            ModelReply(
                finish_reason="tool_calls",
                tool_calls=(ToolCallRequest("c1", "customer", "get_customer", {"customer_id": "CUST-001"}),),
            ),
            ModelReply(finish_reason="stop", content="Done."),
        ]
    )

    result = await run_task(_version(), CUSTOMER_REFUND_WITHIN_POLICY, model)
    execution_result, contract_score = score_execution(CUSTOMER_REFUND_WITHIN_POLICY, result)

    assert contract_score.passed is False
    assert execution_result.status == "failed"
    assert execution_result.passed is False


async def test_max_steps_exceeded_is_errored_regardless_of_partial_contract_progress() -> None:
    reply = ModelReply(
        finish_reason="tool_calls",
        tool_calls=(ToolCallRequest("c1", "customer", "get_customer", {"customer_id": "CUST-001"}),),
    )
    model = ScriptedModelClient([reply, reply])

    result = await run_task(_version(), CUSTOMER_REFUND_WITHIN_POLICY, model, max_steps=2)
    execution_result, _contract_score = score_execution(CUSTOMER_REFUND_WITHIN_POLICY, result)

    assert execution_result.status == "errored"
    assert execution_result.passed is False
    assert execution_result.final_output == "(agent did not produce a final answer)"
