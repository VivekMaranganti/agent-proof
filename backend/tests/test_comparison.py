"""Seeded regression fixtures for paired comparison and first-divergence attribution.

Each divergence-type test isolates exactly the trace shape _event_divergence needs to
classify correctly, including two cases that were previously misclassified: a step
where one side errored and the other didn't (was wrong_tool, should be tool_error),
and a step where both sides errored identically (was flagged as a divergence, should
be skipped so the engine keeps looking for the real one).
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.comparison import compare_runs
from app.schemas import AgentVersionCreate, EvaluationRunCreate, TaskExecutionCreate, TaskExecutionResult
from app.store import PlatformStore
from app.trace import ErrorPayload, FinalAnswerPayload, ToolCallPayload, ToolResultPayload, Trace


async def _version(store: PlatformStore, sha: str):
    #tool_schema_hash varies with sha so distinct shas produce genuinely distinct
    #content-hashed identities, not the same version twice
    return await store.create_agent_version(
        AgentVersionCreate(
            name=f"agent-{sha}",
            git_sha=sha,
            model="test-model",
            system_prompt="test",
            tool_schema_hash=sha,
        )
    )


async def _run(store: PlatformStore, version_id: UUID):
    return await store.create_run(
        EvaluationRunCreate(
            agent_version_id=version_id,
            suite_id="support-ops",
            suite_version="v1",
            suite_manifest_hash="manifest123",
            seed=7,
        )
    )


async def _seed_execution(
    store: PlatformStore,
    run_id: UUID,
    task_id: str,
    trace: Trace,
    *,
    passed: bool,
    latency_ms: int = 100,
    estimated_cost_usd: float = 0.001,
) -> UUID:
    execution = await store.create_execution(run_id, TaskExecutionCreate(task_id=task_id, task_seed=7))
    for event in trace.to_storage():
        await store.append_trace_event(execution.id, event)
    await store.record_result(
        execution.id,
        TaskExecutionResult(
            status="passed" if passed else "failed",
            passed=passed,
            final_output="ok" if passed else "not ok",
            latency_ms=latency_ms,
            input_tokens=10,
            output_tokens=5,
            estimated_cost_usd=estimated_cost_usd,
        ),
    )
    return execution.id


async def _regression(store: PlatformStore, task_id: str, baseline: Trace, candidate: Trace):
    baseline_version = await _version(store, "1111111")
    candidate_version = await _version(store, "2222222")
    baseline_run = await _run(store, baseline_version.id)
    candidate_run = await _run(store, candidate_version.id)
    await _seed_execution(store, baseline_run.id, task_id, baseline, passed=True)
    await _seed_execution(store, candidate_run.id, task_id, candidate, passed=False)
    comparison = await compare_runs(store, baseline_run.id, candidate_run.id)
    assert comparison.regressions == 1
    return comparison.results[0]


async def test_tool_error_where_baseline_succeeded_is_attributed_as_tool_error() -> None:
    baseline = Trace(execution_id=uuid4())
    call_step = baseline.append(ToolCallPayload(call_id="c1", service="order", operation="get_order", arguments={"order_id": "o-1"}))
    baseline.append(ToolResultPayload(call_id="c1", result={"order_id": "o-1"}), parent_step_id=call_step.id)

    candidate = Trace(execution_id=uuid4())
    candidate_call = candidate.append(ToolCallPayload(call_id="c1", service="order", operation="get_order", arguments={"order_id": "o-1"}))
    candidate.append(ErrorPayload(error_type="NotFoundError", message="order not found"), parent_step_id=candidate_call.id)

    result = await _regression(PlatformStore(), "refund-001", baseline, candidate)

    assert result.attribution.divergence_type == "tool_error"


async def test_identical_error_step_is_skipped_and_the_real_divergence_is_found_later() -> None:
    baseline = Trace(execution_id=uuid4())
    baseline_call = baseline.append(ToolCallPayload(call_id="c1", service="order", operation="get_order", arguments={"order_id": "o-1"}))
    baseline.append(ErrorPayload(error_type="NotFoundError", message="order not found"), parent_step_id=baseline_call.id)
    baseline.append(ToolCallPayload(call_id="c2", service="customer", operation="get_customer", arguments={"customer_id": "c-1"}))

    candidate = Trace(execution_id=uuid4())
    candidate_call = candidate.append(ToolCallPayload(call_id="c1", service="order", operation="get_order", arguments={"order_id": "o-1"}))
    candidate.append(ErrorPayload(error_type="NotFoundError", message="order not found"), parent_step_id=candidate_call.id)
    candidate.append(ToolCallPayload(call_id="c2", service="ticket", operation="update_ticket", arguments={"ticket_id": "t-1"}))

    result = await _regression(PlatformStore(), "refund-002", baseline, candidate)

    assert result.attribution.divergence_type == "wrong_tool"
    assert result.attribution.evidence["sequence_no"] == 2


async def test_invalid_tool_argument_regression() -> None:
    baseline = Trace(execution_id=uuid4())
    baseline.append(
        ToolCallPayload(call_id="c1", service="refund", operation="create_refund", arguments={"order_id": "o-1", "amount_cents": 100})
    )
    candidate = Trace(execution_id=uuid4())
    candidate.append(
        ToolCallPayload(call_id="c1", service="refund", operation="create_refund", arguments={"order_id": "o-1", "amount_cents": 999})
    )

    result = await _regression(PlatformStore(), "refund-003", baseline, candidate)

    assert result.attribution.divergence_type == "invalid_tool_argument"


async def test_final_answer_mismatch_regression() -> None:
    baseline = Trace(execution_id=uuid4())
    baseline.append(FinalAnswerPayload(content="Refund issued."))
    candidate = Trace(execution_id=uuid4())
    candidate.append(FinalAnswerPayload(content="Unable to process your request."))

    result = await _regression(PlatformStore(), "refund-004", baseline, candidate)

    assert result.attribution.divergence_type == "final_answer_mismatch"


async def test_premature_termination_regression() -> None:
    baseline = Trace(execution_id=uuid4())
    call_step = baseline.append(ToolCallPayload(call_id="c1", service="order", operation="get_order", arguments={"order_id": "o-1"}))
    baseline.append(ToolResultPayload(call_id="c1", result={"order_id": "o-1"}), parent_step_id=call_step.id)
    baseline.append(FinalAnswerPayload(content="done"))

    candidate = Trace(execution_id=uuid4())
    candidate_call = candidate.append(ToolCallPayload(call_id="c1", service="order", operation="get_order", arguments={"order_id": "o-1"}))
    candidate.append(ToolResultPayload(call_id="c1", result={"order_id": "o-1"}), parent_step_id=candidate_call.id)

    result = await _regression(PlatformStore(), "refund-005", baseline, candidate)

    assert result.attribution.divergence_type == "premature_termination"
    assert result.attribution.candidate_event_id is None


async def test_aggregate_summary_and_per_task_deltas_across_multiple_tasks() -> None:
    store = PlatformStore()
    baseline_version = await _version(store, "1111111")
    candidate_version = await _version(store, "2222222")
    baseline_run = await _run(store, baseline_version.id)
    candidate_run = await _run(store, candidate_version.id)

    stable_baseline = Trace(execution_id=uuid4())
    stable_baseline.append(FinalAnswerPayload(content="ok"))
    await _seed_execution(store, baseline_run.id, "task-stable", stable_baseline, passed=True, latency_ms=100, estimated_cost_usd=0.001)
    stable_candidate = Trace(execution_id=uuid4())
    stable_candidate.append(FinalAnswerPayload(content="ok"))
    await _seed_execution(store, candidate_run.id, "task-stable", stable_candidate, passed=True, latency_ms=150, estimated_cost_usd=0.002)

    regressed_baseline = Trace(execution_id=uuid4())
    regressed_baseline.append(FinalAnswerPayload(content="resolved"))
    await _seed_execution(store, baseline_run.id, "task-regressed", regressed_baseline, passed=True)
    regressed_candidate = Trace(execution_id=uuid4())
    regressed_candidate.append(FinalAnswerPayload(content="failed"))
    await _seed_execution(store, candidate_run.id, "task-regressed", regressed_candidate, passed=False)

    comparison = await compare_runs(store, baseline_run.id, candidate_run.id)

    assert comparison.compared_tasks == 2
    assert comparison.regressions == 1
    assert comparison.improvements == 0

    by_task = {result.task_id: result for result in comparison.results}
    assert by_task["task-stable"].disposition == "stable_pass"
    assert by_task["task-stable"].latency_delta_ms == 50
    assert round(by_task["task-stable"].cost_delta_usd, 3) == 0.001
    assert by_task["task-regressed"].disposition == "regression"
