"""Seeds a baseline/candidate run pair with a real regression and serves the platform API.

Runs three seeded support tasks through the actual runner for both a "baseline" and
a "candidate" agent version. The candidate is scripted to skip the refund step on one
task, producing a genuine regression the /api/v1/comparisons endpoint can attribute.
Uses the in-memory PlatformStore, so no Postgres/Docker is required — this is for
exercising the comparison API and the frontend against it locally, not a persistence
demo (see scripts/run_demo_task.py for that).

Usage:
    python scripts/run_demo_comparison.py
    # then, in frontend/: npm run dev
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import uvicorn

from app.execution_scoring import score_execution
from app.main import create_app
from app.schemas import AgentVersionCreate, EvaluationRunCreate, TaskExecutionCreate
from app.store import PlatformStore
from benchmark.schema import BenchmarkTask
from benchmark.tasks import (
    CUSTOMER_REFUND_OUTSIDE_POLICY,
    CUSTOMER_REFUND_WITHIN_POLICY,
    ORDER_CANCELLATION_DENIED_AFTER_DELIVERY,
)
from runner.model_client import ModelReply, ScriptedModelClient, ToolCallRequest
from runner.runner import run_task

TASKS: tuple[BenchmarkTask, ...] = (
    CUSTOMER_REFUND_WITHIN_POLICY,
    CUSTOMER_REFUND_OUTSIDE_POLICY,
    ORDER_CANCELLATION_DENIED_AFTER_DELIVERY,
)


def _correct_model_for(task: BenchmarkTask) -> ScriptedModelClient:
    if task is CUSTOMER_REFUND_WITHIN_POLICY:
        return ScriptedModelClient(
            [
                ModelReply(
                    finish_reason="tool_calls",
                    tool_calls=(ToolCallRequest("c1", "customer", "get_customer", {"customer_id": "CUST-001"}),),
                ),
                ModelReply(
                    finish_reason="tool_calls",
                    tool_calls=(ToolCallRequest("c2", "order", "get_order", {"order_id": "ORD-1001"}),),
                ),
                ModelReply(
                    finish_reason="tool_calls",
                    tool_calls=(ToolCallRequest("c3", "policy", "check_refund_policy", {"order_id": "ORD-1001"}),),
                ),
                ModelReply(
                    finish_reason="tool_calls",
                    tool_calls=(
                        ToolCallRequest(
                            "c4",
                            "refund",
                            "create_refund",
                            {
                                "order_id": "ORD-1001",
                                "requesting_customer_id": "CUST-001",
                                "amount_cents": 4200,
                                "reason": "damaged_item",
                            },
                        ),
                    ),
                ),
                ModelReply(
                    finish_reason="tool_calls",
                    tool_calls=(
                        ToolCallRequest(
                            "c5", "ticket", "update_ticket", {"ticket_id": "TICK-9001", "status": "resolved"}
                        ),
                    ),
                ),
                ModelReply(finish_reason="stop", content="Your refund has been issued."),
            ]
        )
    if task is CUSTOMER_REFUND_OUTSIDE_POLICY:
        return ScriptedModelClient(
            [
                ModelReply(
                    finish_reason="tool_calls",
                    tool_calls=(ToolCallRequest("c1", "customer", "get_customer", {"customer_id": "CUST-002"}),),
                ),
                ModelReply(
                    finish_reason="tool_calls",
                    tool_calls=(ToolCallRequest("c2", "order", "get_order", {"order_id": "ORD-2001"}),),
                ),
                ModelReply(
                    finish_reason="tool_calls",
                    tool_calls=(ToolCallRequest("c3", "policy", "check_refund_policy", {"order_id": "ORD-2001"}),),
                ),
                ModelReply(
                    finish_reason="tool_calls",
                    tool_calls=(
                        ToolCallRequest(
                            "c4", "ticket", "update_ticket", {"ticket_id": "TICK-9002", "status": "resolved"}
                        ),
                    ),
                ),
                ModelReply(finish_reason="stop", content="This order is outside our 30-day refund window."),
            ]
        )
    return ScriptedModelClient(
        [
            ModelReply(
                finish_reason="tool_calls",
                tool_calls=(ToolCallRequest("c1", "customer", "get_customer", {"customer_id": "CUST-009"}),),
            ),
            ModelReply(
                finish_reason="tool_calls",
                tool_calls=(ToolCallRequest("c2", "order", "get_order", {"order_id": "ORD-9001"}),),
            ),
            ModelReply(
                finish_reason="tool_calls",
                tool_calls=(
                    ToolCallRequest(
                        "c3", "ticket", "update_ticket", {"ticket_id": "TICK-9009", "status": "resolved"}
                    ),
                ),
            ),
            ModelReply(finish_reason="stop", content="This order has already been delivered and can't be cancelled."),
        ]
    )


def _regressed_model_for_refund_within_policy() -> ScriptedModelClient:
    # Skips the refund step entirely: the candidate resolves the ticket without
    # ever issuing the refund the task's contract requires.
    return ScriptedModelClient(
        [
            ModelReply(
                finish_reason="tool_calls",
                tool_calls=(ToolCallRequest("c1", "customer", "get_customer", {"customer_id": "CUST-001"}),),
            ),
            ModelReply(
                finish_reason="tool_calls",
                tool_calls=(
                    ToolCallRequest(
                        "c2", "ticket", "update_ticket", {"ticket_id": "TICK-9001", "status": "resolved"}
                    ),
                ),
            ),
            ModelReply(finish_reason="stop", content="Your ticket has been resolved."),
        ]
    )


async def _run_and_record(store: PlatformStore, run_id, version, task: BenchmarkTask, model: ScriptedModelClient) -> None:
    result = await run_task(version, task, model, execution_id=uuid4())
    execution_result, _ = score_execution(task, result)

    execution = await store.create_execution(run_id, TaskExecutionCreate(task_id=task.task_id, task_seed=0))
    for event in result.trace.to_storage():
        await store.append_trace_event(execution.id, event)
    await store.record_result(execution.id, execution_result)


async def seed(store: PlatformStore) -> tuple[str, str]:
    baseline_version = await store.create_agent_version(
        AgentVersionCreate(
            name="support-agent",
            git_sha="baseline0000000",
            model="demo-model",
            system_prompt="You are a customer support agent.",
            tool_schema_hash="demo-schema-hash",
            config={},
        )
    )
    candidate_version = await store.create_agent_version(
        AgentVersionCreate(
            name="support-agent",
            git_sha="candidate000000",
            model="demo-model",
            system_prompt="You are a customer support agent.",
            tool_schema_hash="demo-schema-hash",
            config={},
        )
    )

    baseline_run = await store.create_run(
        EvaluationRunCreate(
            agent_version_id=baseline_version.id,
            suite_id="customer-support-v1",
            suite_version="1",
            suite_manifest_hash="demo-manifest-hash",
            seed=1,
        )
    )
    candidate_run = await store.create_run(
        EvaluationRunCreate(
            agent_version_id=candidate_version.id,
            suite_id="customer-support-v1",
            suite_version="1",
            suite_manifest_hash="demo-manifest-hash",
            seed=1,
        )
    )

    for task in TASKS:
        await _run_and_record(store, baseline_run.id, baseline_version, task, _correct_model_for(task))
        candidate_model = (
            _regressed_model_for_refund_within_policy()
            if task is CUSTOMER_REFUND_WITHIN_POLICY
            else _correct_model_for(task)
        )
        await _run_and_record(store, candidate_run.id, candidate_version, task, candidate_model)

    return str(baseline_run.id), str(candidate_run.id)


def main() -> None:
    store = PlatformStore()
    app = create_app(store=store)

    baseline_run_id, candidate_run_id = asyncio.run(seed(store))

    print(f"Baseline run:   {baseline_run_id}")
    print(f"Candidate run:  {candidate_run_id}")
    print(f"Comparison API: http://127.0.0.1:8000/api/v1/comparisons/{baseline_run_id}/{candidate_run_id}")
    print("Point the frontend dev server's inputs at the two run IDs above.")

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")


if __name__ == "__main__":
    main()
