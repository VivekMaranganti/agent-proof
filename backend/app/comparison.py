"""Paired run comparison and evidence-backed first-divergence attribution."""

from __future__ import annotations

from collections.abc import Iterable

from fastapi import HTTPException, status

from app.schemas import (
    EventType,
    PairedTaskComparison,
    RegressionDisposition,
    RunComparison,
    TaskExecution,
    TraceAttribution,
    TraceDivergenceType,
    TraceEvent,
)
from app.store import PlatformStore


def compare_runs(store: PlatformStore, baseline_run_id, candidate_run_id) -> RunComparison:
    baseline = _by_task(store.get_run_executions(baseline_run_id))
    candidate = _by_task(store.get_run_executions(candidate_run_id))
    shared_task_ids = sorted(set(baseline).intersection(candidate))
    if not shared_task_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="runs have no shared task ids to compare",
        )

    results: list[PairedTaskComparison] = []
    for task_id in shared_task_ids:
        left, right = baseline[task_id], candidate[task_id]
        disposition = _disposition(left.passed, right.passed)
        attribution = None
        if disposition == RegressionDisposition.REGRESSION:
            attribution = _first_divergence(task_id, left, right, store.get_trace(left.id), store.get_trace(right.id))
        results.append(
            PairedTaskComparison(
                task_id=task_id,
                disposition=disposition,
                baseline_execution_id=left.id,
                candidate_execution_id=right.id,
                baseline_passed=left.passed,
                candidate_passed=right.passed,
                latency_delta_ms=_delta(right.latency_ms, left.latency_ms),
                cost_delta_usd=_cost_delta(right.estimated_cost_usd, left.estimated_cost_usd),
                attribution=attribution,
            )
        )
    return RunComparison(
        baseline_run_id=baseline_run_id,
        candidate_run_id=candidate_run_id,
        compared_tasks=len(results),
        regressions=sum(item.disposition == RegressionDisposition.REGRESSION for item in results),
        improvements=sum(item.disposition == RegressionDisposition.IMPROVEMENT for item in results),
        results=results,
    )


def _by_task(executions: Iterable[TaskExecution]) -> dict[str, TaskExecution]:
    result: dict[str, TaskExecution] = {}
    for execution in executions:
        if execution.task_id in result:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"run contains multiple executions for task {execution.task_id}",
            )
        result[execution.task_id] = execution
    return result


def _disposition(baseline: bool | None, candidate: bool | None) -> RegressionDisposition:
    if baseline is True and candidate is False:
        return RegressionDisposition.REGRESSION
    if baseline is False and candidate is True:
        return RegressionDisposition.IMPROVEMENT
    if baseline is True and candidate is True:
        return RegressionDisposition.STABLE_PASS
    if baseline is False and candidate is False:
        return RegressionDisposition.STABLE_FAILURE
    return RegressionDisposition.INDETERMINATE


def _delta(candidate: int | None, baseline: int | None) -> int | None:
    if candidate is None or baseline is None:
        return None
    return candidate - baseline


def _cost_delta(candidate: float | None, baseline: float | None) -> float | None:
    if candidate is None or baseline is None:
        return None
    return round(candidate - baseline, 8)


def _first_divergence(
    task_id: str,
    baseline: TaskExecution,
    candidate: TaskExecution,
    baseline_events: list[TraceEvent],
    candidate_events: list[TraceEvent],
) -> TraceAttribution | None:
    for left, right in zip(baseline_events, candidate_events, strict=False):
        divergence = _event_divergence(left, right)
        if divergence:
            return TraceAttribution(
                task_id=task_id,
                baseline_execution_id=baseline.id,
                candidate_execution_id=candidate.id,
                baseline_event_id=left.id,
                candidate_event_id=right.id,
                divergence_type=divergence,
                evidence={"baseline": left.payload, "candidate": right.payload, "sequence_no": left.sequence_no},
            )
    if len(baseline_events) != len(candidate_events):
        missing_from_candidate = len(candidate_events) < len(baseline_events)
        return TraceAttribution(
            task_id=task_id,
            baseline_execution_id=baseline.id,
            candidate_execution_id=candidate.id,
            baseline_event_id=baseline_events[len(candidate_events)].id if missing_from_candidate else None,
            candidate_event_id=candidate_events[len(baseline_events)].id if not missing_from_candidate else None,
            divergence_type=TraceDivergenceType.PREMATURE_TERMINATION,
            evidence={"baseline_event_count": len(baseline_events), "candidate_event_count": len(candidate_events)},
        )
    return None


def _event_divergence(left: TraceEvent, right: TraceEvent) -> TraceDivergenceType | None:
    if left.event_type != right.event_type:
        return TraceDivergenceType.WRONG_TOOL
    if left.event_type == EventType.TOOL_CALL:
        if left.payload.get("tool_name") != right.payload.get("tool_name"):
            return TraceDivergenceType.WRONG_TOOL
        if left.payload.get("arguments") != right.payload.get("arguments"):
            return TraceDivergenceType.INVALID_TOOL_ARGUMENT
    if right.event_type == EventType.ERROR:
        return TraceDivergenceType.TOOL_ERROR
    if left.event_type == EventType.FINAL_ANSWER and left.payload.get("content") != right.payload.get("content"):
        return TraceDivergenceType.FINAL_ANSWER_MISMATCH
    return None
