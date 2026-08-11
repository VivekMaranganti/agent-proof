"""Runs one agent version against one seeded benchmark task, producing a complete trace.

Deterministic seeding comes from the task itself: initial_state is a plain dict the
tool environment is rebuilt from on every run, so replaying the same version against
the same task always starts from identical state.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from app.schemas import AgentVersion
from app.trace import ErrorPayload, FinalAnswerPayload, ModelRequestPayload, ModelResponsePayload, RetryPayload, Trace
from benchmark.schema import BenchmarkTask
from runner.model_client import ModelClient, ModelReply, TransientModelError
from runner.tool_proxy import TracedToolProxy
from tool_environment import SupportToolEnvironment

DEFAULT_MAX_STEPS = 20
DEFAULT_MAX_MODEL_RETRIES = 2


@dataclass(frozen=True)
class RunnerResult:
    execution_id: UUID
    trace: Trace
    final_output: str | None
    latency_ms: int
    input_tokens: int
    output_tokens: int
    final_state: dict[str, Any]
    max_steps_exceeded: bool


async def run_task(
    version: AgentVersion,
    task: BenchmarkTask,
    model_client: ModelClient,
    *,
    execution_id: UUID | None = None,
    max_steps: int = DEFAULT_MAX_STEPS,
    max_model_retries: int = DEFAULT_MAX_MODEL_RETRIES,
) -> RunnerResult:
    execution_id = execution_id or uuid4()
    trace = Trace(execution_id=execution_id)
    environment = SupportToolEnvironment(task.initial_state)
    proxy = TracedToolProxy(environment, trace)

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": version.system_prompt},
        {"role": "user", "content": task.input},
    ]

    started_at = time.perf_counter()
    input_tokens = 0
    output_tokens = 0
    final_output: str | None = None
    max_steps_exceeded = False

    for _ in range(max_steps):
        request_step = trace.append(ModelRequestPayload(messages=list(messages), model=version.model))
        reply = await _complete_with_retries(
            model_client, trace, request_step.id, messages, version, max_model_retries
        )
        input_tokens += reply.input_tokens
        output_tokens += reply.output_tokens
        trace.append(
            ModelResponsePayload(
                content=reply.content,
                tool_calls=[vars(call) for call in reply.tool_calls],
                finish_reason=reply.finish_reason,
                input_tokens=reply.input_tokens,
                output_tokens=reply.output_tokens,
            ),
            parent_step_id=request_step.id,
        )

        if not reply.tool_calls:
            final_output = reply.content or ""
            trace.append(FinalAnswerPayload(content=final_output))
            break

        messages.append({"role": "assistant", "tool_calls": [vars(call) for call in reply.tool_calls]})
        for call in reply.tool_calls:
            result_step = proxy.invoke(call.call_id, call.service, call.operation, call.arguments)
            messages.append(
                {
                    "role": "tool",
                    "call_id": call.call_id,
                    "content": result_step.payload.model_dump(mode="json"),
                }
            )
    else:
        max_steps_exceeded = True
        trace.append(
            ErrorPayload(error_type="MaxStepsExceeded", message=f"exceeded {max_steps} steps without a final answer")
        )

    return RunnerResult(
        execution_id=execution_id,
        trace=trace,
        final_output=final_output,
        latency_ms=int((time.perf_counter() - started_at) * 1000),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        final_state=environment.snapshot(),
        max_steps_exceeded=max_steps_exceeded,
    )


async def _complete_with_retries(
    model_client: ModelClient,
    trace: Trace,
    parent_step_id: UUID,
    messages: list[dict[str, Any]],
    version: AgentVersion,
    max_retries: int,
) -> ModelReply:
    attempt = 1
    while True:
        try:
            return await model_client.complete(messages=messages, model=version.model, params=version.config)
        except TransientModelError as error:
            if attempt > max_retries:
                trace.append(
                    ErrorPayload(error_type="ModelError", message=str(error)), parent_step_id=parent_step_id
                )
                raise
            trace.append(RetryPayload(attempt=attempt, reason=str(error)), parent_step_id=parent_step_id)
            attempt += 1
