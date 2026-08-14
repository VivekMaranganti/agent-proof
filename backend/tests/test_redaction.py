from __future__ import annotations

from app.redaction import REDACTED, redact_payload


def test_redacts_a_top_level_sensitive_key() -> None:
    result = redact_payload({"name": "Avery Chen", "order_id": "ORD-1001"})

    assert result == {"name": REDACTED, "order_id": "ORD-1001"}


def test_redacts_sensitive_keys_at_any_nesting_depth() -> None:
    payload = {
        "call_id": "c-1",
        "result": {
            "customer_id": "CUST-001",
            "name": "Avery Chen",
            "email": "avery@example.test",
            "address": {"street": "1 Main St", "city": "Springfield"},
        },
    }

    result = redact_payload(payload)

    assert result["call_id"] == "c-1"
    assert result["result"]["customer_id"] == "CUST-001"
    assert result["result"]["name"] == REDACTED
    assert result["result"]["email"] == REDACTED
    assert result["result"]["address"] == REDACTED


def test_redacts_sensitive_keys_inside_lists() -> None:
    payload = {"items": [{"sku": "MUG-RED", "name": "Red Mug"}]}

    result = redact_payload(payload)

    assert result == {"items": [{"sku": "MUG-RED", "name": REDACTED}]}


def test_is_case_insensitive() -> None:
    result = redact_payload({"Email": "avery@example.test", "EMAIL": "x@example.test"})

    assert result == {"Email": REDACTED, "EMAIL": REDACTED}


def test_leaves_non_sensitive_payloads_untouched() -> None:
    payload = {"service": "order", "operation": "get_order", "arguments": {"order_id": "ORD-1001"}}

    assert redact_payload(payload) == payload


def test_does_not_mutate_the_original_payload() -> None:
    payload = {"name": "Avery Chen"}

    redact_payload(payload)

    assert payload == {"name": "Avery Chen"}
