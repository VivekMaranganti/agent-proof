"""Redis-backed evaluation job queue.

A Redis Stream plus a single consumer group gives at-least-once delivery: a claimed
message stays in the group's pending entries list until acked, so a worker that dies
mid-job doesn't silently lose it (recovering those stranded pending entries after a
crash, via XCLAIM/XAUTOCLAIM, isn't implemented yet - documented gap, not silently
skipped). Retry count lives in the job payload itself rather than Redis's per-message
delivery counter, since a retry here re-enqueues as a new stream entry rather than
redelivering the same one.
"""

from __future__ import annotations

import asyncio
import json
import os
from uuid import UUID

from pydantic import BaseModel, Field
from redis.asyncio import Redis
from redis.exceptions import ResponseError

STREAM = "agentproof:evaluation-jobs"
GROUP = "agentproof:workers"
DEAD_LETTER_STREAM = "agentproof:evaluation-jobs:dead"
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_REDIS_URL = "redis://localhost:6379/0"


def redis_url() -> str:
    return os.environ.get("REDIS_URL", DEFAULT_REDIS_URL)


def create_redis_client() -> Redis:
    return Redis.from_url(redis_url(), decode_responses=True)


class EvaluationJob(BaseModel):
    execution_id: UUID
    agent_version_id: UUID
    task_id: str
    attempt: int = Field(default=1, ge=1)


class Queue:
    def __init__(self, redis: Redis, *, max_attempts: int = DEFAULT_MAX_ATTEMPTS) -> None:
        self._redis = redis
        self._max_attempts = max_attempts

    async def ensure_group(self) -> None:
        try:
            await self._redis.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
        except ResponseError as error:
            if "BUSYGROUP" not in str(error):
                raise

    async def enqueue(self, job: EvaluationJob) -> str:
        return await self._redis.xadd(STREAM, {"payload": job.model_dump_json()})

    async def claim(self, consumer: str, *, block_ms: int = 1000) -> tuple[str, EvaluationJob] | None:
        response = await self._redis.xreadgroup(GROUP, consumer, {STREAM: ">"}, count=1, block=block_ms)
        if not response:
            return None
        _stream_name, messages = response[0]
        message_id, fields = messages[0]
        return message_id, EvaluationJob.model_validate(json.loads(fields["payload"]))

    async def ack(self, message_id: str) -> None:
        await self._redis.xack(STREAM, GROUP, message_id)

    async def retry_or_deadletter(self, message_id: str, job: EvaluationJob, error: str) -> bool:
        """Re-enqueues job with attempt+1, or dead-letters it past max_attempts.

        Returns True if it was retried, False if it was dead-lettered.
        """

        await self.ack(message_id)
        if job.attempt >= self._max_attempts:
            await self._redis.xadd(
                DEAD_LETTER_STREAM, {"payload": job.model_dump_json(), "error": error, "attempts": str(job.attempt)}
            )
            return False

        await asyncio.sleep(min(2 ** (job.attempt - 1), 30))
        retried = job.model_copy(update={"attempt": job.attempt + 1})
        await self.enqueue(retried)
        return True
