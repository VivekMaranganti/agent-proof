from __future__ import annotations

from uuid import UUID

from fastapi import FastAPI, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware

from app.comparison import compare_runs
from app.schemas import (
    AgentVersion,
    AgentVersionCreate,
    EvaluationRun,
    EvaluationRunCreate,
    RegressionDisposition,
    RunComparison,
    TaskExecution,
    TaskExecutionCreate,
    TaskExecutionResult,
    TraceDivergenceType,
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

    @app.get("/api/v1/agent-versions/{agent_version_id}", response_model=AgentVersion)
    async def get_agent_version(agent_version_id: UUID) -> AgentVersion:
        return await app.state.store.get_agent_version(agent_version_id)

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

    @app.get("/api/v1/evaluation-runs/{run_id}/executions", response_model=list[TaskExecution])
    async def get_run_executions(
        run_id: UUID,
        task_id: str | None = None,
        passed: bool | None = None,
    ) -> list[TaskExecution]:
        executions = await app.state.store.get_run_executions(run_id)
        if task_id is not None:
            executions = [execution for execution in executions if execution.task_id == task_id]
        if passed is not None:
            executions = [execution for execution in executions if execution.passed == passed]
        return executions

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
    async def get_trace(
        execution_id: UUID,
        response: Response,
        limit: int = Query(default=200, ge=1, le=1000),
        offset: int = Query(default=0, ge=0),
    ) -> list[TraceEvent]:
        events = await app.state.store.get_trace(execution_id)
        response.headers["X-Total-Count"] = str(len(events))
        return events[offset : offset + limit]

    @app.get("/api/v1/comparisons/{baseline_run_id}/{candidate_run_id}", response_model=RunComparison)
    async def get_comparison(
        baseline_run_id: UUID,
        candidate_run_id: UUID,
        task_id: str | None = None,
        disposition: RegressionDisposition | None = None,
        divergence_type: TraceDivergenceType | None = None,
    ) -> RunComparison:
        comparison = await compare_runs(app.state.store, baseline_run_id, candidate_run_id)
        results = comparison.results
        if task_id is not None:
            results = [result for result in results if result.task_id == task_id]
        if disposition is not None:
            results = [result for result in results if result.disposition == disposition]
        if divergence_type is not None:
            results = [
                result
                for result in results
                if result.attribution is not None and result.attribution.divergence_type == divergence_type
            ]
        return comparison.model_copy(update={"results": results})

    return app


app = create_app()
