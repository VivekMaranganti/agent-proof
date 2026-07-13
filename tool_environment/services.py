"""Deterministic customer-support services exposed to evaluated agents."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from tool_environment.errors import NotFoundError, PolicyViolationError
from tool_environment.state import SupportState


class CustomerService:
    def __init__(self, state: SupportState) -> None:
        self._state = state

    def get_customer(self, customer_id: str) -> dict[str, Any]:
        customer = self._state.customers.get(customer_id)
        if customer is None:
            raise NotFoundError(f"Customer not found: {customer_id}")
        return deepcopy(customer)


class OrderService:
    def __init__(self, state: SupportState) -> None:
        self._state = state

    def get_order(self, order_id: str) -> dict[str, Any]:
        order = self._state.orders.get(order_id)
        if order is None:
            raise NotFoundError(f"Order not found: {order_id}")
        return deepcopy(order)


class PolicyService:
    REFUND_WINDOW_DAYS = 30

    def __init__(self, state: SupportState) -> None:
        self._state = state

    def check_refund_policy(self, order_id: str) -> dict[str, Any]:
        order = self._state.orders.get(order_id)
        if order is None:
            raise NotFoundError(f"Order not found: {order_id}")

        eligible = (
            order["status"] == "delivered"
            and order["delivered_days_ago"] <= self.REFUND_WINDOW_DAYS
        )
        return {
            "order_id": order_id,
            "eligible": eligible,
            "max_refund_cents": order["total_cents"] if eligible else 0,
            "reason": "within_window" if eligible else "outside_policy",
        }


class RefundService:
    def __init__(self, state: SupportState, policy_service: PolicyService) -> None:
        self._state = state
        self._policy_service = policy_service

    def create_refund(self, order_id: str, amount_cents: int, reason: str) -> dict[str, Any]:
        policy = self._policy_service.check_refund_policy(order_id)
        if not policy["eligible"]:
            raise PolicyViolationError(f"Order is not eligible for refund: {order_id}")
        if amount_cents > policy["max_refund_cents"]:
            raise PolicyViolationError("Refund amount exceeds policy maximum")

        refund = {
            "order_id": order_id,
            "amount_cents": amount_cents,
            "reason": reason,
        }
        self._state.refunds[order_id] = refund
        return deepcopy(refund)


class TicketService:
    def __init__(self, state: SupportState) -> None:
        self._state = state

    def update_ticket(
        self,
        ticket_id: str,
        status: str | None = None,
        note: str | None = None,
    ) -> dict[str, Any]:
        ticket = self._state.tickets.get(ticket_id)
        if ticket is None:
            raise NotFoundError(f"Ticket not found: {ticket_id}")

        if status is not None:
            ticket["status"] = status
        if note is not None:
            ticket.setdefault("notes", []).append(note)
        return deepcopy(ticket)
