"""Runner + scorer against real seed tasks, hand-labeled pass/fail.

Each task below is worked twice: once the way a correct agent would (matching its
labeled outcome) and once with a deliberate deviation from the contract, to prove
the scorer actually discriminates rather than always agreeing with the label.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.schemas import AgentVersion
from benchmark.tasks import CUSTOMER_REFUND_OUTSIDE_POLICY, CUSTOMER_REFUND_WITHIN_POLICY
from runner.model_client import ModelReply, ScriptedModelClient, ToolCallRequest
from runner.runner import run_task
from runner.scoring import score_run


def _version() -> AgentVersion:
    return AgentVersion(
        name="test-agent",
        git_sha="abc1234",
        model="test-model",
        system_prompt="You are a support agent. Follow policy exactly.",
        tool_schema_hash="hash1234",
        config={},
        created_at=datetime.now(UTC),
    )


def _final(content: str) -> ModelReply:
    return ModelReply(finish_reason="stop", content=content)


def _call(call_id: str, service: str, operation: str, **arguments) -> ModelReply:
    return ModelReply(finish_reason="tool_calls", tool_calls=(ToolCallRequest(call_id, service, operation, arguments),))


async def test_within_policy_refund_correctly_resolved_passes() -> None:
    model = ScriptedModelClient(
        [
            _call("c1", "customer", "get_customer", customer_id="CUST-001"),
            _call("c2", "order", "get_order", order_id="ORD-1001"),
            _call("c3", "policy", "check_refund_policy", order_id="ORD-1001"),
            _call(
                "c4",
                "refund",
                "create_refund",
                order_id="ORD-1001",
                requesting_customer_id="CUST-001",
                amount_cents=4200,
                reason="damaged_item",
            ),
            _call("c5", "ticket", "update_ticket", ticket_id="TICK-9001", status="resolved"),
            _final("Refund issued for order ORD-1001."),
        ]
    )

    result = await run_task(_version(), CUSTOMER_REFUND_WITHIN_POLICY, model)
    execution_result, contract_score = score_run(CUSTOMER_REFUND_WITHIN_POLICY, result)

    assert contract_score.passed is True
    assert contract_score.missing_expected_actions == ()
    assert contract_score.forbidden_actions_seen == ()
    assert contract_score.final_state_mismatches == ()
    assert execution_result.status == "passed"
    assert execution_result.passed is True


async def test_within_policy_refund_skipped_fails() -> None:
    model = ScriptedModelClient(
        [
            _call("c1", "customer", "get_customer", customer_id="CUST-001"),
            _call("c2", "order", "get_order", order_id="ORD-1001"),
            _call("c3", "ticket", "update_ticket", ticket_id="TICK-9001", status="resolved"),
            _final("Ticket updated."),
        ]
    )

    result = await run_task(_version(), CUSTOMER_REFUND_WITHIN_POLICY, model)
    execution_result, contract_score = score_run(CUSTOMER_REFUND_WITHIN_POLICY, result)

    assert contract_score.passed is False
    assert "refund.create_refund" in contract_score.missing_expected_actions
    assert execution_result.status == "failed"
    assert execution_result.passed is False


async def test_outside_policy_refund_correctly_denied_passes() -> None:
    model = ScriptedModelClient(
        [
            _call("c1", "customer", "get_customer", customer_id="CUST-002"),
            _call("c2", "order", "get_order", order_id="ORD-2001"),
            _call("c3", "policy", "check_refund_policy", order_id="ORD-2001"),
            _call("c4", "ticket", "update_ticket", ticket_id="TICK-9002", status="resolved"),
            _final("This order is outside the refund window, so I've closed the ticket without a refund."),
        ]
    )

    result = await run_task(_version(), CUSTOMER_REFUND_OUTSIDE_POLICY, model)
    execution_result, contract_score = score_run(CUSTOMER_REFUND_OUTSIDE_POLICY, result)

    assert contract_score.passed is True
    assert execution_result.status == "passed"


async def test_outside_policy_refund_wrongly_attempted_fails() -> None:
    model = ScriptedModelClient(
        [
            _call("c1", "customer", "get_customer", customer_id="CUST-002"),
            _call("c2", "order", "get_order", order_id="ORD-2001"),
            _call("c3", "refund", "create_refund", order_id="ORD-2001", requesting_customer_id="CUST-002", amount_cents=12900, reason="stopped_working"),
            _call("c4", "ticket", "update_ticket", ticket_id="TICK-9002", status="resolved"),
            _final("Refund issued."),
        ]
    )

    result = await run_task(_version(), CUSTOMER_REFUND_OUTSIDE_POLICY, model)
    execution_result, contract_score = score_run(CUSTOMER_REFUND_OUTSIDE_POLICY, result)

    assert contract_score.passed is False
    assert len(contract_score.forbidden_actions_seen) == 1
    assert execution_result.status == "failed"


async def test_max_steps_exceeded_is_scored_as_errored_not_passed() -> None:
    reply = _call("c1", "order", "get_order", order_id="ORD-1001")
    model = ScriptedModelClient([reply, reply])

    result = await run_task(_version(), CUSTOMER_REFUND_WITHIN_POLICY, model, max_steps=2)
    execution_result, contract_score = score_run(CUSTOMER_REFUND_WITHIN_POLICY, result)

    assert execution_result.status == "errored"
    assert execution_result.passed is False
