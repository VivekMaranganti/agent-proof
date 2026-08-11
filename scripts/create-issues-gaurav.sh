#!/usr/bin/env bash
#
# Create AgentProof roadmap issues (Gaurav's ownership areas) and assign
# them to you.
#
# Prereqs:
#   - GitHub CLI installed: https://cli.github.com
#   - Authenticated: `gh auth login`  (as the account that owns the repo)
#
# Usage:
#   cd agent-proof
#   ./scripts/create-issues-gaurav.sh            # create + self-assign all issues
#   DRY_RUN=1 ./scripts/create-issues-gaurav.sh   # print what would be created
#
set -euo pipefail

REPO="VivekMaranganti/agent-proof"
ASSIGNEE="@me"   # resolves to the authenticated user

# Ensure labels exist (ignore errors if they already do).
ensure_label() { gh label create "$1" --repo "$REPO" --color "$2" >/dev/null 2>&1 || true; }
if [[ "${DRY_RUN:-0}" != "1" ]]; then
  ensure_label "phase-1"        "1f77b4"
  ensure_label "phase-2"        "2ca02c"
  ensure_label "phase-4"        "ff7f0e"
  ensure_label "phase-5"        "17becf"
  ensure_label "phase-6"        "8c564b"
  ensure_label "area:tool-env"  "c5def5"
  ensure_label "area:benchmark" "0e8a16"
  ensure_label "area:scoring"   "b60205"
  ensure_label "area:judging"   "9467bd"
  ensure_label "area:gold-data" "d4c5f9"
  ensure_label "area:dashboard" "fbca04"
  ensure_label "area:adversarial" "e99695"
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

create "Harden the support-tool environment against duplicate and cross-customer refunds" \
  "phase-1,area:tool-env" \
  "$(cat <<'BODY'
RefundService.create_refund currently only checks policy eligibility and amount; duplicate-refund and identity-mismatch prevention exist as benchmark contracts but aren't enforced by the service itself.

- [ ] Reject a second create_refund for an order that already has one
- [ ] Reject a refund where the order's customer_id doesn't match the requester
- [ ] Raise PolicyViolationError with a clear reason for both cases
- [ ] Update tests/test_tool_environment.py to cover both paths directly

Acceptance: the environment itself refuses the invalid action, independent of contract scoring.
BODY
)"

create "Expand the support-tool environment beyond refunds" \
  "phase-1,area:tool-env,area:benchmark" \
  "$(cat <<'BODY'
The seed suite is refund-only. Add order-status actions (cancel, replace) and ticket escalation so later benchmark tasks aren't all one decision tree.

- [ ] OrderService.cancel_order / replace_item with policy checks
- [ ] TicketService escalation status transition
- [ ] Update SupportState/SupportToolEnvironment snapshot to cover new fields
- [ ] At least one new seed task exercising each new action

Acceptance: new services pass the same deterministic-state pattern as existing ones; seed task(s) added and green.
BODY
)"

create "Benchmark suite serialization and a mutation registry" \
  "phase-2,area:benchmark" \
  "$(cat <<'BODY'
Task and mutation definitions currently only exist as Python literals. Add JSON/YAML (de)serialization for reproducible suite snapshots, and a registry so mutation types can be looked up and run by name.

- [ ] BenchmarkTask/AdversarialVariant (de)serialize losslessly to JSON
- [ ] MUTATION_REGISTRY: dict[str, Callable] keyed by mutation_type
- [ ] A suite snapshot file format with a content hash for reproducibility
- [ ] Round-trip tests: serialize -> deserialize -> identical task

Acceptance: a benchmark suite (seed tasks + generated variants) can be frozen to a file and reloaded byte-identical.
BODY
)"

create "Wire deterministic contract scoring into the runner's result path" \
  "phase-2,area:scoring" \
  "$(cat <<'BODY'
Once Vivek's runner (runner/ package) lands, connect judges.contracts.score_actions so every run gets a deterministic score without manual wiring per task.

- [ ] Runner result includes tool-call sequence + final environment snapshot
- [ ] score_actions invoked automatically after each run
- [ ] Deterministic score persisted alongside the run

Acceptance: a run through the runner produces a ContractScore with no manual scoring step.

Depends on: Vivek's "Build agent runner with traced tool proxy"
BODY
)"

create "LLM judge scaffolding with explicit rubrics" \
  "phase-5,area:judging" \
  "$(cat <<'BODY'
judges/ currently has only deterministic contract scoring. Add the first LLM-judge module for cases deterministic checks can't cover well.

- [ ] judges/llm.py with a Judge protocol (rubric in, label + confidence + rationale out)
- [ ] Policy judge: did the agent apply refund policy correctly, in prose terms
- [ ] Response-quality judge: is the drafted customer reply appropriate and complete
- [ ] Rubrics stored as versioned, reviewable text (not embedded in code)

Acceptance: running a judge against a completed task returns a structured label, confidence, and rationale.
BODY
)"

create "Judge agreement / disagreement analysis" \
  "phase-5,area:judging" \
  "$(cat <<'BODY'
Per the README principle that judge disagreement should be surfaced, not hidden behind one opaque score.

- [ ] Run multiple judges over the same task and record all labels
- [ ] Compute simple agreement metrics (e.g. pairwise agreement rate)
- [ ] Flag tasks with judge disagreement above a threshold for review

Acceptance: a multi-judge run produces a report distinguishing consensus from disagreement, not just an average.
BODY
)"

create "Human-labeled gold dataset format and methodology" \
  "phase-5,area:judging,area:gold-data" \
  "$(cat <<'BODY'
Define how a small human-labeled set is collected and stored so judges can be calibrated against it.

- [ ] Gold-label schema (task id, human label, rationale, labeler, timestamp)
- [ ] Labeling guide documenting the rubric humans apply
- [ ] Judge-vs-gold agreement report using the same metric as the disagreement-analysis issue

Acceptance: a small seeded gold set exists and a judge can be scored against it end-to-end.
BODY
)"

create "Comparison page (baseline vs. candidate)" \
  "phase-4,area:dashboard" \
  "$(cat <<'BODY'
The first dashboard view: per-task and aggregate deltas between two agent versions.

- [ ] Task list with pass/fail/regressed status per version
- [ ] Aggregate summary (pass rate, latency, cost deltas)
- [ ] Consumes Vivek's comparison API endpoint

Acceptance: loading a comparison renders per-task and aggregate diffs from the live API.

Depends on: Vivek's "Paired baseline/candidate run comparison" API
BODY
)"

create "Task detail page" \
  "phase-4,area:dashboard" \
  "$(cat <<'BODY'
Drill-down from the comparison page into one task: input, contract, expected vs. actual final state, and the deterministic score breakdown.

- [ ] Renders ExpectedAction/ForbiddenAction contract alongside actual tool calls
- [ ] Renders final_state_mismatches from ContractScore in a readable diff
- [ ] Links out to trace replay for the same run

Acceptance: a failed task's detail page makes the failure reason legible without reading raw JSON.
BODY
)"

create "Trace replay view" \
  "phase-4,area:dashboard" \
  "$(cat <<'BODY'
Step-by-step playback of one run's ordered trace.

- [ ] Ordered step list (prompt, model response, tool call/result)
- [ ] Step-by-step navigation with stable deep-linkable IDs
- [ ] Highlights the first divergence step when viewing a paired regression

Acceptance: a regressed run can be replayed and the first divergence is visually highlighted.

Depends on: Vivek's "Trace replay API to back the dashboard"
BODY
)"

create "Judge results view" \
  "phase-4,area:dashboard,area:judging" \
  "$(cat <<'BODY'
Surface judge labels, confidence, rationale, and disagreement.

- [ ] Per-judge label/confidence/rationale display
- [ ] Disagreement indicator when judges split
- [ ] Link to the gold-label comparison where available

Acceptance: a task with split judge opinions is visually distinguishable from one with consensus.
BODY
)"

create "Additional adversarial mutation types" \
  "phase-6,area:adversarial" \
  "$(cat <<'BODY'
Extend benchmark/mutations.py beyond the current five mutation types (typo, distractor, conflicting-detail, missing-customer-identity, boundary-amount).

- [ ] Paraphrase mutation (reword the request without changing facts)
- [ ] Tool-result noise mutation (benign extra fields in a tool response)
- [ ] Multi-mutation composition (apply two mutation types to one task) with lineage preserved
- [ ] Validator coverage for each new type

Acceptance: new mutation types pass benchmark.validators.validate_variant and have determinism tests.
BODY
)"

echo "Done."
