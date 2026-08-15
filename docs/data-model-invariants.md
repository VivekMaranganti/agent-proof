# Data model invariants

What the platform's core entities actually guarantee, and what they deliberately
don't. Grounded in `backend/app/schemas.py`, `backend/app/models.py`, and
`backend/app/store.py` as of this writing - if this document and the code disagree,
the code is right and this needs updating, not the other way around.

## AgentVersion

- **Identity is content-hashed, not assigned.** `content_hash` (`backend/app/versioning.py`) is computed from `model`, `system_prompt`, `tool_schema_hash`, and `config` - deliberately *not* `name` (a label) or `git_sha` (provenance, not behavior). `name` and `git_sha` can differ across calls without producing a new version.
- **Creation is idempotent, enforced at the database level.** `create_agent_version` with content matching an existing version returns that version rather than creating a duplicate. `AgentVersionModel.content_hash` has a real Postgres `UNIQUE` constraint, not just an application-level check - `PostgresStore.create_agent_version` checks first, then handles the race (concurrent identical inserts) by catching the constraint violation and re-querying, rather than assuming the check-then-insert is atomic.
- **Immutable once created.** There is no update path anywhere in `Store` - only `create_agent_version` and `get_agent_version`. Changing a version's behavior means creating a new one with a new content hash, never editing a row in place.

## EvaluationRun

- **References an existing AgentVersion**, enforced by both a foreign key (Postgres) and an explicit existence check before insert (`PlatformStore` has no FK to enforce it, so the check is duplicated at the application layer specifically so both stores behave identically).
- **No baseline/candidate pairing is stored on the Run itself.** Two runs being "baseline" and "candidate" of each other is not a persisted relationship - it's purely positional, decided at query time by which two run IDs you pass to `GET /api/v1/comparisons/{baseline_run_id}/{candidate_run_id}`. Nothing stops comparing two runs that were never intended to be compared, and nothing prevents the same run from being used as baseline in one comparison and candidate in another.
- **No run-level cost or timing aggregate is stored.** `estimated_cost_usd` and `latency_ms` live on `TaskExecution`, per task. A run's total cost/latency is a sum over its executions, computed on demand (currently not even computed anywhere - `RunComparison` only ever reports per-task deltas, never a run-level total).

## TaskExecution

- **`task_id` is a free string, not a foreign key to anything.** There's no database-level guarantee that `task_id` corresponds to a real `BenchmarkTask` in `benchmark.tasks.SEED_TASKS` - `GET /api/v1/tasks/{task_id}` will 404 for a typo'd or since-removed task id even though the `TaskExecution` referencing it persists fine. The task contract and the execution that ran against it are only linked by this string matching at read time.
- **Finalization is one-way and enforced.** `record_result` rejects (409) being called a second time once `status` is `passed`, `failed`, or `errored` - `TaskExecutionResult`'s own validator additionally rejects internally inconsistent combinations (e.g. `status=passed` with `passed=false`) before that check even runs. There is no way to un-finalize or correct a recorded result; a wrong result means creating a new execution.
- **`missing_expected_actions` / `forbidden_actions_seen` / `final_state_mismatches` are evidence, not verdicts.** They're the literal output of `judges.contracts.score_run` at the moment of finalization, folded in by `execution_scoring.score_execution`. They aren't recomputed if the task's contract changes later - an execution's stored mismatches reflect the contract as it existed when the execution finished, not the current one.

## TraceEvent

- **Ordering is `sequence_no`, assigned client-side, enforced server-side.** `runner.trace.Trace.append` assigns `sequence_no` by append order in memory - nothing about the database enforces gap-free sequencing on write. What Postgres *does* enforce is uniqueness: `UniqueConstraint(execution_id, sequence_no)` rejects two events claiming the same position in the same execution's trace (`append_trace_event` translates that into a 409, not a 500). `runner.trace.Trace.from_storage` is the one place that actually validates gap-free-ness, and only when reconstructing a `Trace` object from stored events - the raw `GET .../trace` endpoint returns whatever's there in `sequence_no` order without checking for gaps.
- **Redacted on write, not on read.** `redact_payload` runs once, inside `append_trace_event`, before the row is written (`backend/app/redaction.py`). There is no unredacted copy anywhere in the store - the tradeoff is real and one-way: if a redacted field happens to be exactly where a baseline and candidate execution's tool calls differ, `comparison.py` can no longer see that difference, because by the time it reads the trace back, the difference is already gone.
- **`parent_event_id` is not a foreign key.** It references another `TraceEvent.id`, but nothing in the schema enforces that the referenced event exists or belongs to the same execution. `Trace.append`/`Trace.from_storage` validate this in application code for events built through the `Trace` class, but an event inserted directly via `POST .../trace-events` with a bogus `parent_event_id` will persist without complaint.

## JudgeVerdict

- **No uniqueness constraint on `(execution_id, judge_name)`.** Unlike `AgentVersion`'s content hash, nothing stops `append_judge_verdict` being called multiple times for the same judge on the same execution - each call just appends another row. This is a deliberate choice, not an oversight: a verdict is evidence emitted at a point in time (tied to a specific `rubric_version`), not a mutable "current status" field, so treating it as an append-only log rather than an upsert-on-conflict value is consistent with how `TraceEvent` works. The consequence: a UI or query reading verdicts back has to decide for itself how to handle more than one verdict from the same judge (most recent by `created_at`? all of them, surfaced as disagreement over time?) - the platform doesn't decide that for you.
- **Not wired into any run by default.** `runner.worker.process_job` only produces verdicts when called with a `judge_model_caller` - the default is `None`, meaning no live model backend exists yet to call. See the "Evaluation principles" section of the main README.

## Cross-cutting

- **Nothing is soft-deleted or archived.** There is no delete path anywhere in `Store` for any entity. The only way data leaves the database is `TRUNCATE` (used by tests to reset between runs) or `docker compose down -v`.
- **UUIDs are the only identity contract across HTTP.** Every entity's `id` is a UUID generated at creation (except `AgentVersion`, which is idempotent on content as described above). Clients should never assume anything about ID structure or ordering beyond uniqueness - `created_at` is the field to sort by, not the ID.
