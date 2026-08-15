"""Load test: enqueue a batch of jobs, drain them with N concurrent workers against
real Postgres + Redis, and report throughput, latency percentiles, and failure rate.

Workers don't rely on run_worker_loop's auto-stop-on-empty-queue behavior: with
multiple consumers racing on the same Redis consumer group, one worker can see an
empty claim while another is still mid-flight with unacked work, and would stop
early. Instead each worker loops until an explicit stop signal, which the driver
sets only once polling confirms every enqueued execution has actually finished.

Uses the existing ReferenceAgentModelClient oracle - no live model backend needed,
consistent with the rest of the repo. Every job targets the same seeded task, so
correctness isn't the point here; only queue/worker throughput and latency are.

Usage:
    docker compose up -d postgres redis
    alembic upgrade head
    PYTHONPATH=".:backend" python scripts/load_test.py --jobs 200 --workers 8
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time

from app.postgres_store import PostgresStore
from app.queue import EvaluationJob, Queue, create_redis_client
from app.schemas import AgentVersionCreate, EvaluationRunCreate, TaskExecutionCreate
from benchmark.tasks import SEED_TASKS
from runner.worker import claim_and_process_one, task_registry_from

TASK_REGISTRY = task_registry_from(list(SEED_TASKS))
TASK = SEED_TASKS[0]


async def _seed_jobs(store: PostgresStore, queue: Queue, count: int) -> dict[str, float]:
    version = await store.create_agent_version(
        AgentVersionCreate(
            name="load-test-agent",
            git_sha="loadtest",
            model="reference-agent",
            system_prompt="follow policy",
            tool_schema_hash="loadtesthash",
        )
    )
    run = await store.create_run(
        EvaluationRunCreate(
            agent_version_id=version.id,
            suite_id="load-test",
            suite_version="v1",
            suite_manifest_hash="loadtestmanifest",
            seed=1,
        )
    )

    enqueued_at: dict[str, float] = {}
    for i in range(count):
        execution = await store.create_execution(run.id, TaskExecutionCreate(task_id=TASK.task_id, task_seed=i))
        execution_id = str(execution.id)
        enqueued_at[execution_id] = time.monotonic()
        await queue.enqueue(
            EvaluationJob(execution_id=execution.id, agent_version_id=version.id, task_id=TASK.task_id)
        )
    return enqueued_at


async def _worker(
    store: PostgresStore, queue: Queue, consumer: str, stop_event: asyncio.Event, counts: dict[str, int]
) -> None:
    processed = errored = 0
    while not stop_event.is_set():
        try:
            did_work = await claim_and_process_one(store, queue, TASK_REGISTRY, consumer, block_ms=200)
        except Exception:
            errored += 1
            continue
        if did_work:
            processed += 1
    counts[consumer] = processed
    counts[f"{consumer}:errors"] = errored


async def _poll_until_done(
    store: PostgresStore, execution_ids: set[str], poll_interval: float, timeout: float
) -> dict[str, float]:
    completed_at: dict[str, float] = {}
    deadline = time.monotonic() + timeout
    remaining = set(execution_ids)
    while remaining and time.monotonic() < deadline:
        for execution_id in list(remaining):
            try:
                execution = await store.get_execution(execution_id)
            except Exception:
                continue
            if execution.status != "pending":
                completed_at[execution_id] = time.monotonic()
                remaining.discard(execution_id)
        if remaining:
            await asyncio.sleep(poll_interval)
    return completed_at


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round(pct * (len(ordered) - 1))))
    return ordered[index]


async def main(jobs: int, workers: int, timeout: float) -> None:
    store = PostgresStore()
    redis = create_redis_client()
    queue = Queue(redis)
    await queue.ensure_group()

    print(f"seeding {jobs} jobs ...")
    enqueued_at = await _seed_jobs(store, queue, jobs)
    execution_ids = set(enqueued_at)

    stop_event = asyncio.Event()
    counts: dict[str, int] = {}
    worker_tasks = [
        asyncio.create_task(_worker(store, queue, f"worker-{i}", stop_event, counts)) for i in range(workers)
    ]

    started_at = time.monotonic()
    completed_at = await _poll_until_done(store, execution_ids, poll_interval=0.05, timeout=timeout)
    elapsed = time.monotonic() - started_at

    stop_event.set()
    await asyncio.gather(*worker_tasks)
    await redis.aclose()

    succeeded = len(completed_at)
    failed = jobs - succeeded
    latencies_ms = [(completed_at[eid] - enqueued_at[eid]) * 1000 for eid in completed_at]
    total_processed = sum(v for k, v in counts.items() if not k.endswith(":errors"))
    total_worker_errors = sum(v for k, v in counts.items() if k.endswith(":errors"))

    print()
    print(f"jobs:              {jobs}")
    print(f"workers:           {workers}")
    print(f"completed:         {succeeded} ({succeeded / jobs:.1%})")
    print(f"timed out/failed:  {failed} ({failed / jobs:.1%})")
    print(f"worker exceptions: {total_worker_errors}")
    print(f"wall clock:        {elapsed:.2f}s")
    print(f"throughput:        {succeeded / elapsed:.2f} jobs/sec" if elapsed > 0 else "throughput: n/a")
    if latencies_ms:
        print(f"latency p50:       {_percentile(latencies_ms, 0.50):.1f} ms")
        print(f"latency p95:       {_percentile(latencies_ms, 0.95):.1f} ms")
        print(f"latency p99:       {_percentile(latencies_ms, 0.99):.1f} ms")
        print(f"latency mean:      {statistics.mean(latencies_ms):.1f} ms")
    print(f"per-worker jobs processed: {sorted(v for k, v in counts.items() if not k.endswith(':errors'))}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=int, default=100)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=60.0, help="seconds to wait for all jobs to complete")
    args = parser.parse_args()
    asyncio.run(main(args.jobs, args.workers, args.timeout))
