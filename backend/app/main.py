from __future__ import annotations

from uuid import UUID

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware

from app.comparison import compare_runs
from app.schemas import (
    AgentVersion,
    AgentVersionCreate,
    EvaluationRun,
    EvaluationRunCreate,
    RunComparison,
    TaskExecution,
    TaskExecutionCreate,
    TaskExecutionResult,
    TraceEvent,
    TraceEventCreate,
)
from app.postgres_store import PostgresStore
from app.store import Store


def create_app(store: Store | None = None) -> FastAPI:
    app = FastAPI(title="AgentProof Platform API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.state.store = store or PostgresStore()

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/v1/agent-versions", response_model=AgentVersion, status_code=status.HTTP_201_CREATED)
    async def create_agent_version(payload: AgentVersionCreate) -> AgentVersion:
        return await app.state.store.create_agent_version(payload)

    @app.post("/api/v1/evaluation-runs", response_model=EvaluationRun, status_code=status.HTTP_201_CREATED)
    async def create_evaluation_run(payload: EvaluationRunCreate) -> EvaluationRun:
        return await app.state.store.create_run(payload)

    @app.post(
        "/api/v1/evaluation-runs/{run_id}/executions",
        response_model=TaskExecution,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_task_execution(run_id: UUID, payload: TaskExecutionCreate) -> TaskExecution:
        return await app.state.store.create_execution(run_id, payload)

    @app.post("/api/v1/executions/{execution_id}/result", response_model=TaskExecution)
    async def record_task_result(execution_id: UUID, payload: TaskExecutionResult) -> TaskExecution:
        return await app.state.store.record_result(execution_id, payload)

    @app.get("/api/v1/executions/{execution_id}", response_model=TaskExecution)
    async def get_task_execution(execution_id: UUID) -> TaskExecution:
        return await app.state.store.get_execution(execution_id)

    @app.post(
        "/api/v1/executions/{execution_id}/trace-events",
        response_model=TraceEvent,
        status_code=status.HTTP_201_CREATED,
    )
    async def append_trace_event(execution_id: UUID, payload: TraceEventCreate) -> TraceEvent:
        return await app.state.store.append_trace_event(execution_id, payload)

    @app.get("/api/v1/executions/{execution_id}/trace", response_model=list[TraceEvent])
    async def get_trace(execution_id: UUID) -> list[TraceEvent]:
        return await app.state.store.get_trace(execution_id)

    @app.get("/api/v1/comparisons/{baseline_run_id}/{candidate_run_id}", response_model=RunComparison)
    async def get_comparison(baseline_run_id: UUID, candidate_run_id: UUID) -> RunComparison:
        return await compare_runs(app.state.store, baseline_run_id, candidate_run_id)

    return app


app = create_app()
