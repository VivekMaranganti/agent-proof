"""PostgresStore tests. Requires a reachable database (see docker-compose.yml).

Skips cleanly when postgres isn't up, so plain `pytest` stays green without docker.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from app.comparison import compare_runs
from app.db import database_url, session_factory
from app.postgres_store import PostgresStore
from app.schemas import (
    AgentVersionCreate,
    EvaluationRunCreate,
    EventType,
    TaskExecutionCreate,
    TaskExecutionResult,
    TraceEventCreate,
)


def _postgres_reachable() -> bool:
    from sqlalchemy.ext.asyncio import create_async_engine

    async def probe() -> bool:
        engine = create_async_engine(database_url())
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
        finally:
            await engine.dispose()

    return asyncio.run(probe())


pytestmark = pytest.mark.skipif(
    not _postgres_reachable(), reason="postgres is not reachable, run: docker compose up -d postgres"
)


@pytest.fixture(autouse=True)
async def _clean_tables():
    yield
    async with session_factory() as session:
        await session.execute(
            text("TRUNCATE trace_events, task_executions, evaluation_runs, agent_versions RESTART IDENTITY CASCADE")
        )
        await session.commit()


@pytest.fixture
def store() -> PostgresStore:
    return PostgresStore()


async def _agent_version(store: PostgresStore, sha: str = "1111111"):
    return await store.create_agent_version(
        AgentVersionCreate(
            name=f"support-agent-{sha}",
            git_sha=sha,
            model="test-model",
            system_prompt="Follow the policy.",
            tool_schema_hash="a1b2c3d4",
        )
    )


async def _run(store: PostgresStore, agent_version_id):
    return await store.create_run(
        EvaluationRunCreate(
            agent_version_id=agent_version_id,
            suite_id="support-ops",
            suite_version="v1",
            suite_manifest_hash="manifest123",
            seed=7,
        )
    )


async def test_create_and_fetch_agent_version(store: PostgresStore) -> None:
    version = await _agent_version(store)
    assert version.name == "support-agent-1111111"
    assert version.created_at is not None


async def test_create_run_requires_existing_agent_version(store: PostgresStore) -> None:
    with pytest.raises(HTTPException) as error:
        await _run(store, agent_version_id="00000000-0000-0000-0000-000000000000")
    assert error.value.status_code == 404


async def test_create_execution_requires_existing_run(store: PostgresStore) -> None:
    with pytest.raises(HTTPException) as error:
        await store.create_execution(
            run_id="00000000-0000-0000-0000-000000000000",
            payload=TaskExecutionCreate(task_id="refund-001", task_seed=7),
        )
    assert error.value.status_code == 404


async def test_record_result_rejects_double_finalization(store: PostgresStore) -> None:
    version = await _agent_version(store)
    run = await _run(store, version.id)
    execution = await store.create_execution(run.id, TaskExecutionCreate(task_id="refund-001", task_seed=7))
    result = TaskExecutionResult(
        status="passed",
        passed=True,
        final_output="resolved",
        latency_ms=100,
        input_tokens=30,
        output_tokens=12,
        estimated_cost_usd=0.001,
    )
    await store.record_result(execution.id, result)
    with pytest.raises(HTTPException) as error:
        await store.record_result(execution.id, result)
    assert error.value.status_code == 409


async def test_append_trace_event_rejects_duplicate_sequence(store: PostgresStore) -> None:
    version = await _agent_version(store)
    run = await _run(store, version.id)
    execution = await store.create_execution(run.id, TaskExecutionCreate(task_id="refund-001", task_seed=7))
    await store.append_trace_event(
        execution.id, TraceEventCreate(sequence_no=0, event_type=EventType.TOOL_CALL, payload={})
    )
    with pytest.raises(HTTPException) as error:
        await store.append_trace_event(
            execution.id, TraceEventCreate(sequence_no=0, event_type=EventType.TOOL_RESULT, payload={})
        )
    assert error.value.status_code == 409


async def test_trace_events_are_returned_in_sequence_order(store: PostgresStore) -> None:
    version = await _agent_version(store)
    run = await _run(store, version.id)
    execution = await store.create_execution(run.id, TaskExecutionCreate(task_id="refund-001", task_seed=7))
    for sequence_no in (2, 0, 1):
        await store.append_trace_event(
            execution.id, TraceEventCreate(sequence_no=sequence_no, event_type=EventType.TOOL_CALL, payload={})
        )
    trace = await store.get_trace(execution.id)
    assert [event.sequence_no for event in trace] == [0, 1, 2]


async def test_comparison_attributes_a_wrong_tool_regression(store: PostgresStore) -> None:
    baseline_version = await _agent_version(store, sha="1111111")
    candidate_version = await _agent_version(store, sha="2222222")
    baseline_run = await _run(store, baseline_version.id)
    candidate_run = await _run(store, candidate_version.id)
    baseline_execution = await store.create_execution(baseline_run.id, TaskExecutionCreate(task_id="refund-001", task_seed=7))
    candidate_execution = await store.create_execution(candidate_run.id, TaskExecutionCreate(task_id="refund-001", task_seed=7))
    await store.append_trace_event(
        baseline_execution.id,
        TraceEventCreate(sequence_no=0, event_type=EventType.TOOL_CALL, payload={"tool_name": "lookup_order", "arguments": {"order_id": "o-1"}}),
    )
    await store.append_trace_event(
        candidate_execution.id,
        TraceEventCreate(sequence_no=0, event_type=EventType.TOOL_CALL, payload={"tool_name": "issue_refund", "arguments": {"order_id": "o-1"}}),
    )
    await store.record_result(
        baseline_execution.id,
        TaskExecutionResult(status="passed", passed=True, final_output="resolved", latency_ms=100, input_tokens=30, output_tokens=12, estimated_cost_usd=0.001),
    )
    await store.record_result(
        candidate_execution.id,
        TaskExecutionResult(status="failed", passed=False, final_output="wrong resolution", latency_ms=100, input_tokens=30, output_tokens=12, estimated_cost_usd=0.001),
    )

    comparison = await compare_runs(store, baseline_run.id, candidate_run.id)

    assert comparison.regressions == 1
    result = comparison.results[0]
    assert result.disposition == "regression"
    assert result.attribution.divergence_type == "wrong_tool"
