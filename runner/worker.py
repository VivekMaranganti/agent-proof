"""Worker: claims jobs off the queue, runs the agent, persists trace + result.

claim_and_process_one is the unit of work - testable without a background loop or a
shutdown signal. run_worker_loop is the thin real-usage wrapper around it.

Judge evaluation (judges.orchestration.run_judges) is opt-in via judge_model_caller,
not run by default. That's deliberate, not an oversight: there's still no live model
backend anywhere in this repo, so there's nothing to pass by default, and
judges/orchestration.py's own docstring is explicit that the cadence (every
execution, a sample, on-demand only) is an infrastructure call it isn't making -
defaulting it to "every execution" here would be making that call by accident.
"""

from __future__ import annotations

import asyncio
import os
import socket
from collections.abc import Mapping

from app.execution_scoring import score_execution
from app.queue import EvaluationJob, Queue
from app.schemas import JudgeVerdictCreate
from app.store import Store
from benchmark.schema import BenchmarkTask
from judges.llm import ModelCaller
from judges.orchestration import run_judges
from runner.model_client import ModelClient
from runner.reference_agent import ReferenceAgentModelClient
from runner.runner import run_task

TaskRegistry = Mapping[str, BenchmarkTask]


def task_registry_from(tasks: list[BenchmarkTask]) -> TaskRegistry:
    return {task.task_id: task for task in tasks}


async def process_job(
    store: Store,
    task_registry: TaskRegistry,
    job: EvaluationJob,
    *,
    model_client: ModelClient | None = None,
    judge_model_caller: ModelCaller | None = None,
) -> None:
    task = task_registry[job.task_id]
    version = await store.get_agent_version(job.agent_version_id)
    client = model_client or ReferenceAgentModelClient(task)

    result = await run_task(version, task, client, execution_id=job.execution_id)
    for event in result.trace.to_storage():
        await store.append_trace_event(job.execution_id, event)

    execution_result, _contract_score = score_execution(task, result)
    await store.record_result(job.execution_id, execution_result)

    if judge_model_caller is not None:
        for verdict in run_judges(task, result, judge_model_caller):
            await store.append_judge_verdict(
                job.execution_id,
                JudgeVerdictCreate(
                    judge_name=verdict.judge_name,
                    rubric_version=verdict.rubric_version,
                    label=verdict.label,
                    confidence=verdict.confidence,
                    rationale=verdict.rationale,
                ),
            )


async def claim_and_process_one(
    store: Store,
    queue: Queue,
    task_registry: TaskRegistry,
    consumer: str,
    *,
    block_ms: int = 1000,
    judge_model_caller: ModelCaller | None = None,
) -> bool:
    claimed = await queue.claim(consumer, block_ms=block_ms)
    if claimed is None:
        return False

    message_id, job = claimed
    try:
        await process_job(store, task_registry, job, judge_model_caller=judge_model_caller)
    except Exception as error:
        #any failure processing a job is a job failure, not a worker crash
        await queue.retry_or_deadletter(message_id, job, f"{type(error).__name__}: {error}")
    else:
        await queue.ack(message_id)
    return True


async def run_worker_loop(
    store: Store,
    queue: Queue,
    task_registry: TaskRegistry,
    consumer: str,
    *,
    block_ms: int = 1000,
    stop_after: int | None = None,
    judge_model_caller: ModelCaller | None = None,
) -> int:
    """Runs claim_and_process_one until nothing's left to claim, or stop_after jobs are processed."""

    processed = 0
    while stop_after is None or processed < stop_after:
        did_work = await claim_and_process_one(
            store, queue, task_registry, consumer, block_ms=block_ms, judge_model_caller=judge_model_caller
        )
        if not did_work:
            break
        processed += 1
    return processed


async def serve_forever(
    store: Store,
    queue: Queue,
    task_registry: TaskRegistry,
    consumer: str,
    *,
    block_ms: int = 5000,
    judge_model_caller: ModelCaller | None = None,
) -> None:
    """Never returns. For a deployed worker process, not tests.

    Unlike run_worker_loop, an empty queue isn't a stopping condition here - claim's
    block_ms is what keeps this from busy-looping while idle.
    """

    await queue.ensure_group()
    while True:
        await claim_and_process_one(
            store, queue, task_registry, consumer, block_ms=block_ms, judge_model_caller=judge_model_caller
        )


def _main() -> None:
    from app.postgres_store import PostgresStore
    from app.queue import Queue, create_redis_client
    from benchmark.tasks import SEED_TASKS

    store = PostgresStore()
    redis = create_redis_client()
    queue = Queue(redis)
    task_registry = task_registry_from(list(SEED_TASKS))
    consumer = os.environ.get("WORKER_CONSUMER_NAME", socket.gethostname())

    asyncio.run(serve_forever(store, queue, task_registry, consumer))


if __name__ == "__main__":
    _main()
