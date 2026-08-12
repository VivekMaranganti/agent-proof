"""Turns a completed run into a scored, storable outcome.

judges.contracts holds the actual deterministic contract logic (task-agnostic: task,
tool calls, final state in; ContractScore out). This module is the wiring the "worker
result path" acceptance bullet calls for: pull the tool calls a run actually made out
of its trace, score them against the task contract, and shape a TaskExecutionResult
the store can persist.
"""

from __future__ import annotations

from app.schemas import ExecutionStatus, TaskExecutionResult
from app.trace import ToolCallPayload
from benchmark.schema import BenchmarkTask
from judges.contracts import ContractScore, ToolCall, score_actions
from runner.runner import RunnerResult

_NO_FINAL_ANSWER = "(agent did not produce a final answer)"


def score_run(task: BenchmarkTask, result: RunnerResult) -> tuple[TaskExecutionResult, ContractScore]:
    tool_calls = tuple(
        ToolCall(service=step.payload.service, operation=step.payload.operation, arguments=step.payload.arguments)
        for step in result.trace
        if isinstance(step.payload, ToolCallPayload)
    )
    contract_score = score_actions(task, tool_calls, result.final_state)

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
    )
    return execution_result, contract_score
