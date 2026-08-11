"""Ordered, typed trace model.

Runner-facing representation of one task execution's evidence: prompts, model
responses, tool calls/results, retries, and errors, in the order they occurred.
Builds up in memory as `Trace`/`TraceStep` and serializes losslessly to the
`TraceEventCreate`/`TraceEvent` storage contracts in schemas.py.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal, Sequence
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from app.schemas import EventType, TraceEvent, TraceEventCreate


class ModelRequestPayload(BaseModel):
    event_type: Literal[EventType.MODEL_REQUEST] = EventType.MODEL_REQUEST
    messages: list[dict[str, Any]]
    model: str
    params: dict[str, Any] = Field(default_factory=dict)


class ModelResponsePayload(BaseModel):
    event_type: Literal[EventType.MODEL_RESPONSE] = EventType.MODEL_RESPONSE
    content: str | None = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    finish_reason: str
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)


class ToolCallPayload(BaseModel):
    event_type: Literal[EventType.TOOL_CALL] = EventType.TOOL_CALL
    call_id: str
    service: str
    operation: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResultPayload(BaseModel):
    event_type: Literal[EventType.TOOL_RESULT] = EventType.TOOL_RESULT
    call_id: str
    result: Any = None


class RetryPayload(BaseModel):
    event_type: Literal[EventType.RETRY] = EventType.RETRY
    attempt: int = Field(ge=1)
    reason: str


class ErrorPayload(BaseModel):
    event_type: Literal[EventType.ERROR] = EventType.ERROR
    error_type: str
    message: str


class FinalAnswerPayload(BaseModel):
    event_type: Literal[EventType.FINAL_ANSWER] = EventType.FINAL_ANSWER
    content: str


StepPayload = Annotated[
    ModelRequestPayload
    | ModelResponsePayload
    | ToolCallPayload
    | ToolResultPayload
    | RetryPayload
    | ErrorPayload
    | FinalAnswerPayload,
    Field(discriminator="event_type"),
]

_step_payload_adapter: TypeAdapter[StepPayload] = TypeAdapter(StepPayload)


class TraceStep(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4)
    sequence_no: int = Field(ge=0)
    payload: StepPayload
    parent_step_id: UUID | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    created_at: datetime | None = None

    @property
    def event_type(self) -> EventType:
        return self.payload.event_type


class Trace:
    """Ordered, append-only sequence of steps for one task execution.

    Sequence numbers are assigned by append order, not supplied by the caller,
    so the ordering guarantee can't be violated from outside the class.
    """

    def __init__(self, execution_id: UUID) -> None:
        self.execution_id = execution_id
        self._steps: list[TraceStep] = []
        self._step_ids: set[UUID] = set()

    def __len__(self) -> int:
        return len(self._steps)

    def __iter__(self):
        return iter(self._steps)

    @property
    def steps(self) -> list[TraceStep]:
        return list(self._steps)

    def append(
        self,
        payload: StepPayload,
        *,
        parent_step_id: UUID | None = None,
        duration_ms: int | None = None,
    ) -> TraceStep:
        if parent_step_id is not None and parent_step_id not in self._step_ids:
            raise ValueError(f"parent_step_id {parent_step_id} is not a step in this trace")
        step = TraceStep(
            sequence_no=len(self._steps),
            payload=payload,
            parent_step_id=parent_step_id,
            duration_ms=duration_ms,
        )
        self._steps.append(step)
        self._step_ids.add(step.id)
        return step

    def to_storage(self) -> list[TraceEventCreate]:
        return [
            TraceEventCreate(
                id=step.id,
                sequence_no=step.sequence_no,
                event_type=step.event_type,
                payload=step.payload.model_dump(mode="json", exclude={"event_type"}),
                parent_event_id=step.parent_step_id,
                duration_ms=step.duration_ms,
            )
            for step in self._steps
        ]

    @classmethod
    def from_storage(cls, execution_id: UUID, events: Sequence[TraceEvent]) -> "Trace":
        trace = cls(execution_id)
        ordered = sorted(events, key=lambda event: event.sequence_no)
        for expected_sequence_no, event in enumerate(ordered):
            if event.sequence_no != expected_sequence_no:
                raise ValueError(
                    f"trace event sequence gap: expected {expected_sequence_no}, got {event.sequence_no}"
                )
            if event.parent_event_id is not None and event.parent_event_id not in trace._step_ids:
                raise ValueError(f"parent_event_id {event.parent_event_id} is not a prior step in this trace")
            payload = _step_payload_adapter.validate_python({**event.payload, "event_type": event.event_type})
            step = TraceStep(
                id=event.id,
                sequence_no=event.sequence_no,
                payload=payload,
                parent_step_id=event.parent_event_id,
                duration_ms=event.duration_ms,
                created_at=event.created_at,
            )
            trace._steps.append(step)
            trace._step_ids.add(step.id)
        return trace
