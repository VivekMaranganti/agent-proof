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


def _tool_call(client: TestClient, execution_id: str, tool_name: str) -> None:
    response = client.post(
        f"/api/v1/executions/{execution_id}/trace-events",
        json={
            "sequence_no": 0,
            "event_type": "tool_call",
            "payload": {"tool_name": tool_name, "arguments": {"order_id": "o-1"}},
        },
    )
    assert response.status_code == 201


def test_comparison_attributes_a_wrong_tool_regression() -> None:
    client = TestClient(create_app(PlatformStore()))
    baseline_run = _create_run(client, _create_version(client, "1111111"))
    candidate_run = _create_run(client, _create_version(client, "2222222"))
    baseline_execution = _create_execution(client, baseline_run, "refund-001")
    candidate_execution = _create_execution(client, candidate_run, "refund-001")
    _tool_call(client, baseline_execution, "lookup_order")
    _tool_call(client, candidate_execution, "issue_refund")
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
    _tool_call(client, execution_id, "lookup_order")
    duplicate = client.post(
        f"/api/v1/executions/{execution_id}/trace-events",
        json={"sequence_no": 0, "event_type": "tool_result", "payload": {}},
    )
    assert duplicate.status_code == 409
