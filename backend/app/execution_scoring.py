"""Shapes a scored run into the platform's TaskExecutionResult contract.

judges.contracts.score_run does the actual contract checking (task, trace, final
state in; ContractScore out). This is the remaining piece of the "wire into the
worker result path" work: turn that score plus the run's timing/token usage into
the TaskExecutionResult store.record_result expects.
"""

from __future__ import annotations

from app.schemas import ExecutionStatus, TaskExecutionResult
from benchmark.schema import BenchmarkTask
from judges.contracts import ContractScore, score_run
from runner.runner import RunnerResult

_NO_FINAL_ANSWER = "(agent did not produce a final answer)"


def score_execution(task: BenchmarkTask, result: RunnerResult) -> tuple[TaskExecutionResult, ContractScore]:
    contract_score = score_run(task, result)

    if result.max_steps_exceeded:
        status, passed = ExecutionStatus.ERRORED, False
    elif contract_score.passed:
        status, passed = ExecutionStatus.PASSED, True
    else:
        status, passed = ExecutionStatus.FAILED, False

    execution_result = TaskExecutionResult(
        status=status,
        passed=passed,
        final_output=result.final_output or _NO_FINAL_ANSWER,
        latency_ms=result.latency_ms,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        estimated_cost_usd=0.0,
        missing_expected_actions=contract_score.missing_expected_actions,
        forbidden_actions_seen=contract_score.forbidden_actions_seen,
        final_state_mismatches=contract_score.final_state_mismatches,
    )
    return execution_result, contract_score
