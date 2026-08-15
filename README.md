# AgentProof

**Evaluation, regression detection, and trace debugging for AI agents.**

AgentProof makes AI-agent changes measurable. Run reproducible benchmark suites against versioned agents, capture structured tool-use traces, detect regressions, and inspect the first trace divergence associated with a failed task.

## The problem

An agent can pass a demo and still regress after a prompt, model, tool-schema, or routing change. Aggregate pass rates alone do not explain why. AgentProof treats agents as unreliable production systems: it pairs a baseline and candidate version on the same tasks, records every model and tool step, then surfaces the changed behavior that is most associated with a failure.

## What AgentProof will do

- Run versioned agents against deterministic, reproducible task suites.
- Capture prompts, model responses, tool calls, tool results, retries, latency, token usage, and errors as ordered traces.
- Score outcomes with executable task contracts and transparent LLM judges where deterministic checks are insufficient.
- Compare paired baseline and candidate runs by task, correctness, latency, cost, and failure mode.
- Attribute pass-to-fail regressions to the first material trace divergence: a changed tool choice, invalid argument, tool failure, policy violation, or early termination.
- Generate validated, constraint-preserving adversarial task variants and preserve their lineage.
- Surface judge disagreement instead of hiding it behind a single opaque score.

## Initial benchmark: customer-support operations

The first benchmark evaluates a support agent that can look up customers and orders, inspect policies, issue permitted refunds or replacements, draft responses, and update tickets. Each task has synthetic seeded state and a structured success contract, enabling robust checks of both the agent's final response and the actions it took.

## Planned architecture

```text
React / TypeScript UI
        |
FastAPI API - versions, suites, runs, trace queries
        |
PostgreSQL <--> Redis job queue <--> evaluation workers
                                      |
                         agent runner + traced tool proxy
                                      |
                       isolated, seeded support-tool environment
```

## Repository structure

```text
agent-proof/
├── backend/       # FastAPI API, database models, worker orchestration
├── runner/        # Agent runner, trace instrumentation, tool proxy
├── benchmark/     # Task definitions, contracts, mutations, validators
├── judges/        # Deterministic and LLM-based scoring
├── frontend/      # React comparison and trace-replay dashboard
├── tests/         # Unit, integration, and seeded-regression tests
├── docs/          # Architecture, methodology, benchmark reports
└── docker-compose.yml
```

## Development setup

```bash
git clone https://github.com/VivekMaranganti/agent-proof.git
cd agent-proof
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

When active, your shell prompt should begin with `(.venv)`. Leave the environment with `deactivate`.

Run the test suite with `pytest`; tests that need Postgres skip cleanly if it isn't running.

### Reproducing the end-to-end milestone

The first implementation milestone: one agent version, a seeded support task, a complete trace, and a deterministic score, persisted through the platform API and read back over that same API.

```bash
docker compose up -d postgres
alembic upgrade head
PYTHONPATH=".:backend" python scripts/run_demo_task.py
```

`scripts/run_demo_task.py` runs a scripted agent (there's no live model backend wired up yet, see `runner/model_client.py`) against the `support_refund_within_30_days_001` seed task through `runner.run_task`, scores the result with `judges.contracts.score_run`, and persists both the trace and the score through the same FastAPI app the platform serves. It prints the run id, execution id, pass/fail, and the number of trace steps persisted, and it's reproducible: rerunning it always produces a fresh run that passes the same way.

### Deployed demo (full stack)

Brings up Postgres, Redis, the API, and a worker as containers, all built from the same image.

```bash
docker compose up -d --build
docker compose run --rm api python scripts/seed_demo_data.py
```

The first command starts `postgres` and `redis`, runs a one-shot `migrate` service (`alembic upgrade head`) that `api` and `worker` both wait on before starting, then brings up `api` (`http://localhost:8000`, see the Platform API table below) and `worker` (`python -m runner.worker`, claims jobs off the Redis queue forever — see `runner/worker.py`'s `serve_forever`).

`scripts/seed_demo_data.py` seeds the same baseline/candidate regression scenario as `scripts/run_demo_comparison.py` (three seeded tasks, one genuine regression on `support_refund_within_30_days_001`), but into the stack's real Postgres instead of an in-process store, and prints a ready-to-use comparison URL. Re-running it just adds another baseline/candidate pair rather than erroring, so it's a manual step, not an automatic one on every `docker compose up`.

The frontend isn't containerized yet — run it separately with `npm run dev` in `frontend/` (see `frontend/README.md`), pointed at `http://localhost:8000` via `VITE_API_BASE_URL`.

Tear down with `docker compose down` (add `-v` to also drop the seeded data).

### Load testing

```bash
docker compose up -d postgres redis
alembic upgrade head
PYTHONPATH=".:backend" python scripts/load_test.py --jobs 100 --workers 4 --timeout 60
```

`scripts/load_test.py` seeds a batch of jobs against one seeded task, drains them with N concurrent workers, and reports wall-clock time, throughput, and p50/p95/p99 latency. Uses the deterministic `ReferenceAgentModelClient` oracle, not a live model, so it measures queue/worker overhead, not agent latency. See `docs/load-test-results.md` for baseline numbers from a real run and their limitations (single process, single machine - not a substitute for testing the actual multi-container deployment under real concurrent load).

## Platform API

Interactive docs (generated from the live schema) are at `/docs` once the app is running. Summary of the surface:

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/tasks` | List every seed task's contract (`expected_actions`, `forbidden_actions`, `expected_final_state`, etc.) |
| GET | `/api/v1/tasks/{task_id}` | Fetch one task's contract |
| POST | `/api/v1/agent-versions` | Register an agent version. Idempotent on content: identical `model`/`system_prompt`/`tool_schema_hash`/`config` returns the existing version instead of creating a duplicate |
| GET | `/api/v1/agent-versions/{id}` | Fetch an agent version |
| POST | `/api/v1/evaluation-runs` | Start a run against an agent version |
| POST | `/api/v1/evaluation-runs/{run_id}/executions` | Create a task execution within a run |
| GET | `/api/v1/evaluation-runs/{run_id}/executions` | List a run's executions. Filterable: `task_id`, `passed` |
| POST | `/api/v1/executions/{id}/trace-events` | Append one ordered trace step |
| GET | `/api/v1/executions/{id}/trace` | Read an execution's trace, ordered by `sequence_no`. Paginated: `limit` (default 200, max 1000) and `offset` query params; total count is in the `X-Total-Count` response header |
| POST | `/api/v1/executions/{id}/result` | Record an execution's deterministic score |
| GET | `/api/v1/executions/{id}` | Fetch an execution's recorded result, including contract-check detail (`missing_expected_actions`, `forbidden_actions_seen`, `final_state_mismatches`) |
| POST | `/api/v1/executions/{id}/judge-verdicts` | Record one LLM judge's verdict (label, confidence, rationale) for an execution |
| GET | `/api/v1/executions/{id}/judge-verdicts` | List an execution's judge verdicts |
| GET | `/api/v1/comparisons/{baseline_run_id}/{candidate_run_id}` | Paired comparison: per-task disposition, latency/cost deltas, and first-divergence attribution for regressions. Filterable: `task_id`, `disposition`, `divergence_type` (only narrows `results`; `compared_tasks`/`regressions`/`improvements` always reflect the whole comparison) |

`judges/orchestration.py`'s `run_judges` decides which judges apply to an execution; `runner/worker.py`'s `process_job` runs them and persists verdicts, but only when given a `judge_model_caller` - it's opt-in, not automatic, and nothing wires one up by default since there's still no live model backend (same gap as the agent's own `ModelClient`, see `runner/model_client.py`). Judge evaluation cadence (every execution, a sample, on-demand only) is a call for whoever wires a real caller in, not decided here.

See `docs/data-model-invariants.md` for what each core entity (`AgentVersion`, `EvaluationRun`, `TaskExecution`, `TraceEvent`, `JudgeVerdict`) actually guarantees at the database level - identity, ordering, finalization, and what's deliberately left unenforced.

## Evaluation principles

- Agent versions and benchmark snapshots are immutable and reproducible. AgentVersion identity is content-hashed (`backend/app/versioning.py`, over `model`/`system_prompt`/`tool_schema_hash`/`config` - not the `name` label or `git_sha` provenance): creating a version with content identical to an existing one returns that same version rather than minting a new identity, enforced by a real uniqueness constraint in Postgres, not just an app-level check. `benchmark.serialization.compute_content_hash` gives `SuiteSnapshot` the same guarantee.
- Raw trace data is redacted before persistence (`backend/app/redaction.py`; key-name based - `name`, `email`, `phone`, `address`, etc., scrubbed at any nesting depth in a trace event's payload before it's written). Scoring and attribution run on the real, unredacted values in memory before that happens; only what's actually persisted (and anything read back from it later - comparisons, replay) is affected. That's a real tradeoff: if a redacted field is exactly where two runs differ, comparison can no longer see that difference after the fact.
- Deterministic scoring is preferred for verifiable actions and state changes.
- LLM judges use explicit rubrics; their individual labels, confidence, and disagreement are retained.
- Regression attribution is evidence-backed trace correlation, not a claim of causal proof.
- Published performance and quality claims will come from reproducible scripts and benchmark reports (`scripts/load_test.py` / `docs/load-test-results.md` for queue and worker throughput).

## Roadmap

1. Define data contracts and build the deterministic support-tool sandbox.
2. Implement the runner, trace model, worker queue, and deterministic scorer.
3. Add version comparison, paired regression analysis, and trace-based attribution.
4. Build the dashboard and trace replay experience.
5. Add multi-judge scoring with a human-labeled gold set and disagreement analysis.
6. Add validated adversarial mutations, load testing, documentation, and a deployed demo.

## Team ownership

- **Vivek Maranganti:** platform architecture, FastAPI/PostgreSQL/Redis, tracing and performance, version comparison, regression attribution, and systems testing.
- **Gaurav Jha:** MCP-compatible tool environment, benchmark suite design, adversarial task mutation, judge methodology/gold-label study, and dashboard UX.

Both contributors will review architecture, own demo-visible features, and co-author the benchmark report.

## License

License selection is pending.
