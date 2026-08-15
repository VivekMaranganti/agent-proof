from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.schemas import AgentVersion
from app.trace import ToolCallPayload, ToolResultPayload, Trace
from benchmark.tasks import CUSTOMER_REFUND_WITHIN_POLICY
from judges.contracts import ToolCall, extract_tool_calls, score_run
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
        content_hash="contenthash1234",
        created_at=datetime.now(UTC),
    )


def test_extract_tool_calls_pulls_only_tool_call_steps_in_order() -> None:
    trace = Trace(execution_id=uuid4())
    call_step = trace.append(
        ToolCallPayload(call_id="c1", service="order", operation="get_order", arguments={"order_id": "o-1"})
    )
    trace.append(ToolResultPayload(call_id="c1", result={"order_id": "o-1"}), parent_step_id=call_step.id)

    calls = extract_tool_calls(trace)

    assert calls == (ToolCall("order", "get_order", {"order_id": "o-1"}),)


async def test_score_run_passes_for_a_fully_resolved_run() -> None:
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
                    ToolCallRequest(
                        "c5", "ticket", "update_ticket", {"ticket_id": "TICK-9001", "status": "resolved"}
                    ),
                ),
            ),
            ModelReply(finish_reason="stop", content="Refund issued."),
        ]
    )

    result = await run_task(_version(), CUSTOMER_REFUND_WITHIN_POLICY, model, execution_id=uuid4())
    score = score_run(CUSTOMER_REFUND_WITHIN_POLICY, result)

    assert score.passed is True
    assert score.missing_expected_actions == ()
    assert score.forbidden_actions_seen == ()
    assert score.final_state_mismatches == ()


async def test_score_run_fails_when_the_agent_skips_the_refund() -> None:
    model = ScriptedModelClient(
        [
            ModelReply(
                finish_reason="tool_calls",
                tool_calls=(ToolCallRequest("c1", "customer", "get_customer", {"customer_id": "CUST-001"}),),
            ),
            ModelReply(
                finish_reason="tool_calls",
                tool_calls=(
                    ToolCallRequest(
                        "c2", "ticket", "update_ticket", {"ticket_id": "TICK-9001", "status": "resolved"}
                    ),
                ),
            ),
            ModelReply(finish_reason="stop", content="Ticket resolved."),
        ]
    )

    result = await run_task(_version(), CUSTOMER_REFUND_WITHIN_POLICY, model, execution_id=uuid4())
    score = score_run(CUSTOMER_REFUND_WITHIN_POLICY, result)

    assert score.passed is False
    assert "refund.create_refund" in score.missing_expected_actions
    assert any(mismatch.startswith("refunds.ORD-1001") for mismatch in score.final_state_mismatches)
