"""SQLAlchemy models backing the platform's persisted entities.

Mirrors the Pydantic contracts in schemas.py field for field. Comparisons and
attributions are computed on demand by comparison.py and are not persisted here.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.schemas import EventType, ExecutionStatus, RunStatus


class Base(DeclarativeBase):
    type_annotation_map = {datetime: DateTime(timezone=True)}


def _enum_column(enum_cls: type) -> Enum:
    return Enum(enum_cls, values_callable=lambda cls: [member.value for member in cls])


class AgentVersionModel(Base):
    __tablename__ = "agent_versions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(nullable=False)
    git_sha: Mapped[str] = mapped_column(nullable=False)
    model: Mapped[str] = mapped_column(nullable=False)
    system_prompt: Mapped[str] = mapped_column(nullable=False)
    tool_schema_hash: Mapped[str] = mapped_column(nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(nullable=False)


class EvaluationRunModel(Base):
    __tablename__ = "evaluation_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    agent_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_versions.id"), nullable=False
    )
    suite_id: Mapped[str] = mapped_column(nullable=False)
    suite_version: Mapped[str] = mapped_column(nullable=False)
    suite_manifest_hash: Mapped[str] = mapped_column(nullable=False)
    seed: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[RunStatus] = mapped_column(
        _enum_column(RunStatus), nullable=False, default=RunStatus.QUEUED
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)

    __table_args__ = (Index("ix_evaluation_runs_agent_version_id", "agent_version_id"),)


class TaskExecutionModel(Base):
    __tablename__ = "task_executions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("evaluation_runs.id"), nullable=False)
    task_id: Mapped[str] = mapped_column(nullable=False)
    task_seed: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[ExecutionStatus] = mapped_column(
        _enum_column(ExecutionStatus), nullable=False, default=ExecutionStatus.PENDING
    )
    passed: Mapped[bool | None] = mapped_column(nullable=True)
    final_output: Mapped[str | None] = mapped_column(nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(nullable=True)
    estimated_cost_usd: Mapped[float | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)

    __table_args__ = (
        Index("ix_task_executions_run_id", "run_id"),
        Index("ix_task_executions_run_id_task_id", "run_id", "task_id"),
    )


class TraceEventModel(Base):
    __tablename__ = "trace_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    execution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("task_executions.id"), nullable=False
    )
    sequence_no: Mapped[int] = mapped_column(nullable=False)
    event_type: Mapped[EventType] = mapped_column(_enum_column(EventType), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    parent_event_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False)

    __table_args__ = (
        Index("ix_trace_events_execution_id", "execution_id"),
        UniqueConstraint("execution_id", "sequence_no", name="uq_trace_events_execution_sequence"),
    )
