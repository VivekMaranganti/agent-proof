from benchmark.tasks import CUSTOMER_REFUND_WITHIN_POLICY
from judges.contracts import ToolCall, score_actions
from tool_environment import SupportToolEnvironment


def _run_full_resolution(env: SupportToolEnvironment) -> tuple[ToolCall, ...]:
    env.customer.get_customer("CUST-001")
    env.order.get_order("ORD-1001")
    env.policy.check_refund_policy("ORD-1001")
    env.refund.create_refund("ORD-1001", 4200, "damaged_item")
    env.ticket.update_ticket("TICK-9001", status="resolved")

    return (
        ToolCall("customer", "get_customer", {"customer_id": "CUST-001"}),
        ToolCall("order", "get_order", {"order_id": "ORD-1001"}),
        ToolCall("policy", "check_refund_policy", {"order_id": "ORD-1001"}),
        ToolCall("refund", "create_refund", {"order_id": "ORD-1001", "amount_cents": 4200}),
        ToolCall("ticket", "update_ticket", {"ticket_id": "TICK-9001", "status": "resolved"}),
    )


def test_score_actions_passes_when_expected_calls_and_final_state_match() -> None:
    env = SupportToolEnvironment(CUSTOMER_REFUND_WITHIN_POLICY.initial_state)
    calls = _run_full_resolution(env)

    score = score_actions(CUSTOMER_REFUND_WITHIN_POLICY, calls, env.snapshot())

    assert score.passed is True
    assert score.missing_expected_actions == ()
    assert score.forbidden_actions_seen == ()
    assert score.final_state_mismatches == ()


def test_score_actions_fails_when_expected_call_is_missing() -> None:
    calls = (ToolCall("customer", "get_customer", {"customer_id": "CUST-001"}),)

    score = score_actions(CUSTOMER_REFUND_WITHIN_POLICY, calls, CUSTOMER_REFUND_WITHIN_POLICY.initial_state)

    assert score.passed is False
    assert "refund.create_refund" in score.missing_expected_actions


def test_score_actions_fails_when_final_state_diverges() -> None:
    env = SupportToolEnvironment(CUSTOMER_REFUND_WITHIN_POLICY.initial_state)
    # Agent resolves the ticket but never actually issues the refund.
    env.customer.get_customer("CUST-001")
    env.order.get_order("ORD-1001")
    env.policy.check_refund_policy("ORD-1001")
    env.ticket.update_ticket("TICK-9001", status="resolved")

    calls = (
        ToolCall("customer", "get_customer", {"customer_id": "CUST-001"}),
        ToolCall("order", "get_order", {"order_id": "ORD-1001"}),
        ToolCall("policy", "check_refund_policy", {"order_id": "ORD-1001"}),
        ToolCall("refund", "create_refund", {"order_id": "ORD-1001", "amount_cents": 4200}),
        ToolCall("ticket", "update_ticket", {"ticket_id": "TICK-9001", "status": "resolved"}),
    )

    score = score_actions(CUSTOMER_REFUND_WITHIN_POLICY, calls, env.snapshot())

    assert score.passed is False
    assert score.missing_expected_actions == ()
    assert any(mismatch.startswith("refunds.ORD-1001") for mismatch in score.final_state_mismatches)


def test_score_actions_reports_wrong_ticket_status_as_a_mismatch() -> None:
    env = SupportToolEnvironment(CUSTOMER_REFUND_WITHIN_POLICY.initial_state)
    env.customer.get_customer("CUST-001")
    env.order.get_order("ORD-1001")
    env.policy.check_refund_policy("ORD-1001")
    env.refund.create_refund("ORD-1001", 4200, "damaged_item")
    env.ticket.update_ticket("TICK-9001", status="pending")

    calls = (
        ToolCall("customer", "get_customer", {"customer_id": "CUST-001"}),
        ToolCall("order", "get_order", {"order_id": "ORD-1001"}),
        ToolCall("policy", "check_refund_policy", {"order_id": "ORD-1001"}),
        ToolCall("refund", "create_refund", {"order_id": "ORD-1001", "amount_cents": 4200}),
        ToolCall("ticket", "update_ticket", {"ticket_id": "TICK-9001", "status": "pending"}),
    )

    score = score_actions(CUSTOMER_REFUND_WITHIN_POLICY, calls, env.snapshot())

    assert score.passed is False
    assert score.final_state_mismatches == ("tickets.TICK-9001.status: expected 'resolved', got 'pending'",)
