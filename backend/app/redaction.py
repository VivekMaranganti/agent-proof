"""Redacts known-sensitive fields from trace event payloads before persistence.

Key-name-based, not content-detection: any dict key matching a known-sensitive name
(case-insensitive, at any nesting depth) has its value replaced. This is deliberately
the conservative, cheap option - matching by key name catches the fields a tool
environment would plausibly return (a customer's name/email, say) without needing
PII-detection ML, at the cost of not catching a genuinely sensitive value stored
under an innocuous key. That's a real limitation, not a silently assumed-complete one.

Applied at the store layer (Store.append_trace_event), not in the runner. Scoring and
attribution run on the in-memory Trace before any of this happens, so they still see
real values - only what actually lands in Postgres (and anything read back from it:
comparisons, the trace replay API) is affected. That has a real cost: if a redacted
field is exactly where a baseline and candidate run differ, that difference is no
longer visible to comparison.py's divergence detection. Redacting it anyway is still
the right tradeoff - the alternative is persisting raw PII - but it's worth knowing
this isn't free.
"""

from __future__ import annotations

from typing import Any

REDACTED = "[REDACTED]"

SENSITIVE_KEYS = frozenset(
    {
        "name",
        "email",
        "phone",
        "phone_number",
        "address",
        "ssn",
        "credit_card",
        "card_number",
    }
)


def redact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Returns a copy of payload with sensitive field values replaced."""

    return _redact_value(payload)


def _redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: REDACTED if key.lower() in SENSITIVE_KEYS else _redact_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    return value
