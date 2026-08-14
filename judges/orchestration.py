"""Judge selection and orchestration methodology.

Decides which registered judges apply to a completed execution and runs
them, producing verdicts a caller (a worker, an on-demand API handler, a
manual review script) can persist. This module owns *which judges run and
on what basis* — that's an evaluation-methodology call. It deliberately
does not decide *when* that happens in a pipeline; that's an infrastructure
call for whoever wires this in.

Methodology, and why:

- The policy judge always runs. There is always a tool-call sequence to
  assess, even an empty one (e.g. the agent never acted at all is itself
  a policy-relevant fact).
- The response-quality judge only runs when the execution produced a final
  response. Grading the quality of a reply that doesn't exist is
  meaningless, not merely uninformative -- it would force a confidence
  score and rationale onto a judge with nothing to look at.
- Judge evaluation is intentionally decoupled from deterministic contract
  scoring (judges.contracts.score_run). Deterministic scoring is cheap,
  local, and safe to run on every execution unconditionally. LLM judge
  calls are not: they cost money, add latency, and depend on a configured
  model backend. Bundling them into the same synchronous path as
  deterministic scoring would force every execution in every run to pay
  for N judge calls whether or not anyone asked for that. run_judges is an
  opt-in step a caller invokes separately, so a worker can choose to run
  it on every execution, on a sample, or only on demand from the UI --
  that cadence decision belongs to whoever owns the pipeline, not here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from benchmark.schema import BenchmarkTask
from judges.contracts import extract_tool_calls
from judges.llm import POLICY_JUDGE, RESPONSE_QUALITY_JUDGE, Judge, JudgeVerdict, ModelCaller

if TYPE_CHECKING:
    from runner.runner import RunnerResult


def select_judges(final_response: str | None) -> tuple[Judge, ...]:
    """Choose which judges apply to a completed execution's evidence."""

    if final_response:
        return (POLICY_JUDGE, RESPONSE_QUALITY_JUDGE)
    return (POLICY_JUDGE,)


def run_judges(
    task: BenchmarkTask, result: "RunnerResult", model_caller: ModelCaller
) -> tuple[JudgeVerdict, ...]:
    """Run the judges selected for this execution and return their verdicts.

    Mirrors judges.contracts.score_run's shape (task, RunnerResult in,
    verdicts out) so the two can sit side by side in a pipeline; unlike
    score_run this also takes a ModelCaller, since judge evaluation needs
    an actual model behind it.
    """

    tool_calls = extract_tool_calls(result.trace)
    judges = select_judges(result.final_output)
    return tuple(judge.evaluate(task, tool_calls, result.final_output, model_caller) for judge in judges)
