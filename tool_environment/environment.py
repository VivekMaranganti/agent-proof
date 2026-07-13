"""Facade that wires deterministic support-tool services for one task run."""

from __future__ import annotations

from tool_environment.services import (
    CustomerService,
    OrderService,
    PolicyService,
    RefundService,
    TicketService,
)
from tool_environment.state import SupportState


class SupportToolEnvironment:
    """In-memory deterministic tools seeded from a benchmark task state."""

    def __init__(self, initial_state: dict) -> None:
        self.state = SupportState.from_mapping(initial_state)
        self.customer = CustomerService(self.state)
        self.order = OrderService(self.state)
        self.policy = PolicyService(self.state)
        self.refund = RefundService(self.state, self.policy)
        self.ticket = TicketService(self.state)

    def snapshot(self) -> dict:
        return self.state.snapshot()
