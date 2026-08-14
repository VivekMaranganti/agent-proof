"""Full-stack integration: runner, queue, worker, scorer, and the platform API
chained together, not just each covered in isolation.

Creation and verification go through real HTTP calls against the actual FastAPI app
(an in-process ASGI client, not a live server); only enqueueing bypasses the API,
since there's no enqueue endpoint by design (see backend/app/queue.py's module
docstring - the API and the queue are deliberately decoupled). Requires both redis
and postgres; skips cleanly if either isn't reachable.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest
from sqlalchemy import text

from app.db import database_url, session_factory
from app.main import create_app
from app.postgres_store import PostgresStore
from app.queue import DEAD_LETTER_STREAM, STREAM, EvaluationJob, Queue, create_redis_client
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
            text("TRUNCATE trace_events, task_executions, evaluation_runs, agent_versions RESTART IDENTITY CASCADE")
        )
        await session.commit()
    redis = create_redis_client()
    await redis.delete(STREAM, DEAD_LETTER_STREAM)
    await redis.aclose()


async def test_api_created_run_is_processed_by_a_queued_worker_and_readable_over_the_api() -> None:
    store = PostgresStore()
    app = create_app(store)
    transport = httpx.ASGITransport(app=app)
    redis = create_redis_client()
    queue = Queue(redis)
    await queue.ensure_group()

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        version_response = await client.post(
            "/api/v1/agent-versions",
            json={
                "name": "oracle-agent",
                "git_sha": "abc1234",
                "model": "reference-agent",
                "system_prompt": "follow policy",
                "tool_schema_hash": "hash1234",
            },
        )
        assert version_response.status_code == 201
        version_id = version_response.json()["id"]

        run_response = await client.post(
            "/api/v1/evaluation-runs",
            json={
                "agent_version_id": version_id,
                "suite_id": "support-ops",
                "suite_version": "v1",
                "suite_manifest_hash": "manifest1",
                "seed": 7,
            },
        )
        assert run_response.status_code == 201
        run_id = run_response.json()["id"]

        task_ids = [task.task_id for task in list(SEED_TASKS)[:3]]
        execution_ids = []
        for task_id in task_ids:
            execution_response = await client.post(
                f"/api/v1/evaluation-runs/{run_id}/executions", json={"task_id": task_id, "task_seed": 7}
            )
            assert execution_response.status_code == 201
            execution_id = execution_response.json()["id"]
            execution_ids.append(execution_id)
            await queue.enqueue(
                EvaluationJob(execution_id=execution_id, agent_version_id=version_id, task_id=task_id)
            )

        processed = await run_worker_loop(store, queue, TASK_REGISTRY, consumer="worker-1", block_ms=200)
        assert processed == len(task_ids)

        listed = await client.get(f"/api/v1/evaluation-runs/{run_id}/executions")
        assert listed.status_code == 200
        assert {execution["id"] for execution in listed.json()} == set(execution_ids)
        assert all(execution["status"] != "pending" for execution in listed.json())

        for execution_id in execution_ids:
            fetched = await client.get(f"/api/v1/executions/{execution_id}")
            assert fetched.status_code == 200
            assert fetched.json()["status"] != "pending"

            trace = await client.get(f"/api/v1/executions/{execution_id}/trace")
            assert trace.status_code == 200
            assert len(trace.json()) > 0
            assert trace.headers["X-Total-Count"] == str(len(trace.json()))

    await redis.aclose()
