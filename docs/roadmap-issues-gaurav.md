# AgentProof — Roadmap Issues (Gaurav)

PR-sized GitHub issues covering Gaurav Jha's ownership areas (deterministic
support-tool environment, benchmark schema & tasks, adversarial task
mutation, judge methodology, human-labeled gold dataset methodology, and
dashboard evaluation UX), grouped by the README roadmap phases. All are
intended to be assigned to Gaurav.

Companion script: `scripts/create-issues-gaurav.sh` creates and self-assigns
every issue below via the GitHub CLI.

---

## Phase 1 — Data contracts & foundation

### 1. Harden the support-tool environment against duplicate and cross-customer refunds
`RefundService.create_refund` currently only checks policy eligibility and
amount; duplicate-refund and identity-mismatch prevention exist as benchmark
contracts (`DUPLICATE_REFUND_PREVENTION`, `CUSTOMER_ORDER_MISMATCH`) but
aren't enforced by the service itself, so a direct service call can still
create an invalid refund.

- [ ] Reject a second `create_refund` for an order that already has one
- [ ] Reject a refund where the order's `customer_id` doesn't match the requester
- [ ] Raise `PolicyViolationError` with a clear reason for both cases
- [ ] Update `tests/test_tool_environment.py` to cover both paths directly

**Acceptance:** the environment itself refuses the invalid action, independent of contract scoring.
**Labels:** phase-1, area:tool-env

### 2. Expand the support-tool environment beyond refunds
The seed suite is refund-only. Add order-status actions (cancel, replace)
and ticket escalation so later benchmark tasks aren't all one decision tree.

- [ ] `OrderService.cancel_order` / `replace_item` with policy checks
- [ ] `TicketService` escalation status transition
- [ ] Update `SupportState`/`SupportToolEnvironment` snapshot to cover new fields
- [ ] At least one new seed task exercising each new action

**Acceptance:** new services pass the same deterministic-state pattern as existing ones; seed task(s) added and green.
**Labels:** phase-1, area:tool-env, area:benchmark

---

## Phase 2 — Deterministic scoring & reproducible suites

### 3. Benchmark suite serialization and a mutation registry
Task and mutation definitions currently only exist as Python literals.
Add JSON/YAML (de)serialization for reproducible suite snapshots, and a
registry so mutation types can be looked up and run by name instead of
importing each function individually.

- [ ] `BenchmarkTask`/`AdversarialVariant` (de)serialize losslessly to JSON
- [ ] `MUTATION_REGISTRY: dict[str, Callable]` keyed by `mutation_type`
- [ ] A suite snapshot file format with a content hash for reproducibility
- [ ] Round-trip tests: serialize → deserialize → identical task

**Acceptance:** a benchmark suite (seed tasks + generated variants) can be frozen to a file and reloaded byte-identical.
**Labels:** phase-2, area:benchmark

### 4. Wire deterministic contract scoring into the runner's result path
Once Vivek's runner (`runner/` package, roadmap item 3) lands, connect
`judges.contracts.score_actions` so every run gets a deterministic score
without manual wiring per task.

- [ ] Runner result includes tool-call sequence + final environment snapshot
- [ ] `score_actions` invoked automatically after each run
- [ ] Deterministic score persisted alongside the run

**Acceptance:** a run through the runner produces a `ContractScore` with no manual scoring step.
**Labels:** phase-2, area:scoring
**Depends on:** Vivek's "Build agent runner with traced tool proxy"

---

## Phase 5 — Judge methodology & gold-label dataset

### 5. LLM judge scaffolding with explicit rubrics
`judges/` currently has only deterministic contract scoring. Add the first
LLM-judge module for cases deterministic checks can't cover well.

- [ ] `judges/llm.py` with a `Judge` protocol (rubric in, label + confidence + rationale out)
- [ ] Policy judge: did the agent apply refund policy correctly, in prose terms
- [ ] Response-quality judge: is the drafted customer reply appropriate and complete
- [ ] Rubrics stored as versioned, reviewable text (not embedded in code)

**Acceptance:** running a judge against a completed task returns a structured label, confidence, and rationale.
**Labels:** phase-5, area:judging

### 6. Judge agreement / disagreement analysis
Per the README principle that judge disagreement should be surfaced, not
hidden behind one opaque score.

- [ ] Run multiple judges over the same task and record all labels
- [ ] Compute simple agreement metrics (e.g. pairwise agreement rate)
- [ ] Flag tasks with judge disagreement above a threshold for review

**Acceptance:** a multi-judge run produces a report distinguishing consensus from disagreement, not just an average.
**Labels:** phase-5, area:judging

### 7. Human-labeled gold dataset format and methodology
Define how a small human-labeled set is collected and stored so judges can
be calibrated against it.

- [ ] Gold-label schema (task id, human label, rationale, labeler, timestamp)
- [ ] Labeling guide documenting the rubric humans apply
- [ ] Judge-vs-gold agreement report using the same metric as issue 6

**Acceptance:** a small seeded gold set exists and a judge can be scored against it end-to-end.
**Labels:** phase-5, area:judging, area:gold-data

---

## Phase 4 — Dashboard evaluation UX

### 8. Comparison page (baseline vs. candidate)
The first dashboard view: per-task and aggregate deltas between two agent
versions.

- [ ] Task list with pass/fail/regressed status per version
- [ ] Aggregate summary (pass rate, latency, cost deltas)
- [ ] Consumes Vivek's comparison API endpoint

**Acceptance:** loading a comparison renders per-task and aggregate diffs from the live API.
**Labels:** phase-4, area:dashboard
**Depends on:** Vivek's "Paired baseline/candidate run comparison" API

### 9. Task detail page
Drill-down from the comparison page into one task: input, contract,
expected vs. actual final state, and the deterministic score breakdown.

- [ ] Renders `ExpectedAction`/`ForbiddenAction` contract alongside actual tool calls
- [ ] Renders `final_state_mismatches` from `ContractScore` in a readable diff
- [ ] Links out to trace replay for the same run

**Acceptance:** a failed task's detail page makes the failure reason legible without reading raw JSON.
**Labels:** phase-4, area:dashboard

### 10. Trace replay view
Step-by-step playback of one run's ordered trace.

- [ ] Ordered step list (prompt, model response, tool call/result)
- [ ] Step-by-step navigation with stable deep-linkable IDs
- [ ] Highlights the first divergence step when viewing a paired regression

**Acceptance:** a regressed run can be replayed and the first divergence is visually highlighted.
**Labels:** phase-4, area:dashboard
**Depends on:** Vivek's "Trace replay API to back the dashboard"

### 11. Judge results view
Surface judge labels, confidence, rationale, and disagreement from issues 5–6.

- [ ] Per-judge label/confidence/rationale display
- [ ] Disagreement indicator when judges split
- [ ] Link to the gold-label comparison where available

**Acceptance:** a task with split judge opinions is visually distinguishable from one with consensus.
**Labels:** phase-4, area:dashboard, area:judging

---

## Phase 6 — Adversarial coverage & docs

### 12. Additional adversarial mutation types
Extend `benchmark/mutations.py` beyond the current five mutation types
(typo, distractor, conflicting-detail, missing-customer-identity,
boundary-amount).

- [ ] Paraphrase mutation (reword the request without changing facts)
- [ ] Tool-result noise mutation (benign extra fields in a tool response)
- [ ] Multi-mutation composition (apply two mutation types to one task) with lineage preserved
- [ ] Validator coverage for each new type

**Acceptance:** new mutation types pass `benchmark.validators.validate_variant` and have determinism tests.
**Labels:** phase-6, area:adversarial
