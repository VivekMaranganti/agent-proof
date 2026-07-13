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

This repository currently contains the project foundation. The first implementation milestone is a reproducible end-to-end run: one agent version, a seeded support task, a complete trace, and deterministic scoring.

```bash
git clone https://github.com/VivekMaranganti/agent-proof.git
cd agent-proof
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

When active, your shell prompt should begin with `(.venv)`. Leave the environment with `deactivate`.

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
