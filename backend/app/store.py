"""In-memory development repository.

The API is intentionally coded against a small repository boundary so the forthcoming
PostgreSQL adapter can replace this implementation without changing API contracts.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from fastapi import HTTPException, status

from app.schemas import (
    AgentVersion,
    AgentVersionCreate,
    EvaluationRun,
    EvaluationRunCreate,
    ExecutionStatus,
    TaskExecution,
    TaskExecutionCreate,
    TaskExecutionResult,
    TraceEvent,
    TraceEventCreate,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


class Store(Protocol):
    async def create_agent_version(self, payload: AgentVersionCreate) -> AgentVersion: ...

    async def get_agent_version(self, agent_version_id: UUID) -> AgentVersion: ...

    async def create_run(self, payload: EvaluationRunCreate) -> EvaluationRun: ...

    async def create_execution(self, run_id: UUID, payload: TaskExecutionCreate) -> TaskExecution: ...

    async def record_result(self, execution_id: UUID, payload: TaskExecutionResult) -> TaskExecution: ...

    async def append_trace_event(self, execution_id: UUID, payload: TraceEventCreate) -> TraceEvent: ...

    async def get_execution(self, execution_id: UUID) -> TaskExecution: ...

    async def get_run_executions(self, run_id: UUID) -> list[TaskExecution]: ...

    async def get_trace(self, execution_id: UUID) -> list[TraceEvent]: ...


class PlatformStore:
    def __init__(self) -> None:
        self.agent_versions: dict[UUID, AgentVersion] = {}
        self.runs: dict[UUID, EvaluationRun] = {}
        self.executions: dict[UUID, TaskExecution] = {}
        self.events_by_execution: dict[UUID, list[TraceEvent]] = defaultdict(list)

    async def create_agent_version(self, payload: AgentVersionCreate) -> AgentVersion:
        version = AgentVersion(**payload.model_dump(), created_at=utc_now())
        self.agent_versions[version.id] = version
        return version

    async def get_agent_version(self, agent_version_id: UUID) -> AgentVersion:
        try:
            return self.agent_versions[agent_version_id]
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="agent version not found") from error

    async def create_run(self, payload: EvaluationRunCreate) -> EvaluationRun:
        if payload.agent_version_id not in self.agent_versions:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="agent version not found")
        run = EvaluationRun(**payload.model_dump(), created_at=utc_now())
        self.runs[run.id] = run
        return run

    async def create_execution(self, run_id: UUID, payload: TaskExecutionCreate) -> TaskExecution:
        if run_id not in self.runs:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="evaluation run not found")
        execution = TaskExecution(**payload.model_dump(), run_id=run_id, created_at=utc_now())
        self.executions[execution.id] = execution
        return execution

    async def record_result(self, execution_id: UUID, payload: TaskExecutionResult) -> TaskExecution:
        execution = await self.get_execution(execution_id)
        if execution.status in {ExecutionStatus.PASSED, ExecutionStatus.FAILED, ExecutionStatus.ERRORED}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="execution already finalized")
        updated = execution.model_copy(update={**payload.model_dump(), "finished_at": utc_now()})
        self.executions[execution_id] = updated
        return updated

    async def append_trace_event(self, execution_id: UUID, payload: TraceEventCreate) -> TraceEvent:
        await self.get_execution(execution_id)
        events = self.events_by_execution[execution_id]
        if any(event.sequence_no == payload.sequence_no for event in events):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="duplicate trace sequence number")
        event = TraceEvent(**payload.model_dump(), execution_id=execution_id, created_at=utc_now())
        events.append(event)
        events.sort(key=lambda item: item.sequence_no)
        return event

    async def get_execution(self, execution_id: UUID) -> TaskExecution:
        try:
            return self.executions[execution_id]
        except KeyError as error:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task execution not found") from error

    async def get_run_executions(self, run_id: UUID) -> list[TaskExecution]:
        if run_id not in self.runs:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="evaluation run not found")
        return [item for item in self.executions.values() if item.run_id == run_id]

    async def get_trace(self, execution_id: UUID) -> list[TraceEvent]:
        await self.get_execution(execution_id)
        return list(self.events_by_execution[execution_id])
