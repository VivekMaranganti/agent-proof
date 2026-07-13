"""Stable contracts for AgentProof's platform layer.

This module intentionally contains no benchmark, judge, or tool-sandbox implementation.
Those are separate subsystems; the platform only stores their immutable references and
the execution evidence they emit.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EventType(StrEnum):
    MODEL_REQUEST = "model_request"
    MODEL_RESPONSE = "model_response"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    RETRY = "retry"
    ERROR = "error"
    FINAL_ANSWER = "final_answer"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ExecutionStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERRORED = "errored"


class RegressionDisposition(StrEnum):
    STABLE_PASS = "stable_pass"
    STABLE_FAILURE = "stable_failure"
    IMPROVEMENT = "improvement"
    REGRESSION = "regression"
    INDETERMINATE = "indeterminate"


class TraceDivergenceType(StrEnum):
    WRONG_TOOL = "wrong_tool"
    INVALID_TOOL_ARGUMENT = "invalid_tool_argument"
    TOOL_ERROR = "tool_error"
    PREMATURE_TERMINATION = "premature_termination"
    FINAL_ANSWER_MISMATCH = "final_answer_mismatch"


class AgentVersionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    git_sha: str = Field(min_length=7, max_length=64)
    model: str = Field(min_length=1, max_length=160)
    system_prompt: str = Field(min_length=1)
    tool_schema_hash: str = Field(min_length=7, max_length=128)
    config: dict[str, Any] = Field(default_factory=dict)


class AgentVersion(AgentVersionCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4)
    created_at: datetime


class EvaluationRunCreate(BaseModel):
    agent_version_id: UUID
    suite_id: str = Field(min_length=1, max_length=120)
    suite_version: str = Field(min_length=1, max_length=80)
    suite_manifest_hash: str = Field(min_length=7, max_length=128)
    seed: int = Field(ge=0)


class EvaluationRun(EvaluationRunCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4)
    status: RunStatus = RunStatus.QUEUED
    created_at: datetime
    finished_at: datetime | None = None


class TaskExecutionCreate(BaseModel):
    task_id: str = Field(min_length=1, max_length=120)
    task_seed: int = Field(ge=0)


class TaskExecution(TaskExecutionCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4)
    run_id: UUID
    status: ExecutionStatus = ExecutionStatus.PENDING
    passed: bool | None = None
    final_output: str | None = None
    latency_ms: int | None = Field(default=None, ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0)
    created_at: datetime
    finished_at: datetime | None = None


class TaskExecutionResult(BaseModel):
    status: ExecutionStatus
    passed: bool
    final_output: str = Field(min_length=1)
    latency_ms: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)

    @model_validator(mode="after")
    def terminal_status_matches_outcome(self) -> "TaskExecutionResult":
        if self.status not in {ExecutionStatus.PASSED, ExecutionStatus.FAILED, ExecutionStatus.ERRORED}:
            raise ValueError("result status must be passed, failed, or errored")
        if self.status == ExecutionStatus.PASSED and not self.passed:
            raise ValueError("a passed execution must have passed=true")
        if self.status == ExecutionStatus.FAILED and self.passed:
            raise ValueError("a failed execution must have passed=false")
        return self


class TraceEventCreate(BaseModel):
    sequence_no: int = Field(ge=0)
    event_type: EventType
    payload: dict[str, Any] = Field(default_factory=dict)
    parent_event_id: UUID | None = None
    duration_ms: int | None = Field(default=None, ge=0)


class TraceEvent(TraceEventCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4)
    execution_id: UUID
    created_at: datetime


class TraceAttribution(BaseModel):
    task_id: str
    baseline_execution_id: UUID
    candidate_execution_id: UUID
    baseline_event_id: UUID | None = None
    candidate_event_id: UUID | None = None
    divergence_type: TraceDivergenceType
    evidence: dict[str, Any]


class PairedTaskComparison(BaseModel):
    task_id: str
    disposition: RegressionDisposition
    baseline_execution_id: UUID
    candidate_execution_id: UUID
    baseline_passed: bool | None
    candidate_passed: bool | None
    latency_delta_ms: int | None
    cost_delta_usd: float | None
    attribution: TraceAttribution | None = None


class RunComparison(BaseModel):
    baseline_run_id: UUID
    candidate_run_id: UUID
    compared_tasks: int
    regressions: int
    improvements: int
    results: list[PairedTaskComparison]
