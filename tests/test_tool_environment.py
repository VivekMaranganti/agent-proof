import pytest

from benchmark.tasks import (
    CUSTOMER_ORDER_MISMATCH,
    CUSTOMER_REFUND_WITHIN_POLICY,
    DUPLICATE_REFUND_PREVENTION,
)
from tool_environment import SupportToolEnvironment
from tool_environment.errors import PolicyViolationError


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
