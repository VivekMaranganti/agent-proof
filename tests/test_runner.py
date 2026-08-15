from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.schemas import AgentVersion, EventType
from benchmark.schema import BenchmarkTask, Difficulty
from runner.model_client import ModelReply, ScriptedModelClient, ToolCallRequest, TransientModelError
from runner.runner import run_task


def _version(**overrides) -> AgentVersion:
    defaults = dict(
        name="test-agent",
        git_sha="abc1234",
        model="test-model",
        system_prompt="You are a support agent.",
        tool_schema_hash="hash1234",
        config={},
        content_hash="contenthash1234",
        created_at=datetime.now(UTC),
    )
    defaults.update(overrides)
    return AgentVersion(**defaults)


def _task(**overrides) -> BenchmarkTask:
    defaults = dict(
        task_id="runner-smoke-001",
        input="Refund order o-1 for customer c-1.",
        initial_state={
            "customers": {"c-1": {"customer_id": "c-1", "name": "Test Customer"}},
            "orders": {
                "o-1": {
                    "order_id": "o-1",
                    "customer_id": "c-1",
                    "status": "delivered",
                    "total_cents": 500,
                    "delivered_days_ago": 1,
                    "items": [],
                }
            },
            "refunds": {},
            "tickets": {},
        },
        expected_actions=(),
        forbidden_actions=(),
        expected_final_state={},
        tags=(),
        difficulty=Difficulty.EASY,
    )
    defaults.update(overrides)
    return BenchmarkTask(**defaults)


async def test_successful_run_produces_a_complete_ordered_trace() -> None:
    model = ScriptedModelClient(
        [
            ModelReply(
                finish_reason="tool_calls",
                tool_calls=(ToolCallRequest("c1", "order", "get_order", {"order_id": "o-1"}),),
                input_tokens=10,
                output_tokens=5,
            ),
            ModelReply(
                finish_reason="tool_calls",
                tool_calls=(
                    ToolCallRequest(
                        "c2",
                        "refund",
                        "create_refund",
                        {
                            "order_id": "o-1",
                            "requesting_customer_id": "c-1",
                            "amount_cents": 500,
                            "reason": "damaged",
                        },
                    ),
                ),
                input_tokens=12,
                output_tokens=6,
            ),
            ModelReply(finish_reason="stop", content="Refund issued.", input_tokens=8, output_tokens=4),
        ]
    )

    result = await run_task(_version(), _task(), model, execution_id=uuid4())

    assert result.final_output == "Refund issued."
    assert result.max_steps_exceeded is False
    assert result.final_state["refunds"]["o-1"]["amount_cents"] == 500
    assert result.input_tokens == 30
    assert result.output_tokens == 15
    assert model.calls_made == 3
    assert [step.event_type for step in result.trace] == [
        EventType.MODEL_REQUEST,
        EventType.MODEL_RESPONSE,
        EventType.TOOL_CALL,
        EventType.TOOL_RESULT,
        EventType.MODEL_REQUEST,
        EventType.MODEL_RESPONSE,
        EventType.TOOL_CALL,
        EventType.TOOL_RESULT,
        EventType.MODEL_REQUEST,
        EventType.MODEL_RESPONSE,
        EventType.FINAL_ANSWER,
    ]


async def test_tool_error_is_captured_and_run_continues() -> None:
    model = ScriptedModelClient(
        [
            ModelReply(
                finish_reason="tool_calls",
                tool_calls=(ToolCallRequest("c1", "order", "get_order", {"order_id": "missing"}),),
            ),
            ModelReply(finish_reason="stop", content="Could not find that order."),
        ]
    )

    result = await run_task(_version(), _task(), model, execution_id=uuid4())

    assert result.final_output == "Could not find that order."
    error_steps = [step for step in result.trace if step.event_type == EventType.ERROR]
    assert len(error_steps) == 1
    assert error_steps[0].payload.error_type == "NotFoundError"


async def test_transient_model_error_is_retried() -> None:
    model = ScriptedModelClient(
        [
            TransientModelError("rate limited"),
            ModelReply(finish_reason="stop", content="ok"),
        ]
    )

    result = await run_task(_version(), _task(), model, execution_id=uuid4())

    assert result.final_output == "ok"
    assert model.calls_made == 2
    retry_steps = [step for step in result.trace if step.event_type == EventType.RETRY]
    assert len(retry_steps) == 1
    assert retry_steps[0].payload.attempt == 1
    assert retry_steps[0].payload.reason == "rate limited"


async def test_model_error_raises_after_exhausting_retries() -> None:
    model = ScriptedModelClient([TransientModelError("down")] * 3)

    with pytest.raises(TransientModelError):
        await run_task(_version(), _task(), model, execution_id=uuid4(), max_model_retries=2)

    assert model.calls_made == 3


async def test_max_steps_exceeded_is_recorded_without_crashing() -> None:
    reply = ModelReply(
        finish_reason="tool_calls",
        tool_calls=(ToolCallRequest("c1", "order", "get_order", {"order_id": "o-1"}),),
    )
    model = ScriptedModelClient([reply, reply])

    result = await run_task(_version(), _task(), model, execution_id=uuid4(), max_steps=2)

    assert result.max_steps_exceeded is True
    assert result.final_output is None
    assert result.trace.steps[-1].event_type == EventType.ERROR
    assert result.trace.steps[-1].payload.error_type == "MaxStepsExceeded"
