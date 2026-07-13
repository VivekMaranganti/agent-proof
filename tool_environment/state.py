"""State container for deterministic support-tool services."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any


@dataclass
class SupportState:
    """Mutable synthetic state shared by support services during one task run."""

    customers: dict[str, dict[str, Any]]
    orders: dict[str, dict[str, Any]]
    refunds: dict[str, dict[str, Any]]
    tickets: dict[str, dict[str, Any]]

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "SupportState":
        return cls(
            customers=deepcopy(data.get("customers", {})),
            orders=deepcopy(data.get("orders", {})),
            refunds=deepcopy(data.get("refunds", {})),
            tickets=deepcopy(data.get("tickets", {})),
        )

    def snapshot(self) -> dict[str, Any]:
        return {
            "customers": deepcopy(self.customers),
            "orders": deepcopy(self.orders),
            "refunds": deepcopy(self.refunds),
            "tickets": deepcopy(self.tickets),
        }
