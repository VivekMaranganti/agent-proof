from benchmark.tasks import (
    ITEM_REPLACEMENT_WITHIN_POLICY,
    ORDER_CANCELLATION_BEFORE_SHIPPING,
    ORDER_CANCELLATION_DENIED_AFTER_DELIVERY,
    TICKET_ESCALATION_FOR_UNRESOLVED_ISSUE,
)
from judges.contracts import ToolCall, score_actions
from tool_environment import SupportToolEnvironment


def test_order_cancellation_before_shipping_scores_as_passed() -> None:
    env = SupportToolEnvironment(ORDER_CANCELLATION_BEFORE_SHIPPING.initial_state)
    env.customer.get_customer("CUST-008")
    env.order.get_order("ORD-8001")
    env.order.cancel_order("ORD-8001", "CUST-008")
    env.ticket.update_ticket("TICK-9008", status="resolved")

    calls = (
        ToolCall("customer", "get_customer", {"customer_id": "CUST-008"}),
        ToolCall("order", "get_order", {"order_id": "ORD-8001"}),
        ToolCall("order", "cancel_order", {"order_id": "ORD-8001"}),
        ToolCall("ticket", "update_ticket", {"ticket_id": "TICK-9008", "status": "resolved"}),
    )

    score = score_actions(ORDER_CANCELLATION_BEFORE_SHIPPING, calls, env.snapshot())

    assert score.passed is True


def test_order_cancellation_denied_after_delivery_scores_as_passed_without_cancelling() -> None:
    env = SupportToolEnvironment(ORDER_CANCELLATION_DENIED_AFTER_DELIVERY.initial_state)
    env.customer.get_customer("CUST-009")
    env.order.get_order("ORD-9001")
    env.ticket.update_ticket("TICK-9009", status="resolved")

    calls = (
        ToolCall("customer", "get_customer", {"customer_id": "CUST-009"}),
        ToolCall("order", "get_order", {"order_id": "ORD-9001"}),
        ToolCall("ticket", "update_ticket", {"ticket_id": "TICK-9009", "status": "resolved"}),
    )

    score = score_actions(ORDER_CANCELLATION_DENIED_AFTER_DELIVERY, calls, env.snapshot())

    assert score.passed is True


def test_item_replacement_within_policy_scores_as_passed() -> None:
    env = SupportToolEnvironment(ITEM_REPLACEMENT_WITHIN_POLICY.initial_state)
    env.customer.get_customer("CUST-010")
    env.order.get_order("ORD-10001")
    env.policy.check_replacement_policy("ORD-10001")
    env.order.replace_item("ORD-10001", "CUST-010", "SHIRT-BLU-L", "wrong_size")
    env.ticket.update_ticket("TICK-9010", status="resolved")

    calls = (
        ToolCall("customer", "get_customer", {"customer_id": "CUST-010"}),
        ToolCall("order", "get_order", {"order_id": "ORD-10001"}),
        ToolCall("policy", "check_replacement_policy", {"order_id": "ORD-10001"}),
        ToolCall("order", "replace_item", {"order_id": "ORD-10001", "sku": "SHIRT-BLU-L"}),
        ToolCall("ticket", "update_ticket", {"ticket_id": "TICK-9010", "status": "resolved"}),
    )

    score = score_actions(ITEM_REPLACEMENT_WITHIN_POLICY, calls, env.snapshot())

    assert score.passed is True


def test_ticket_escalation_scores_as_passed() -> None:
    env = SupportToolEnvironment(TICKET_ESCALATION_FOR_UNRESOLVED_ISSUE.initial_state)
    env.customer.get_customer("CUST-011")
    env.ticket.escalate_ticket("TICK-9011", "Customer requested a supervisor.")

    calls = (
        ToolCall("customer", "get_customer", {"customer_id": "CUST-011"}),
        ToolCall("ticket", "escalate_ticket", {"ticket_id": "TICK-9011"}),
    )

    score = score_actions(TICKET_ESCALATION_FOR_UNRESOLVED_ISSUE, calls, env.snapshot())

    assert score.passed is True
