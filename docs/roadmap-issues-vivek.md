# AgentProof — Roadmap Issues (Vivek)

PR-sized GitHub issues covering Vivek Maranganti's ownership areas (platform
architecture, FastAPI/PostgreSQL/Redis, tracing & performance, version
comparison, regression attribution, systems testing), grouped by the README
roadmap phases. All are intended to be assigned to Vivek.

Companion script: `scripts/create-issues.sh` creates and self-assigns every
issue below via the GitHub CLI.

---

## Phase 1 — Data contracts & foundation

### 1. Finalize core data contracts for versions, suites, runs, and traces
Lock the Pydantic/schema definitions that everything else depends on: agent
version, benchmark suite/snapshot, run, and the ordered trace envelope.

- [ ] Define immutable `AgentVersion` and `SuiteSnapshot` identities (content-hashed)
- [ ] Define `Run` (baseline/candidate pairing, status, timing, cost)
- [ ] Define the trace envelope referenced by scoring and attribution
- [ ] Document invariants in `docs/`

**Acceptance:** schemas typed, validated, and imported by backend + runner without circular deps.
**Labels:** phase-1, area:platform

### 2. Postgres schema + Alembic migrations for trace storage
Extend the core tables to persist ordered trace steps efficiently and support
trace queries.

- [ ] Tables for runs, trace steps, tool calls/results, judgements
- [ ] Indexes for per-run ordered retrieval and divergence queries
- [ ] Alembic migration + downgrade
- [ ] Redaction hook applied before persistence

**Acceptance:** `alembic upgrade head` builds the schema; round-trip test writes and reads an ordered trace.
**Labels:** phase-1, area:platform, area:db

---

## Phase 2 — Runner, trace model, worker queue, scorer

### 3. Build agent runner with traced tool proxy
Create the `runner/` package: execute a versioned agent against a seeded task,
routing all tool calls through a proxy that records every step.

- [ ] Runner entrypoint takes (version, task) and returns a completed run
- [ ] Traced tool proxy wraps the tool environment
- [ ] Capture retries, latency, token usage, and errors
- [ ] Deterministic seeding of task state

**Acceptance:** running one version against one seeded task produces a complete, ordered trace.
**Labels:** phase-2, area:tracing

### 4. Define and implement the ordered trace model
Concrete, serializable representation of prompts, model responses, tool calls,
tool results, retries, latency, tokens, and errors as an ordered sequence.

- [ ] Step types and ordering guarantees
- [ ] Serialize/deserialize losslessly to the Postgres schema
- [ ] Stable step IDs for divergence comparison

**Acceptance:** trace serializes to storage and reconstructs identically; unit tests cover each step type.
**Labels:** phase-2, area:tracing

### 5. Implement Redis job queue and evaluation workers
Stand up the async execution path: enqueue runs, workers pull and execute via
the runner, results persisted.

- [ ] Redis-backed queue (enqueue/claim/complete/fail)
- [ ] Worker process that runs the runner and writes results
- [ ] Retry/backoff and dead-letter handling
- [ ] docker-compose wiring for Redis + workers

**Acceptance:** a suite of tasks enqueued is executed by workers and lands in Postgres.
**Labels:** phase-2, area:platform

### 6. Implement the deterministic scorer
Score outcomes against executable task contracts (final response + actions
taken) without LLM judgement.

- [ ] Evaluate contract checks over final state and trace actions
- [ ] Pass/fail with per-check detail
- [ ] Wire into the worker result path

**Acceptance:** deterministic pass/fail matches hand-labeled fixtures for the support tasks.
**Labels:** phase-2, area:scoring

### 7. Milestone: reproducible end-to-end run
Integrate 3–6 into the first vertical slice: one agent version, one seeded
support task, a complete trace, deterministic score.

- [ ] Single command runs the slice
- [ ] Result persisted and retrievable via API
- [ ] Documented in README dev setup

**Acceptance:** `make e2e` (or documented command) produces a scored run reproducibly.
**Labels:** phase-2, area:platform, milestone

---

## Phase 3 — Comparison, regression analysis, attribution

### 8. Paired baseline/candidate run comparison
Compare two versions on the same tasks by correctness, latency, cost, and
failure mode.

- [ ] Comparison query joining paired runs
- [ ] Per-task deltas and aggregate summary
- [ ] API endpoint returning the comparison

**Acceptance:** comparing two versions returns per-task and aggregate diffs.
**Labels:** phase-3, area:comparison

### 9. First-divergence regression attribution engine
For a pass→fail regression, locate the first material trace divergence (changed
tool choice, invalid argument, tool failure, policy violation, early
termination).

- [ ] Align paired traces by stable step IDs
- [ ] Classify the first material divergence
- [ ] Return evidence-backed attribution (not causal claim)

**Acceptance:** on seeded regression fixtures, the engine reports the correct first divergence.
**Labels:** phase-3, area:attribution

### 10. Trace query API endpoints
Expose ordered trace retrieval, comparison, and attribution results to the
frontend.

- [ ] Endpoints for run trace, paired comparison, attribution
- [ ] Pagination / ordered retrieval
- [ ] Contract tests

**Acceptance:** endpoints documented and covered by API tests.
**Labels:** phase-3, area:platform

---

## Phase 4 — Dashboard support (API side)

### 11. Trace replay API to back the dashboard
Provide the backend surface the replay/comparison UI needs (Gaurav owns the UI).

- [ ] Replay-friendly ordered step feed
- [ ] Filters by task, correctness, failure mode
- [ ] Stable IDs for deep-linking

**Acceptance:** UI can render a full trace replay from these endpoints alone.
**Labels:** phase-4, area:platform

---

## Phase 6 — Performance, deployment, systems testing

### 12. Load-testing harness
Measure throughput and latency of the queue + workers under realistic suite
sizes.

- [ ] Parameterized load scenarios
- [ ] Report throughput, latency percentiles, failure rate
- [ ] Baseline numbers checked into docs

**Acceptance:** reproducible load run emits a metrics report.
**Labels:** phase-6, area:performance

### 13. Dockerized deployment + demo environment
Package the stack for a deployed demo.

- [ ] Production-oriented compose/deploy config
- [ ] Seeded demo data
- [ ] Documented bring-up

**Acceptance:** documented steps bring up a working demo instance.
**Labels:** phase-6, area:platform

### 14. Systems / integration test suite + CI
End-to-end and seeded-regression tests wired into CI.

- [ ] Integration tests across runner, queue, scorer, API
- [ ] Seeded-regression tests for the attribution engine
- [ ] CI workflow running the suite

**Acceptance:** CI runs green on the integration + regression suites.
**Labels:** phase-6, area:testing
