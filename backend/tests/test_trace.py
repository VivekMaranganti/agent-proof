from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.schemas import EventType, TraceEvent
from app.trace import (
    ErrorPayload,
    FinalAnswerPayload,
    ModelRequestPayload,
    ModelResponsePayload,
    RetryPayload,
    ToolCallPayload,
    ToolResultPayload,
    Trace,
)


def _one_of_each(trace: Trace) -> None:
    request_step = trace.append(
        ModelRequestPayload(messages=[{"role": "user", "content": "refund order o-1"}], model="gpt-test")
    )
    trace.append(
        ModelResponsePayload(
            tool_calls=[{"id": "c-1", "name": "issue_refund"}],
            finish_reason="tool_calls",
            input_tokens=42,
            output_tokens=7,
        ),
        parent_step_id=request_step.id,
    )
    call_step = trace.append(ToolCallPayload(call_id="c-1", tool_name="issue_refund", arguments={"order_id": "o-1"}))
    trace.append(
        ToolResultPayload(call_id="c-1", result={"refunded": True}),
        parent_step_id=call_step.id,
        duration_ms=120,
    )
    trace.append(RetryPayload(attempt=1, reason="transient tool timeout"))
    trace.append(ErrorPayload(error_type="ToolError", message="order not found"))
    trace.append(FinalAnswerPayload(content="Refund issued for order o-1."))


def test_append_assigns_sequential_sequence_numbers() -> None:
    trace = Trace(execution_id=uuid4())
    _one_of_each(trace)
    assert [step.sequence_no for step in trace.steps] == list(range(len(trace)))
    assert len(trace) == 7


def test_event_type_matches_payload() -> None:
    trace = Trace(execution_id=uuid4())
    step = trace.append(FinalAnswerPayload(content="done"))
    assert step.event_type == EventType.FINAL_ANSWER


def test_append_rejects_unknown_parent_step() -> None:
    trace = Trace(execution_id=uuid4())
    with pytest.raises(ValueError, match="not a step in this trace"):
        trace.append(FinalAnswerPayload(content="done"), parent_step_id=uuid4())


def _round_trip(trace: Trace) -> Trace:
    execution_id = trace.execution_id
    storage_rows = trace.to_storage()
    events = [
        TraceEvent(**row.model_dump(), execution_id=execution_id, created_at=datetime.now(UTC))
        for row in storage_rows
    ]
    return Trace.from_storage(execution_id, events)


def test_round_trip_reconstructs_identically() -> None:
    execution_id = uuid4()
    trace = Trace(execution_id=execution_id)
    _one_of_each(trace)

    rebuilt = _round_trip(trace)

    assert len(rebuilt) == len(trace)
    for original, restored in zip(trace.steps, rebuilt.steps):
        assert original.id == restored.id
        assert original.sequence_no == restored.sequence_no
        assert original.parent_step_id == restored.parent_step_id
        assert original.duration_ms == restored.duration_ms
        assert original.payload == restored.payload


def test_from_storage_rejects_sequence_gap() -> None:
    execution_id = uuid4()
    trace = Trace(execution_id=execution_id)
    trace.append(FinalAnswerPayload(content="done"))
    events = [
        TraceEvent(**row.model_dump(), execution_id=execution_id, created_at=datetime.now(UTC))
        for row in trace.to_storage()
    ]
    events[0].sequence_no = 5

    with pytest.raises(ValueError, match="sequence gap"):
        Trace.from_storage(execution_id, events)


def test_from_storage_rejects_dangling_parent_reference() -> None:
    execution_id = uuid4()
    trace = Trace(execution_id=execution_id)
    trace.append(FinalAnswerPayload(content="done"))
    events = [
        TraceEvent(**row.model_dump(), execution_id=execution_id, created_at=datetime.now(UTC))
        for row in trace.to_storage()
    ]
    events[0].parent_event_id = uuid4()

    with pytest.raises(ValueError, match="not a prior step"):
        Trace.from_storage(execution_id, events)
