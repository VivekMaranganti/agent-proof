import pytest

from benchmark.tasks import (
    CUSTOMER_ORDER_MISMATCH,
    CUSTOMER_REFUND_WITHIN_POLICY,
    DUPLICATE_REFUND_PREVENTION,
    ITEM_REPLACEMENT_WITHIN_POLICY,
    ORDER_CANCELLATION_BEFORE_SHIPPING,
    ORDER_CANCELLATION_DENIED_AFTER_DELIVERY,
    TICKET_ESCALATION_FOR_UNRESOLVED_ISSUE,
)
from tool_environment import SupportToolEnvironment
from tool_environment.errors import NotFoundError, PolicyViolationError


def test_customer_refund_flow_updates_state() -> None:
    env = SupportToolEnvironment(CUSTOMER_REFUND_WITHIN_POLICY.initial_state)

    customer = env.customer.get_customer("CUST-001")
    order = env.order.get_order("ORD-1001")
    policy = env.policy.check_refund_policy("ORD-1001")
    refund = env.refund.create_refund("ORD-1001", "CUST-001", 4200, "damaged_item")
    ticket = env.ticket.update_ticket("TICK-9001", status="resolved", note="Refund issued.")

    assert customer["name"] == "Avery Chen"
    assert order["total_cents"] == 4200
    assert policy["eligible"] is True
    assert refund["amount_cents"] == 4200
    assert ticket["status"] == "resolved"
    assert env.snapshot()["refunds"]["ORD-1001"]["reason"] == "damaged_item"


def test_create_refund_rejects_a_duplicate_refund() -> None:
    env = SupportToolEnvironment(DUPLICATE_REFUND_PREVENTION.initial_state)

    with pytest.raises(PolicyViolationError):
        env.refund.create_refund("ORD-7001", "CUST-007", 2400, "damaged_item")


def test_create_refund_rejects_a_cross_customer_refund() -> None:
    env = SupportToolEnvironment(CUSTOMER_ORDER_MISMATCH.initial_state)

    with pytest.raises(PolicyViolationError):
        env.refund.create_refund("ORD-5001", "CUST-005", 7600, "requested_by_wrong_customer")


def test_create_refund_succeeds_for_the_owning_customer() -> None:
    env = SupportToolEnvironment(CUSTOMER_ORDER_MISMATCH.initial_state)

    refund = env.refund.create_refund("ORD-5001", "CUST-006", 7600, "damaged_item")

    assert refund["order_id"] == "ORD-5001"


def test_cancel_order_succeeds_before_shipping() -> None:
    env = SupportToolEnvironment(ORDER_CANCELLATION_BEFORE_SHIPPING.initial_state)

    order = env.order.cancel_order("ORD-8001", "CUST-008")

    assert order["status"] == "cancelled"
    assert env.snapshot()["orders"]["ORD-8001"]["status"] == "cancelled"


def test_cancel_order_rejects_an_already_delivered_order() -> None:
    env = SupportToolEnvironment(ORDER_CANCELLATION_DENIED_AFTER_DELIVERY.initial_state)

    with pytest.raises(PolicyViolationError):
        env.order.cancel_order("ORD-9001", "CUST-009")


def test_cancel_order_rejects_a_cross_customer_request() -> None:
    env = SupportToolEnvironment(ORDER_CANCELLATION_BEFORE_SHIPPING.initial_state)

    with pytest.raises(PolicyViolationError):
        env.order.cancel_order("ORD-8001", "CUST-999")


def test_replace_item_succeeds_within_policy() -> None:
    env = SupportToolEnvironment(ITEM_REPLACEMENT_WITHIN_POLICY.initial_state)

    replacement = env.order.replace_item("ORD-10001", "CUST-010", "SHIRT-BLU-L", "wrong_size")

    assert replacement["sku"] == "SHIRT-BLU-L"
    assert env.snapshot()["replacements"]["ORD-10001"]["sku"] == "SHIRT-BLU-L"


def test_replace_item_rejects_a_duplicate_replacement() -> None:
    env = SupportToolEnvironment(ITEM_REPLACEMENT_WITHIN_POLICY.initial_state)
    env.order.replace_item("ORD-10001", "CUST-010", "SHIRT-BLU-L", "wrong_size")

    with pytest.raises(PolicyViolationError):
        env.order.replace_item("ORD-10001", "CUST-010", "SHIRT-BLU-L", "wrong_size")


def test_replace_item_rejects_a_sku_not_on_the_order() -> None:
    env = SupportToolEnvironment(ITEM_REPLACEMENT_WITHIN_POLICY.initial_state)

    with pytest.raises(NotFoundError):
        env.order.replace_item("ORD-10001", "CUST-010", "NOT-A-REAL-SKU", "wrong_size")


def test_escalate_ticket_succeeds_from_open() -> None:
    env = SupportToolEnvironment(TICKET_ESCALATION_FOR_UNRESOLVED_ISSUE.initial_state)

    ticket = env.ticket.escalate_ticket("TICK-9011", "Customer requested a supervisor.")

    assert ticket["status"] == "escalated"
    assert ticket["escalation_count"] == 1


def test_escalate_ticket_rejects_an_already_resolved_ticket() -> None:
    env = SupportToolEnvironment(TICKET_ESCALATION_FOR_UNRESOLVED_ISSUE.initial_state)
    env.ticket.update_ticket("TICK-9011", status="resolved")

    with pytest.raises(PolicyViolationError):
        env.ticket.escalate_ticket("TICK-9011", "Too late to escalate.")
