"""Runs one agent version against one seeded support task end to end.

The milestone this script exists for: agent version -> runner -> ordered trace ->
deterministic score -> persisted through the platform API -> read back over that
same API. Everything below runs on a single event loop (an in-process ASGI client
talking to the real app, not a live server) since PostgresStore's engine is a
module-level singleton that can't be reused across separate asyncio.run() calls.

Usage:
    docker compose up -d postgres
    alembic upgrade head
    python scripts/run_demo_task.py
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import httpx

from app.execution_scoring import score_execution
from app.main import create_app
from app.postgres_store import PostgresStore
from app.schemas import AgentVersion
from benchmark.tasks import CUSTOMER_REFUND_WITHIN_POLICY
from runner.model_client import ModelReply, ScriptedModelClient, ToolCallRequest
from runner.runner import run_task

TASK = CUSTOMER_REFUND_WITHIN_POLICY

# stands in for a live model backend until one is wired up behind runner.model_client.ModelClient;
# this exact sequence is what a correct agent does for TASK's expected_actions
MODEL_SCRIPT = [
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
        tool_calls=(ToolCallRequest("c5", "ticket", "update_ticket", {"ticket_id": "TICK-9001", "status": "resolved"}),),
    ),
    ModelReply(finish_reason="stop", content="Refund issued for order ORD-1001."),
]


async def main() -> None:
    app = create_app(PostgresStore())
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://demo") as client:
        version_response = await client.post(
            "/api/v1/agent-versions",
            json={
                "name": "demo-refund-agent",
                "git_sha": "0000000",
                "model": "scripted-demo-v1",
                "system_prompt": "You are a support agent. Follow policy exactly.",
                "tool_schema_hash": "demo0001",
            },
        )
        version_response.raise_for_status()
        version = AgentVersion.model_validate(version_response.json())

        run_response = await client.post(
            "/api/v1/evaluation-runs",
            json={
                "agent_version_id": str(version.id),
                "suite_id": "support-ops",
                "suite_version": "v1",
                "suite_manifest_hash": "demo-manifest",
                "seed": 7,
            },
        )
        run_response.raise_for_status()
        run_id = run_response.json()["id"]

        execution_response = await client.post(
            f"/api/v1/evaluation-runs/{run_id}/executions",
            json={"task_id": TASK.task_id, "task_seed": 7},
        )
        execution_response.raise_for_status()
        execution_id = execution_response.json()["id"]

        result = await run_task(version, TASK, ScriptedModelClient(MODEL_SCRIPT), execution_id=UUID(execution_id))

        for event in result.trace.to_storage():
            trace_response = await client.post(
                f"/api/v1/executions/{execution_id}/trace-events", json=event.model_dump(mode="json")
            )
            trace_response.raise_for_status()

        execution_result, contract_score = score_execution(TASK, result)
        result_response = await client.post(
            f"/api/v1/executions/{execution_id}/result", json=execution_result.model_dump(mode="json")
        )
        result_response.raise_for_status()

        fetched_execution = (await client.get(f"/api/v1/executions/{execution_id}")).json()
        fetched_trace = (await client.get(f"/api/v1/executions/{execution_id}/trace")).json()

    print(f"task:          {TASK.task_id}")
    print(f"run_id:        {run_id}")
    print(f"execution_id:  {execution_id}")
    print(f"status:        {fetched_execution['status']} (passed={fetched_execution['passed']})")
    print(f"final_output:  {fetched_execution['final_output']}")
    print(f"trace steps:   {len(fetched_trace)} (persisted and read back via the API)")
    print(
        "contract score: missing=%s forbidden=%s final_state_mismatches=%s"
        % (
            contract_score.missing_expected_actions,
            contract_score.forbidden_actions_seen,
            contract_score.final_state_mismatches,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
