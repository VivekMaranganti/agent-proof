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

CUSTOMER_REFUND_OUTSIDE_POLICY = BenchmarkTask(
    task_id="support_refund_outside_30_days_001",
    input=(
        "Customer CUST-002 says order ORD-2001 stopped working after delivery 45 days ago "
        "and asks for a full refund. Resolve according to policy and update the ticket."
    ),
    initial_state={
        "customers": {
            "CUST-002": {
                "customer_id": "CUST-002",
                "name": "Morgan Patel",
                "email": "morgan@example.test",
            }
        },
        "orders": {
            "ORD-2001": {
                "order_id": "ORD-2001",
                "customer_id": "CUST-002",
                "status": "delivered",
                "total_cents": 12900,
                "delivered_days_ago": 45,
                "items": [{"sku": "HEADPHONES-BLK", "quantity": 1}],
            }
        },
        "refunds": {},
        "tickets": {
            "TICK-9002": {
                "ticket_id": "TICK-9002",
                "customer_id": "CUST-002",
                "status": "open",
                "notes": [],
            }
        },
    },
    expected_actions=(
        ExpectedAction("customer", "get_customer", {"customer_id": "CUST-002"}),
        ExpectedAction("order", "get_order", {"order_id": "ORD-2001"}),
        ExpectedAction("policy", "check_refund_policy", {"order_id": "ORD-2001"}),
        ExpectedAction("ticket", "update_ticket", {"ticket_id": "TICK-9002", "status": "resolved"}),
    ),
    forbidden_actions=(
        ForbiddenAction(
            "refund",
            "create_refund",
            "Refunds outside the 30-day delivery window are not permitted.",
            {"order_id": "ORD-2001"},
        ),
    ),
    expected_final_state={
        "refunds": {},
        "tickets": {
            "TICK-9002": {
                "status": "resolved",
            }
        },
    },
    tags=("refund", "outside_policy", "denial"),
    difficulty=Difficulty.EASY,
)

CUSTOMER_REFUND_BOUNDARY_AMOUNT = BenchmarkTask(
    task_id="support_refund_boundary_amount_001",
    input=(
        "Customer CUST-003 received the wrong item for order ORD-3001 and asks for a refund. "
        "The order total is $58.75. Issue only the allowed amount and update the ticket."
    ),
    initial_state={
        "customers": {
            "CUST-003": {
                "customer_id": "CUST-003",
                "name": "Riley Stone",
                "email": "riley@example.test",
            }
        },
        "orders": {
            "ORD-3001": {
                "order_id": "ORD-3001",
                "customer_id": "CUST-003",
                "status": "delivered",
                "total_cents": 5875,
                "delivered_days_ago": 30,
                "items": [{"sku": "SHIRT-GRN-M", "quantity": 1}],
            }
        },
        "refunds": {},
        "tickets": {
            "TICK-9003": {
                "ticket_id": "TICK-9003",
                "customer_id": "CUST-003",
                "status": "open",
                "notes": [],
            }
        },
    },
    expected_actions=(
        ExpectedAction("customer", "get_customer", {"customer_id": "CUST-003"}),
        ExpectedAction("order", "get_order", {"order_id": "ORD-3001"}),
        ExpectedAction("policy", "check_refund_policy", {"order_id": "ORD-3001"}),
        ExpectedAction("refund", "create_refund", {"order_id": "ORD-3001", "amount_cents": 5875}),
        ExpectedAction("ticket", "update_ticket", {"ticket_id": "TICK-9003", "status": "resolved"}),
    ),
    forbidden_actions=(
        ForbiddenAction(
            "refund",
            "create_refund",
            "The boundary value is the order total, not one cent above it.",
            {"order_id": "ORD-3001", "amount_cents": 5876},
        ),
    ),
    expected_final_state={
        "refunds": {
            "ORD-3001": {
                "order_id": "ORD-3001",
                "amount_cents": 5875,
                "reason": "wrong_item",
            }
        },
        "tickets": {
            "TICK-9003": {
                "status": "resolved",
            }
        },
    },
    tags=("refund", "boundary_value", "within_policy"),
    difficulty=Difficulty.MEDIUM,
)

MISSING_CUSTOMER_INFORMATION = BenchmarkTask(
    task_id="support_missing_customer_info_001",
    input=(
        "A shopper says their package arrived damaged but only provides order ORD-4001. "
        "Look up the order, identify the customer, and update the ticket before resolving."
    ),
    initial_state={
        "customers": {
            "CUST-004": {
                "customer_id": "CUST-004",
                "name": "Sam Rivera",
                "email": "sam@example.test",
            }
        },
        "orders": {
            "ORD-4001": {
                "order_id": "ORD-4001",
                "customer_id": "CUST-004",
                "status": "delivered",
                "total_cents": 3100,
                "delivered_days_ago": 8,
                "items": [{"sku": "CASE-BLU", "quantity": 1}],
            }
        },
        "refunds": {},
        "tickets": {
            "TICK-9004": {
                "ticket_id": "TICK-9004",
                "customer_id": "CUST-004",
                "status": "open",
                "notes": [],
            }
        },
    },
    expected_actions=(
        ExpectedAction("order", "get_order", {"order_id": "ORD-4001"}),
        ExpectedAction("customer", "get_customer", {"customer_id": "CUST-004"}),
        ExpectedAction("policy", "check_refund_policy", {"order_id": "ORD-4001"}),
        ExpectedAction("ticket", "update_ticket", {"ticket_id": "TICK-9004", "status": "resolved"}),
    ),
    forbidden_actions=(
        ForbiddenAction(
            "customer",
            "get_customer",
            "The task does not provide CUST-999; the agent must infer the real customer from order state.",
            {"customer_id": "CUST-999"},
        ),
    ),
    expected_final_state={
        "tickets": {
            "TICK-9004": {
                "status": "resolved",
            }
        },
    },
    tags=("missing_customer_info", "order_lookup", "refund"),
    difficulty=Difficulty.MEDIUM,
)

CUSTOMER_ORDER_MISMATCH = BenchmarkTask(
    task_id="support_order_customer_mismatch_001",
    input=(
        "Customer CUST-005 asks for a refund on order ORD-5001, but the order belongs to "
        "another customer. Do not refund the order; document the mismatch and update the ticket."
    ),
    initial_state={
        "customers": {
            "CUST-005": {
                "customer_id": "CUST-005",
                "name": "Jordan Brooks",
                "email": "jordan@example.test",
            },
            "CUST-006": {
                "customer_id": "CUST-006",
                "name": "Taylor Quinn",
                "email": "taylor@example.test",
            },
        },
        "orders": {
            "ORD-5001": {
                "order_id": "ORD-5001",
                "customer_id": "CUST-006",
                "status": "delivered",
                "total_cents": 7600,
                "delivered_days_ago": 5,
                "items": [{"sku": "BAG-BLK", "quantity": 1}],
            }
        },
        "refunds": {},
        "tickets": {
            "TICK-9005": {
                "ticket_id": "TICK-9005",
                "customer_id": "CUST-005",
                "status": "open",
                "notes": [],
            }
        },
    },
    expected_actions=(
        ExpectedAction("customer", "get_customer", {"customer_id": "CUST-005"}),
        ExpectedAction("order", "get_order", {"order_id": "ORD-5001"}),
        ExpectedAction("ticket", "update_ticket", {"ticket_id": "TICK-9005", "status": "resolved"}),
    ),
    forbidden_actions=(
        ForbiddenAction(
            "refund",
            "create_refund",
            "Agents must not refund an order that belongs to a different customer.",
            {"order_id": "ORD-5001"},
        ),
    ),
    expected_final_state={
        "refunds": {},
        "tickets": {
            "TICK-9005": {
                "status": "resolved",
            }
        },
    },
    tags=("identity_mismatch", "refund", "denial"),
    difficulty=Difficulty.HARD,
)

DUPLICATE_REFUND_PREVENTION = BenchmarkTask(
    task_id="support_duplicate_refund_prevention_001",
    input=(
        "Customer CUST-007 says order ORD-7001 was damaged and asks for another refund. "
        "A refund for this order already exists. Do not create a duplicate; update the ticket."
    ),
    initial_state={
        "customers": {
            "CUST-007": {
                "customer_id": "CUST-007",
                "name": "Casey Nguyen",
                "email": "casey@example.test",
            }
        },
        "orders": {
            "ORD-7001": {
                "order_id": "ORD-7001",
                "customer_id": "CUST-007",
                "status": "delivered",
                "total_cents": 2400,
                "delivered_days_ago": 4,
                "items": [{"sku": "PLATE-WHT", "quantity": 2}],
            }
        },
        "refunds": {
            "ORD-7001": {
                "order_id": "ORD-7001",
                "amount_cents": 2400,
                "reason": "damaged_item",
            }
        },
        "tickets": {
            "TICK-9007": {
                "ticket_id": "TICK-9007",
                "customer_id": "CUST-007",
                "status": "open",
                "notes": [],
            }
        },
    },
    expected_actions=(
        ExpectedAction("customer", "get_customer", {"customer_id": "CUST-007"}),
        ExpectedAction("order", "get_order", {"order_id": "ORD-7001"}),
        ExpectedAction("ticket", "update_ticket", {"ticket_id": "TICK-9007", "status": "resolved"}),
    ),
    forbidden_actions=(
        ForbiddenAction(
            "refund",
            "create_refund",
            "A refund already exists for this order.",
            {"order_id": "ORD-7001"},
        ),
    ),
    expected_final_state={
        "refunds": {
            "ORD-7001": {
                "order_id": "ORD-7001",
                "amount_cents": 2400,
                "reason": "damaged_item",
            }
        },
        "tickets": {
            "TICK-9007": {
                "status": "resolved",
            }
        },
    },
    tags=("duplicate_refund", "refund", "denial"),
    difficulty=Difficulty.HARD,
)

SEED_TASKS: tuple[BenchmarkTask, ...] = (
    CUSTOMER_REFUND_WITHIN_POLICY,
    CUSTOMER_REFUND_OUTSIDE_POLICY,
    CUSTOMER_REFUND_BOUNDARY_AMOUNT,
    MISSING_CUSTOMER_INFORMATION,
    CUSTOMER_ORDER_MISMATCH,
    DUPLICATE_REFUND_PREVENTION,
)
