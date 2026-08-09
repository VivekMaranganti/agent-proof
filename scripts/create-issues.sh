#!/usr/bin/env bash
#
# Create AgentProof roadmap issues and assign them to you.
#
# Prereqs:
#   - GitHub CLI installed: https://cli.github.com
#   - Authenticated: `gh auth login`  (as the account that owns the repo)
#
# Usage:
#   cd agent-proof
#   ./scripts/create-issues.sh            # create + self-assign all issues
#   DRY_RUN=1 ./scripts/create-issues.sh  # print what would be created
#
set -euo pipefail

REPO="VivekMaranganti/agent-proof"
ASSIGNEE="@me"   # resolves to the authenticated user

# Ensure labels exist (ignore errors if they already do).
ensure_label() { gh label create "$1" --repo "$REPO" --color "$2" >/dev/null 2>&1 || true; }
if [[ "${DRY_RUN:-0}" != "1" ]]; then
  ensure_label "phase-1"          "1f77b4"
  ensure_label "phase-2"          "2ca02c"
  ensure_label "phase-3"          "9467bd"
  ensure_label "phase-4"          "ff7f0e"
  ensure_label "phase-6"          "8c564b"
  ensure_label "milestone"        "d62728"
  ensure_label "area:platform"    "0e8a16"
  ensure_label "area:db"          "5319e7"
  ensure_label "area:tracing"     "006b75"
  ensure_label "area:scoring"     "b60205"
  ensure_label "area:comparison"  "fbca04"
  ensure_label "area:attribution" "e99695"
  ensure_label "area:performance" "c2e0c6"
  ensure_label "area:testing"     "bfd4f2"
fi

create() {
  local title="$1" labels="$2" body="$3"
  if [[ "${DRY_RUN:-0}" == "1" ]]; then
    echo "would create: [$labels] $title"
    return
  fi
  gh issue create --repo "$REPO" --assignee "$ASSIGNEE" \
    --title "$title" --label "$labels" --body "$body"
}

create "Finalize core data contracts for versions, suites, runs, and traces" \
  "phase-1,area:platform" \
  "$(cat <<'BODY'
Lock the Pydantic/schema definitions everything depends on: agent version, benchmark suite/snapshot, run, and the ordered trace envelope.

- [ ] Define immutable AgentVersion and SuiteSnapshot identities (content-hashed)
- [ ] Define Run (baseline/candidate pairing, status, timing, cost)
- [ ] Define the trace envelope referenced by scoring and attribution
- [ ] Document invariants in docs/

Acceptance: schemas typed, validated, and imported by backend + runner without circular deps.
BODY
)"

create "Postgres schema + Alembic migrations for trace storage" \
  "phase-1,area:platform,area:db" \
  "$(cat <<'BODY'
Extend core tables to persist ordered trace steps efficiently and support trace queries.

- [ ] Tables for runs, trace steps, tool calls/results, judgements
- [ ] Indexes for per-run ordered retrieval and divergence queries
- [ ] Alembic migration + downgrade
- [ ] Redaction hook applied before persistence

Acceptance: `alembic upgrade head` builds the schema; round-trip test writes and reads an ordered trace.
BODY
)"

create "Build agent runner with traced tool proxy" \
  "phase-2,area:tracing" \
  "$(cat <<'BODY'
Create the runner/ package: execute a versioned agent against a seeded task, routing all tool calls through a proxy that records every step.

- [ ] Runner entrypoint takes (version, task) and returns a completed run
- [ ] Traced tool proxy wraps the tool environment
- [ ] Capture retries, latency, token usage, and errors
- [ ] Deterministic seeding of task state

Acceptance: running one version against one seeded task produces a complete, ordered trace.
BODY
)"

create "Define and implement the ordered trace model" \
  "phase-2,area:tracing" \
  "$(cat <<'BODY'
Concrete, serializable representation of prompts, model responses, tool calls, tool results, retries, latency, tokens, and errors as an ordered sequence.

- [ ] Step types and ordering guarantees
- [ ] Serialize/deserialize losslessly to the Postgres schema
- [ ] Stable step IDs for divergence comparison

Acceptance: trace serializes to storage and reconstructs identically; unit tests cover each step type.
BODY
)"

create "Implement Redis job queue and evaluation workers" \
  "phase-2,area:platform" \
  "$(cat <<'BODY'
Stand up the async execution path: enqueue runs, workers pull and execute via the runner, results persisted.

- [ ] Redis-backed queue (enqueue/claim/complete/fail)
- [ ] Worker process that runs the runner and writes results
- [ ] Retry/backoff and dead-letter handling
- [ ] docker-compose wiring for Redis + workers

Acceptance: a suite of tasks enqueued is executed by workers and lands in Postgres.
BODY
)"

create "Implement the deterministic scorer" \
  "phase-2,area:scoring" \
  "$(cat <<'BODY'
Score outcomes against executable task contracts (final response + actions taken) without LLM judgement.

- [ ] Evaluate contract checks over final state and trace actions
- [ ] Pass/fail with per-check detail
- [ ] Wire into the worker result path

Acceptance: deterministic pass/fail matches hand-labeled fixtures for the support tasks.
BODY
)"

create "Milestone: reproducible end-to-end run" \
  "phase-2,area:platform,milestone" \
  "$(cat <<'BODY'
Integrate runner + trace + queue + scorer into the first vertical slice: one agent version, one seeded support task, a complete trace, deterministic score.

- [ ] Single command runs the slice
- [ ] Result persisted and retrievable via API
- [ ] Documented in README dev setup

Acceptance: documented command produces a scored run reproducibly.
BODY
)"

create "Paired baseline/candidate run comparison" \
  "phase-3,area:comparison" \
  "$(cat <<'BODY'
Compare two versions on the same tasks by correctness, latency, cost, and failure mode.

- [ ] Comparison query joining paired runs
- [ ] Per-task deltas and aggregate summary
- [ ] API endpoint returning the comparison

Acceptance: comparing two versions returns per-task and aggregate diffs.
BODY
)"

create "First-divergence regression attribution engine" \
  "phase-3,area:attribution" \
  "$(cat <<'BODY'
For a pass->fail regression, locate the first material trace divergence (changed tool choice, invalid argument, tool failure, policy violation, early termination).

- [ ] Align paired traces by stable step IDs
- [ ] Classify the first material divergence
- [ ] Return evidence-backed attribution (not causal claim)

Acceptance: on seeded regression fixtures, the engine reports the correct first divergence.
BODY
)"

create "Trace query API endpoints" \
  "phase-3,area:platform" \
  "$(cat <<'BODY'
Expose ordered trace retrieval, comparison, and attribution results to the frontend.

- [ ] Endpoints for run trace, paired comparison, attribution
- [ ] Pagination / ordered retrieval
- [ ] Contract tests

Acceptance: endpoints documented and covered by API tests.
BODY
)"

create "Trace replay API to back the dashboard" \
  "phase-4,area:platform" \
  "$(cat <<'BODY'
Provide the backend surface the replay/comparison UI needs (Gaurav owns the UI).

- [ ] Replay-friendly ordered step feed
- [ ] Filters by task, correctness, failure mode
- [ ] Stable IDs for deep-linking

Acceptance: UI can render a full trace replay from these endpoints alone.
BODY
)"

create "Load-testing harness" \
  "phase-6,area:performance" \
  "$(cat <<'BODY'
Measure throughput and latency of the queue + workers under realistic suite sizes.

- [ ] Parameterized load scenarios
- [ ] Report throughput, latency percentiles, failure rate
- [ ] Baseline numbers checked into docs

Acceptance: reproducible load run emits a metrics report.
BODY
)"

create "Dockerized deployment + demo environment" \
  "phase-6,area:platform" \
  "$(cat <<'BODY'
Package the stack for a deployed demo.

- [ ] Production-oriented compose/deploy config
- [ ] Seeded demo data
- [ ] Documented bring-up

Acceptance: documented steps bring up a working demo instance.
BODY
)"

create "Systems / integration test suite + CI" \
  "phase-6,area:testing" \
  "$(cat <<'BODY'
End-to-end and seeded-regression tests wired into CI.

- [ ] Integration tests across runner, queue, scorer, API
- [ ] Seeded-regression tests for the attribution engine
- [ ] CI workflow running the suite

Acceptance: CI runs green on the integration + regression suites.
BODY
)"

echo "Done."
