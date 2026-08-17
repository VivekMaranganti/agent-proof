"""scripts/load_test.py: the percentile math directly, plus one tiny real run against
Postgres + Redis to prove the seed/drain/poll loop actually works, not just the math.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text

from app.db import database_url, session_factory
from app.queue import DEAD_LETTER_STREAM, STREAM, create_redis_client
from scripts.load_test import _percentile, main


def test_percentile_of_a_single_value() -> None:
    assert _percentile([42.0], 0.50) == 42.0
    assert _percentile([42.0], 0.99) == 42.0


def test_percentile_p50_and_p99_of_ten_values() -> None:
    values = [float(i) for i in range(1, 11)]  # 1..10

    #index = round(pct * (len - 1)); round(0.50 * 9) = round(4.5) = 4 (banker's rounding), so values[4] = 5.0
    assert _percentile(values, 0.50) == 5.0
    assert _percentile(values, 0.99) == 10.0


def test_percentile_of_empty_list_is_nan() -> None:
    import math

    assert math.isnan(_percentile([], 0.50))


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


@pytest.mark.skipif(
    not (_postgres_reachable() and _redis_reachable()),
    reason="requires both postgres and redis, run: docker compose up -d postgres redis",
)
async def test_a_small_real_run_completes_every_job(capsys) -> None:
    async with session_factory() as session:
        await session.execute(
            text("TRUNCATE judge_verdicts, trace_events, task_executions, evaluation_runs, agent_versions RESTART IDENTITY CASCADE")
        )
        await session.commit()
    redis = create_redis_client()
    await redis.delete(STREAM, DEAD_LETTER_STREAM)
    await redis.aclose()

    await main(jobs=5, workers=2, timeout=15.0)

    output = capsys.readouterr().out
    assert "completed:         5 (100.0%)" in output
    assert "timed out/failed:  0 (0.0%)" in output

    cleanup_redis = create_redis_client()
    await cleanup_redis.delete(STREAM, DEAD_LETTER_STREAM)
    await cleanup_redis.aclose()
    async with session_factory() as session:
        await session.execute(
            text("TRUNCATE judge_verdicts, trace_events, task_executions, evaluation_runs, agent_versions RESTART IDENTITY CASCADE")
        )
        await session.commit()
