from benchmark.tasks import CUSTOMER_REFUND_WITHIN_POLICY
from tool_environment import SupportToolEnvironment


def test_customer_refund_flow_updates_state() -> None:
    env = SupportToolEnvironment(CUSTOMER_REFUND_WITHIN_POLICY.initial_state)

    customer = env.customer.get_customer("CUST-001")
    order = env.order.get_order("ORD-1001")
    policy = env.policy.check_refund_policy("ORD-1001")
    refund = env.refund.create_refund("ORD-1001", 4200, "damaged_item")
    ticket = env.ticket.update_ticket("TICK-9001", status="resolved", note="Refund issued.")

    assert customer["name"] == "Avery Chen"
    assert order["total_cents"] == 4200
    assert policy["eligible"] is True
    assert refund["amount_cents"] == 4200
    assert ticket["status"] == "resolved"
    assert env.snapshot()["refunds"]["ORD-1001"]["reason"] == "damaged_item"
