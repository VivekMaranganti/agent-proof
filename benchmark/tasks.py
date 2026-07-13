"""Seed benchmark tasks for the customer-support operations suite."""

from __future__ import annotations

from benchmark.schema import BenchmarkTask, Difficulty, ExpectedAction, ForbiddenAction


CUSTOMER_REFUND_WITHIN_POLICY = BenchmarkTask(
    task_id="support_refund_within_30_days_001",
    input=(
        "Customer CUST-001 says order ORD-1001 arrived damaged and asks for a refund. "
        "Resolve according to policy and update the ticket."
    ),
    initial_state={
        "customers": {
            "CUST-001": {
                "customer_id": "CUST-001",
                "name": "Avery Chen",
                "email": "avery@example.test",
            }
        },
        "orders": {
            "ORD-1001": {
                "order_id": "ORD-1001",
                "customer_id": "CUST-001",
                "status": "delivered",
                "total_cents": 4200,
                "delivered_days_ago": 12,
                "items": [{"sku": "MUG-RED", "quantity": 1}],
            }
        },
        "refunds": {},
        "tickets": {
            "TICK-9001": {
                "ticket_id": "TICK-9001",
                "customer_id": "CUST-001",
                "status": "open",
                "notes": [],
            }
        },
    },
    expected_actions=(
        ExpectedAction("customer", "get_customer", {"customer_id": "CUST-001"}),
        ExpectedAction("order", "get_order", {"order_id": "ORD-1001"}),
        ExpectedAction("policy", "check_refund_policy", {"order_id": "ORD-1001"}),
        ExpectedAction("refund", "create_refund", {"order_id": "ORD-1001", "amount_cents": 4200}),
        ExpectedAction("ticket", "update_ticket", {"ticket_id": "TICK-9001", "status": "resolved"}),
    ),
    forbidden_actions=(
        ForbiddenAction(
            "refund",
            "create_refund",
            "Refund amount must not exceed the order total.",
            {"order_id": "ORD-1001", "amount_cents": 4201},
        ),
    ),
    expected_final_state={
        "refunds": {
            "ORD-1001": {
                "order_id": "ORD-1001",
                "amount_cents": 4200,
                "reason": "damaged_item",
            }
        },
        "tickets": {
            "TICK-9001": {
                "status": "resolved",
            }
        },
    },
    tags=("refund", "damaged_item", "within_policy"),
    difficulty=Difficulty.EASY,
)


SEED_TASKS: tuple[BenchmarkTask, ...] = (CUSTOMER_REFUND_WITHIN_POLICY,)
