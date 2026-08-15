"""PostgreSQL-backed implementation of the Store protocol."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import session_factory as default_session_factory
from app.models import (
    AgentVersionModel,
    EvaluationRunModel,
    JudgeVerdictModel,
    TaskExecutionModel,
    TraceEventModel,
)
from app.redaction import redact_payload
from app.schemas import (
    AgentVersion,
    AgentVersionCreate,
    EvaluationRun,
    EvaluationRunCreate,
    ExecutionStatus,
    JudgeVerdict,
    JudgeVerdictCreate,
    TaskExecution,
    TaskExecutionCreate,
    TaskExecutionResult,
    TraceEvent,
    TraceEventCreate,
)
from app.store import utc_now
from app.versioning import compute_agent_version_content_hash


class PostgresStore:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession] | None = None) -> None:
        self._session_factory = session_factory or default_session_factory

    async def create_agent_version(self, payload: AgentVersionCreate) -> AgentVersion:
        content_hash = compute_agent_version_content_hash(
            payload.model, payload.system_prompt, payload.tool_schema_hash, payload.config
        )
        async with self._session_factory() as session:
            existing = await session.execute(
                select(AgentVersionModel).where(AgentVersionModel.content_hash == content_hash)
            )
            existing_row = existing.scalar_one_or_none()
            if existing_row is not None:
                return AgentVersion.model_validate(existing_row, from_attributes=True)

            row = AgentVersionModel(**payload.model_dump(), content_hash=content_hash, created_at=utc_now())
            session.add(row)
            try:
                await session.commit()
            except IntegrityError:
                # a concurrent request inserted the same content_hash between our check and this insert
                await session.rollback()
                result = await session.execute(
                    select(AgentVersionModel).where(AgentVersionModel.content_hash == content_hash)
                )
                return AgentVersion.model_validate(result.scalar_one(), from_attributes=True)
            return AgentVersion.model_validate(row, from_attributes=True)

    async def get_agent_version(self, agent_version_id: UUID) -> AgentVersion:
        async with self._session_factory() as session:
            row = await session.get(AgentVersionModel, agent_version_id)
            if row is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="agent version not found")
            return AgentVersion.model_validate(row, from_attributes=True)

    async def create_run(self, payload: EvaluationRunCreate) -> EvaluationRun:
        async with self._session_factory() as session:
            agent_version = await session.get(AgentVersionModel, payload.agent_version_id)
            if agent_version is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="agent version not found")
            row = EvaluationRunModel(**payload.model_dump(), created_at=utc_now())
            session.add(row)
            await session.commit()
            return EvaluationRun.model_validate(row, from_attributes=True)

    async def create_execution(self, run_id: UUID, payload: TaskExecutionCreate) -> TaskExecution:
        async with self._session_factory() as session:
            run = await session.get(EvaluationRunModel, run_id)
            if run is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="evaluation run not found")
            row = TaskExecutionModel(**payload.model_dump(), run_id=run_id, created_at=utc_now())
            session.add(row)
            await session.commit()
            return TaskExecution.model_validate(row, from_attributes=True)

    async def record_result(self, execution_id: UUID, payload: TaskExecutionResult) -> TaskExecution:
        async with self._session_factory() as session:
            row = await session.get(TaskExecutionModel, execution_id)
            if row is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task execution not found")
            if row.status in {ExecutionStatus.PASSED, ExecutionStatus.FAILED, ExecutionStatus.ERRORED}:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="execution already finalized")
            for field, value in payload.model_dump().items():
                setattr(row, field, value)
            row.finished_at = utc_now()
            await session.commit()
            return TaskExecution.model_validate(row, from_attributes=True)

    async def append_trace_event(self, execution_id: UUID, payload: TraceEventCreate) -> TraceEvent:
        async with self._session_factory() as session:
            execution = await session.get(TaskExecutionModel, execution_id)
            if execution is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task execution not found")
            redacted = payload.model_copy(update={"payload": redact_payload(payload.payload)})
            row = TraceEventModel(**redacted.model_dump(), execution_id=execution_id, created_at=utc_now())
            session.add(row)
            try:
                await session.commit()
            except IntegrityError as error:
                await session.rollback()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail="duplicate trace sequence number"
                ) from error
            return TraceEvent.model_validate(row, from_attributes=True)

    async def get_execution(self, execution_id: UUID) -> TaskExecution:
        async with self._session_factory() as session:
            row = await session.get(TaskExecutionModel, execution_id)
            if row is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task execution not found")
            return TaskExecution.model_validate(row, from_attributes=True)

    async def get_run_executions(self, run_id: UUID) -> list[TaskExecution]:
        async with self._session_factory() as session:
            run = await session.get(EvaluationRunModel, run_id)
            if run is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="evaluation run not found")
            result = await session.execute(select(TaskExecutionModel).where(TaskExecutionModel.run_id == run_id))
            return [TaskExecution.model_validate(row, from_attributes=True) for row in result.scalars()]

    async def get_trace(self, execution_id: UUID) -> list[TraceEvent]:
        async with self._session_factory() as session:
            execution = await session.get(TaskExecutionModel, execution_id)
            if execution is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task execution not found")
            result = await session.execute(
                select(TraceEventModel)
                .where(TraceEventModel.execution_id == execution_id)
                .order_by(TraceEventModel.sequence_no)
            )
            return [TraceEvent.model_validate(row, from_attributes=True) for row in result.scalars()]

    async def append_judge_verdict(self, execution_id: UUID, payload: JudgeVerdictCreate) -> JudgeVerdict:
        async with self._session_factory() as session:
            execution = await session.get(TaskExecutionModel, execution_id)
            if execution is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task execution not found")
            row = JudgeVerdictModel(**payload.model_dump(), execution_id=execution_id, created_at=utc_now())
            session.add(row)
            await session.commit()
            return JudgeVerdict.model_validate(row, from_attributes=True)

    async def get_judge_verdicts(self, execution_id: UUID) -> list[JudgeVerdict]:
        async with self._session_factory() as session:
            execution = await session.get(TaskExecutionModel, execution_id)
            if execution is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task execution not found")
            result = await session.execute(
                select(JudgeVerdictModel).where(JudgeVerdictModel.execution_id == execution_id)
            )
            return [JudgeVerdict.model_validate(row, from_attributes=True) for row in result.scalars()]
