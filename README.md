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

## Platform API

Interactive docs (generated from the live schema) are at `/docs` once the app is running. Summary of the surface:

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/v1/agent-versions` | Register an agent version |
| GET | `/api/v1/agent-versions/{id}` | Fetch an agent version |
| POST | `/api/v1/evaluation-runs` | Start a run against an agent version |
| POST | `/api/v1/evaluation-runs/{run_id}/executions` | Create a task execution within a run |
| GET | `/api/v1/evaluation-runs/{run_id}/executions` | List a run's executions |
| POST | `/api/v1/executions/{id}/trace-events` | Append one ordered trace step |
| GET | `/api/v1/executions/{id}/trace` | Read an execution's trace, ordered by `sequence_no`. Paginated: `limit` (default 200, max 1000) and `offset` query params; total count is in the `X-Total-Count` response header |
| POST | `/api/v1/executions/{id}/result` | Record an execution's deterministic score |
| GET | `/api/v1/executions/{id}` | Fetch an execution's recorded result |
| GET | `/api/v1/comparisons/{baseline_run_id}/{candidate_run_id}` | Paired comparison: per-task disposition, latency/cost deltas, and first-divergence attribution for regressions |

## Evaluation principles

- Agent versions and benchmark snapshots are immutable and reproducible.
- Raw trace data is redacted before persistence.
- Deterministic scoring is preferred for verifiable actions and state changes.
- LLM judges use explicit rubrics; their individual labels, confidence, and disagreement are retained.
- Regression attribution is evidence-backed trace correlation, not a claim of causal proof.
- Published performance and quality claims will come from reproducible scripts and benchmark reports.

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
