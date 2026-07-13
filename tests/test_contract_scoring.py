from benchmark.tasks import CUSTOMER_REFUND_WITHIN_POLICY
from judges.contracts import ToolCall, score_actions


def test_score_actions_passes_when_expected_calls_are_seen() -> None:
    calls = (
        ToolCall("customer", "get_customer", {"customer_id": "CUST-001"}),
        ToolCall("order", "get_order", {"order_id": "ORD-1001"}),
        ToolCall("policy", "check_refund_policy", {"order_id": "ORD-1001"}),
        ToolCall("refund", "create_refund", {"order_id": "ORD-1001", "amount_cents": 4200}),
        ToolCall("ticket", "update_ticket", {"ticket_id": "TICK-9001", "status": "resolved"}),
    )

    score = score_actions(CUSTOMER_REFUND_WITHIN_POLICY, calls)

    assert score.passed is True
    assert score.missing_expected_actions == ()
    assert score.forbidden_actions_seen == ()


def test_score_actions_fails_when_expected_call_is_missing() -> None:
    calls = (ToolCall("customer", "get_customer", {"customer_id": "CUST-001"}),)

    score = score_actions(CUSTOMER_REFUND_WITHIN_POLICY, calls)

    assert score.passed is False
    assert "refund.create_refund" in score.missing_expected_actions
