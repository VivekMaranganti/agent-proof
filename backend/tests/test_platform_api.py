from fastapi.testclient import TestClient

from app.main import create_app
from app.store import PlatformStore


def _create_version(client: TestClient, sha: str) -> str:
    response = client.post(
        "/api/v1/agent-versions",
        json={
            "name": f"support-agent-{sha}",
            "git_sha": sha,
            "model": "test-model",
            "system_prompt": "Follow the policy.",
            "tool_schema_hash": "a1b2c3d4",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_run(client: TestClient, version_id: str) -> str:
    response = client.post(
        "/api/v1/evaluation-runs",
        json={
            "agent_version_id": version_id,
            "suite_id": "support-ops",
            "suite_version": "v1",
            "suite_manifest_hash": "manifest123",
            "seed": 7,
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_execution(client: TestClient, run_id: str, task_id: str) -> str:
    response = client.post(
        f"/api/v1/evaluation-runs/{run_id}/executions",
        json={"task_id": task_id, "task_seed": 7},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _result(client: TestClient, execution_id: str, passed: bool) -> None:
    response = client.post(
        f"/api/v1/executions/{execution_id}/result",
        json={
            "status": "passed" if passed else "failed",
            "passed": passed,
            "final_output": "resolved" if passed else "wrong resolution",
            "latency_ms": 100,
            "input_tokens": 30,
            "output_tokens": 12,
            "estimated_cost_usd": 0.001,
        },
    )
    assert response.status_code == 200


def _tool_call(client: TestClient, execution_id: str, operation: str) -> None:
    response = client.post(
        f"/api/v1/executions/{execution_id}/trace-events",
        json={
            "sequence_no": 0,
            "event_type": "tool_call",
            "payload": {"call_id": "c-1", "service": "order", "operation": operation, "arguments": {"order_id": "o-1"}},
        },
    )
    assert response.status_code == 201


def test_comparison_attributes_a_wrong_tool_regression() -> None:
    client = TestClient(create_app(PlatformStore()))
    baseline_run = _create_run(client, _create_version(client, "1111111"))
    candidate_run = _create_run(client, _create_version(client, "2222222"))
    baseline_execution = _create_execution(client, baseline_run, "refund-001")
    candidate_execution = _create_execution(client, candidate_run, "refund-001")
    _tool_call(client, baseline_execution, "get_order")
    _tool_call(client, candidate_execution, "create_refund")
    _result(client, baseline_execution, passed=True)
    _result(client, candidate_execution, passed=False)

    response = client.get(f"/api/v1/comparisons/{baseline_run}/{candidate_run}")

    assert response.status_code == 200
    comparison = response.json()
    assert comparison["regressions"] == 1
    result = comparison["results"][0]
    assert result["disposition"] == "regression"
    assert result["attribution"]["divergence_type"] == "wrong_tool"


def test_trace_sequence_numbers_are_unique_per_execution() -> None:
    client = TestClient(create_app(PlatformStore()))
    run_id = _create_run(client, _create_version(client, "3333333"))
    execution_id = _create_execution(client, run_id, "refund-002")
    _tool_call(client, execution_id, "get_order")
    duplicate = client.post(
        f"/api/v1/executions/{execution_id}/trace-events",
        json={"sequence_no": 0, "event_type": "tool_result", "payload": {}},
    )
    assert duplicate.status_code == 409


def test_get_execution_returns_the_recorded_result() -> None:
    client = TestClient(create_app(PlatformStore()))
    run_id = _create_run(client, _create_version(client, "4444444"))
    execution_id = _create_execution(client, run_id, "refund-003")
    _result(client, execution_id, passed=True)

    response = client.get(f"/api/v1/executions/{execution_id}")

    assert response.status_code == 200
    execution = response.json()
    assert execution["id"] == execution_id
    assert execution["status"] == "passed"
    assert execution["passed"] is True


def test_get_run_executions_lists_all_executions_for_a_run() -> None:
    client = TestClient(create_app(PlatformStore()))
    run_id = _create_run(client, _create_version(client, "5555555"))
    first = _create_execution(client, run_id, "refund-004")
    second = _create_execution(client, run_id, "refund-005")

    response = client.get(f"/api/v1/evaluation-runs/{run_id}/executions")

    assert response.status_code == 200
    execution_ids = {execution["id"] for execution in response.json()}
    assert execution_ids == {first, second}


def test_get_trace_paginates_and_reports_total_count() -> None:
    client = TestClient(create_app(PlatformStore()))
    run_id = _create_run(client, _create_version(client, "6666666"))
    execution_id = _create_execution(client, run_id, "refund-006")
    for sequence_no in range(5):
        response = client.post(
            f"/api/v1/executions/{execution_id}/trace-events",
            json={"sequence_no": sequence_no, "event_type": "tool_result", "payload": {}},
        )
        assert response.status_code == 201

    page = client.get(f"/api/v1/executions/{execution_id}/trace", params={"limit": 2, "offset": 1})

    assert page.status_code == 200
    assert page.headers["X-Total-Count"] == "5"
    events = page.json()
    assert [event["sequence_no"] for event in events] == [1, 2]

    full = client.get(f"/api/v1/executions/{execution_id}/trace")
    assert len(full.json()) == 5
