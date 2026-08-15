# Load test results

Baseline numbers for `scripts/load_test.py`, per README's evaluation principle that
performance claims come from reproducible scripts, not assertion. Every number below
is from an actual run against real Postgres and Redis (throwaway Docker containers on
a single laptop), not estimated.

## Method

`scripts/load_test.py` seeds N `TaskExecution`s against one seeded task, enqueues one
job per execution, and drains the queue with W concurrent workers running in the same
Python process (`asyncio` tasks, not separate OS processes - see "what this doesn't
measure" below). The job uses `runner.reference_agent.ReferenceAgentModelClient`
(the deterministic oracle already used elsewhere in the repo), not a live model, so
these numbers are queue/worker overhead only, not agent or model latency. Per-job
latency is wall-clock time from enqueue to the execution leaving `pending` status.

Reproduce with:

```bash
docker compose up -d postgres redis
alembic upgrade head
PYTHONPATH=".:backend" python scripts/load_test.py --jobs 100 --workers 4 --timeout 60
```

## Results

Run on 2026-08-14, one laptop, both Postgres and Redis as local Docker containers on
default settings (no tuning).

| Jobs | Workers | Wall clock | Throughput (jobs/sec) | p50 latency | p95 latency | p99 latency | Failures |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 100 | 1 | 3.69s | 27.1 | 2085 ms | 3539 ms | 3642 ms | 0 |
| 100 | 4 | 1.91s | 52.5 | 1220 ms | 1860 ms | 1909 ms | 0 |
| 100 | 16 | 2.32s | 43.1 | 1996 ms | 2310 ms | 2325 ms | 0 |
| 300 | 4 | 5.61s | 53.5 | 3487 ms | 5416 ms | 5568 ms | 0 |

Zero failures and zero worker exceptions across every run - nothing here stress-tests
correctness under failure, only throughput and latency under load. Retry/dead-letter
behavior is covered separately by `backend/tests/test_queue.py`, not by this harness.

## What this shows

- **4 workers roughly doubles throughput over 1** (27 → 52 jobs/sec), consistent
  whether the batch is 100 or 300 jobs (52.5 vs 53.5 jobs/sec) - throughput is stable
  under load, not just a lucky small-batch number.
- **16 workers is worse than 4** (43 vs 52 jobs/sec), not better. All workers in this
  harness run as `asyncio` tasks inside one Python process on one CPU core, so past
  some point adding more concurrent workers adds Postgres/Redis round-trip contention
  without adding real parallelism. This is a real, useful finding about *this specific
  single-process test harness* - it is not a claim about the deployed `worker` service
  in `docker-compose.yml`, which runs as one process per container and would need
  multiple container replicas (out of scope here) to test true multi-process scaling.
- **Latency grows with queue depth**, as expected for a fixed number of workers behind
  a FIFO-ish queue: p50 latency roughly triples going from 100 to 300 jobs at the same
  4 workers, because later jobs simply wait longer before being claimed.

## Known limitations of this harness

- Single process, single machine: doesn't measure multi-container/multi-machine
  worker scaling, network latency between services, or Postgres/Redis under
  production-grade concurrent load from other tenants.
- Every job runs the same seeded task through the same deterministic oracle client -
  doesn't measure variance from a real, variable-latency LLM backend, which doesn't
  exist in this repo yet (see `runner/model_client.py`).
- No sustained-load or soak testing (all runs here complete in single-digit seconds);
  doesn't say anything about behavior over hours, memory growth, or connection pool
  exhaustion.
