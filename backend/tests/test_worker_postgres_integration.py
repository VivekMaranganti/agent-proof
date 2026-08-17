"""Proves the #9 acceptance criterion literally: a suite of tasks enqueued is executed
by workers and lands in Postgres. Requires both redis and postgres; skips cleanly if
either isn't reachable.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text

from app.db import database_url, session_factory
from app.postgres_store import PostgresStore
from app.queue import DEAD_LETTER_STREAM, EvaluationJob, Queue, STREAM, create_redis_client
from app.schemas import AgentVersionCreate, EvaluationRunCreate, TaskExecutionCreate
from benchmark.tasks import SEED_TASKS
from runner.worker import run_worker_loop, task_registry_from


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


def _redis_reachable() -> bool:
    async def probe() -> bool:
        redis = create_redis_client()
        try:
            await redis.ping()
            return True
        except Exception:
            return False
        finally:
            await redis.aclose()

    return asyncio.run(probe())


pytestmark = pytest.mark.skipif(
    not (_postgres_reachable() and _redis_reachable()),
    reason="requires both postgres and redis, run: docker compose up -d postgres redis",
)

TASK_REGISTRY = task_registry_from(list(SEED_TASKS))


@pytest.fixture(autouse=True)
async def _clean_state():
    yield
    async with session_factory() as session:
        await session.execute(
            text("TRUNCATE judge_verdicts, trace_events, task_executions, evaluation_runs, agent_versions RESTART IDENTITY CASCADE")
        )
        await session.commit()
    redis = create_redis_client()
    await redis.delete(STREAM, DEAD_LETTER_STREAM)
    await redis.aclose()


async def test_enqueued_suite_is_executed_and_lands_in_postgres() -> None:
    store = PostgresStore()
    redis = create_redis_client()
    queue = Queue(redis)
    await queue.ensure_group()

    version = await store.create_agent_version(
        AgentVersionCreate(
            name="oracle-agent",
            git_sha="abc1234",
            model="reference-agent",
            system_prompt="follow policy",
            tool_schema_hash="hash1234",
        )
    )
    run = await store.create_run(
        EvaluationRunCreate(
            agent_version_id=version.id,
            suite_id="support-ops",
            suite_version="v1",
            suite_manifest_hash="manifest1",
            seed=7,
        )
    )

    task_ids = [task.task_id for task in list(SEED_TASKS)[:3]]
    execution_ids = []
    for task_id in task_ids:
        execution = await store.create_execution(run.id, TaskExecutionCreate(task_id=task_id, task_seed=7))
        execution_ids.append(execution.id)
        await queue.enqueue(EvaluationJob(execution_id=execution.id, agent_version_id=version.id, task_id=task_id))

    processed = await run_worker_loop(store, queue, TASK_REGISTRY, consumer="worker-1", block_ms=200)
    assert processed == len(task_ids)

    await redis.aclose()

    for execution_id in execution_ids:
        execution = await store.get_execution(execution_id)
        trace = await store.get_trace(execution_id)
        assert execution.status != "pending"
        assert len(trace) > 0
