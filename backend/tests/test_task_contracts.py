"""GET /api/v1/tasks and GET /api/v1/tasks/{task_id}.

These are read-only views of benchmark.tasks.SEED_TASKS - nothing here touches the
store, so a single PlatformStore-backed client covers it.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from app.store import PlatformStore
from benchmark.tasks import SEED_TASKS


def _client() -> TestClient:
    return TestClient(create_app(PlatformStore()))


def test_list_task_contracts_returns_every_seed_task() -> None:
    response = _client().get("/api/v1/tasks")

    assert response.status_code == 200
    task_ids = {task["task_id"] for task in response.json()}
    assert task_ids == {task.task_id for task in SEED_TASKS}


def test_get_task_contract_returns_the_full_contract() -> None:
    task = SEED_TASKS[0]

    response = _client().get(f"/api/v1/tasks/{task.task_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["task_id"] == task.task_id
    assert body["input"] == task.input
    assert body["difficulty"] == task.difficulty.value
    assert [(a["service"], a["operation"], a["arguments"]) for a in body["expected_actions"]] == [
        (action.service, action.operation, action.arguments) for action in task.expected_actions
    ]
    assert body["expected_final_state"] == task.expected_final_state


def test_get_task_contract_404s_for_an_unknown_task_id() -> None:
    response = _client().get("/api/v1/tasks/does-not-exist")

    assert response.status_code == 404
