"""POST/GET /api/v1/executions/{id}/judge-verdicts."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from app.store import PlatformStore


def _client_with_execution() -> tuple[TestClient, str]:
    client = TestClient(create_app(PlatformStore()))
    version = client.post(
        "/api/v1/agent-versions",
        json={
            "name": "support-agent",
            "git_sha": "abc1234",
            "model": "test-model",
            "system_prompt": "Follow the policy.",
            "tool_schema_hash": "a1b2c3d4",
        },
    ).json()
    run = client.post(
        "/api/v1/evaluation-runs",
        json={
            "agent_version_id": version["id"],
            "suite_id": "support-ops",
            "suite_version": "v1",
            "suite_manifest_hash": "manifest123",
            "seed": 7,
        },
    ).json()
    execution = client.post(
        f"/api/v1/evaluation-runs/{run['id']}/executions",
        json={"task_id": "refund-001", "task_seed": 7},
    ).json()
    return client, execution["id"]


def test_append_and_list_judge_verdicts() -> None:
    client, execution_id = _client_with_execution()

    post = client.post(
        f"/api/v1/executions/{execution_id}/judge-verdicts",
        json={
            "judge_name": "policy_judge",
            "rubric_version": "v1",
            "label": "pass",
            "confidence": 0.9,
            "rationale": "Identity was checked before acting.",
        },
    )
    assert post.status_code == 201
    assert post.json()["judge_name"] == "policy_judge"

    get = client.get(f"/api/v1/executions/{execution_id}/judge-verdicts")
    assert get.status_code == 200
    verdicts = get.json()
    assert len(verdicts) == 1
    assert verdicts[0]["label"] == "pass"
    assert verdicts[0]["execution_id"] == execution_id


def test_get_judge_verdicts_is_empty_for_an_execution_with_none() -> None:
    client, execution_id = _client_with_execution()

    response = client.get(f"/api/v1/executions/{execution_id}/judge-verdicts")

    assert response.status_code == 200
    assert response.json() == []


def test_append_judge_verdict_404s_for_an_unknown_execution() -> None:
    client = TestClient(create_app(PlatformStore()))

    response = client.post(
        "/api/v1/executions/00000000-0000-0000-0000-000000000000/judge-verdicts",
        json={
            "judge_name": "policy_judge",
            "rubric_version": "v1",
            "label": "pass",
            "confidence": 0.9,
            "rationale": "n/a",
        },
    )

    assert response.status_code == 404
