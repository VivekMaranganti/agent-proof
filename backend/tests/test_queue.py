"""Queue tests. Requires a reachable Redis (see docker-compose.yml).

Skips cleanly when redis isn't up, so plain `pytest` stays green without docker.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from app.queue import DEAD_LETTER_STREAM, STREAM, EvaluationJob, Queue, create_redis_client


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


@pytest.fixture(autouse=True)
async def _clean_streams(redis):
    yield
    await redis.delete(STREAM, DEAD_LETTER_STREAM)


@pytest.fixture
async def redis():
    client = create_redis_client()
    yield client
    await client.aclose()


@pytest.fixture
async def queue(redis) -> Queue:
    q = Queue(redis, max_attempts=2)
    await q.ensure_group()
    return q


def _job(**overrides) -> EvaluationJob:
    defaults = dict(execution_id=uuid4(), agent_version_id=uuid4(), task_id="refund-001")
    defaults.update(overrides)
    return EvaluationJob(**defaults)


async def test_ensure_group_is_idempotent(queue: Queue) -> None:
    await queue.ensure_group()
    await queue.ensure_group()


async def test_claim_returns_none_when_nothing_enqueued(queue: Queue) -> None:
    claimed = await queue.claim("worker-1", block_ms=200)
    assert claimed is None


async def test_enqueue_then_claim_round_trips_the_job(queue: Queue) -> None:
    job = _job(task_id="refund-002")
    await queue.enqueue(job)

    claimed = await queue.claim("worker-1")

    assert claimed is not None
    _message_id, claimed_job = claimed
    assert claimed_job == job


async def test_ack_removes_the_job_so_it_is_not_reclaimed(queue: Queue) -> None:
    await queue.enqueue(_job())
    message_id, _job_data = await queue.claim("worker-1")
    await queue.ack(message_id)

    assert await queue.claim("worker-2", block_ms=200) is None


async def test_retry_re_enqueues_with_incremented_attempt(queue: Queue) -> None:
    await queue.enqueue(_job())
    message_id, job = await queue.claim("worker-1")
    assert job.attempt == 1

    retried = await queue.retry_or_deadletter(message_id, job, "transient failure")

    assert retried is True
    _next_id, next_job = await queue.claim("worker-1")
    assert next_job.attempt == 2
    assert next_job.execution_id == job.execution_id


async def test_dead_letters_after_max_attempts(queue: Queue, redis) -> None:
    await queue.enqueue(_job(task_id="refund-dlq"))

    message_id, job = await queue.claim("worker-1")
    retried = await queue.retry_or_deadletter(message_id, job, "first failure")
    assert retried is True

    message_id, job = await queue.claim("worker-1")
    assert job.attempt == 2
    retried = await queue.retry_or_deadletter(message_id, job, "second failure")
    assert retried is False

    assert await queue.claim("worker-1", block_ms=200) is None
    dead_entries = await redis.xrange(DEAD_LETTER_STREAM, min="-", max="+")
    assert len(dead_entries) == 1
    _entry_id, fields = dead_entries[0]
    assert fields["error"] == "second failure"
    assert fields["attempts"] == "2"


async def test_two_consumers_in_the_same_group_do_not_claim_the_same_job(queue: Queue) -> None:
    await queue.enqueue(_job())
    await queue.enqueue(_job())

    first = await queue.claim("worker-1")
    second = await queue.claim("worker-2")

    assert first is not None
    assert second is not None
    assert first[0] != second[0]
