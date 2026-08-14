"""Worker tests against real Redis and an in-memory store.

The worker is Store-protocol-generic, so PlatformStore is enough to prove it works -
no need for the worker's own tests to also depend on Postgres being up. Skips cleanly
when redis isn't reachable.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import pytest

from app.queue import EvaluationJob, Queue, create_redis_client
from app.schemas import AgentVersionCreate, EvaluationRunCreate, TaskExecutionCreate
from app.store import PlatformStore
from benchmark.tasks import SEED_TASKS
from runner.worker import claim_and_process_one, process_job, run_worker_loop, task_registry_from


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
    not _redis_reachable(), reason="redis is not reachable, run: docker compose up -d redis"
)

TASK_REGISTRY = task_registry_from(list(SEED_TASKS))
KNOWN_PASSING_TASK_ID = "support_refund_outside_30_days_001"


@pytest.fixture
async def redis():
    client = create_redis_client()
    yield client
    await client.aclose()


@pytest.fixture(autouse=True)
async def _clean_streams(redis):
    from app.queue import DEAD_LETTER_STREAM, STREAM

    yield
    await redis.delete(STREAM, DEAD_LETTER_STREAM)


@pytest.fixture
async def queue(redis) -> Queue:
    q = Queue(redis, max_attempts=2)
    await q.ensure_group()
    return q


@pytest.fixture
def store() -> PlatformStore:
    return PlatformStore()


async def _seeded_job(store: PlatformStore, task_id: str = KNOWN_PASSING_TASK_ID) -> EvaluationJob:
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
    execution = await store.create_execution(run.id, TaskExecutionCreate(task_id=task_id, task_seed=7))
    return EvaluationJob(execution_id=execution.id, agent_version_id=version.id, task_id=task_id)


async def test_process_job_runs_the_agent_and_persists_trace_and_result(store: PlatformStore) -> None:
    job = await _seeded_job(store)

    await process_job(store, TASK_REGISTRY, job)

    execution = await store.get_execution(job.execution_id)
    trace = await store.get_trace(job.execution_id)
    assert execution.status == "passed"
    assert execution.passed is True
    assert len(trace) > 0


async def test_process_job_persists_contract_score_detail_not_just_pass_fail(store: PlatformStore) -> None:
    from runner.model_client import ModelReply, ScriptedModelClient, ToolCallRequest

    job = await _seeded_job(store, task_id="support_refund_within_30_days_001")
    model = ScriptedModelClient(
        [
            ModelReply(
                finish_reason="tool_calls",
                tool_calls=(ToolCallRequest("c1", "customer", "get_customer", {"customer_id": "CUST-001"}),),
            ),
            ModelReply(
                finish_reason="tool_calls",
                tool_calls=(
                    ToolCallRequest("c2", "ticket", "update_ticket", {"ticket_id": "TICK-9001", "status": "resolved"}),
                ),
            ),
            ModelReply(finish_reason="stop", content="Ticket resolved."),
        ]
    )

    await process_job(store, TASK_REGISTRY, job, model_client=model)

    execution = await store.get_execution(job.execution_id)
    assert execution.status == "failed"
    assert execution.passed is False
    assert "refund.create_refund" in execution.missing_expected_actions


async def test_claim_and_process_one_acks_on_success(store: PlatformStore, queue: Queue) -> None:
    job = await _seeded_job(store)
    await queue.enqueue(job)

    did_work = await claim_and_process_one(store, queue, TASK_REGISTRY, consumer="worker-1")

    assert did_work is True
    execution = await store.get_execution(job.execution_id)
    assert execution.status == "passed"
    assert await queue.claim("worker-2", block_ms=200) is None


async def test_claim_and_process_one_returns_false_when_queue_is_empty(store: PlatformStore, queue: Queue) -> None:
    did_work = await claim_and_process_one(store, queue, TASK_REGISTRY, consumer="worker-1", block_ms=200)
    assert did_work is False


async def test_unknown_task_id_is_retried_then_dead_lettered_without_crashing_the_worker(
    store: PlatformStore, queue: Queue, redis
) -> None:
    from app.queue import DEAD_LETTER_STREAM

    job = EvaluationJob(execution_id=UUID(int=1), agent_version_id=UUID(int=2), task_id="does-not-exist")
    await queue.enqueue(job)

    processed = await run_worker_loop(store, queue, TASK_REGISTRY, consumer="worker-1", stop_after=2)

    assert processed == 2
    dead_entries = await redis.xrange(DEAD_LETTER_STREAM, min="-", max="+")
    assert len(dead_entries) == 1


async def test_run_worker_loop_drains_a_suite_of_mixed_pass_fail_tasks(store: PlatformStore, queue: Queue) -> None:
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
    task_ids = [task.task_id for task in list(SEED_TASKS)[:4]]
    execution_ids = []
    for task_id in task_ids:
        execution = await store.create_execution(run.id, TaskExecutionCreate(task_id=task_id, task_seed=7))
        execution_ids.append(execution.id)
        await queue.enqueue(EvaluationJob(execution_id=execution.id, agent_version_id=version.id, task_id=task_id))

    processed = await run_worker_loop(store, queue, TASK_REGISTRY, consumer="worker-1", block_ms=200)

    assert processed == len(task_ids)
    executions = await store.get_run_executions(run.id)
    assert {execution.status for execution in executions} <= {"passed", "failed", "errored"}
    assert all(execution.status != "pending" for execution in executions)
