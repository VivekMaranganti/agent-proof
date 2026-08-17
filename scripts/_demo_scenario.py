"""Shared baseline/candidate demo scenario: a real regression on real seed tasks.

Used by both run_demo_comparison.py (PlatformStore, serves the API itself, for local
frontend dev) and seed_demo_data.py (PostgresStore, for the docker-compose stack).
seed() is generic over any Store-protocol store - only the caller decides which one.
"""

from __future__ import annotations

from uuid import uuid4

from app.execution_scoring import score_execution
from app.schemas import AgentVersionCreate, EvaluationRunCreate, JudgeVerdictCreate, TaskExecutionCreate
from app.store import Store
from benchmark.schema import BenchmarkTask
from benchmark.tasks import (
    CUSTOMER_REFUND_OUTSIDE_POLICY,
    CUSTOMER_REFUND_WITHIN_POLICY,
    ORDER_CANCELLATION_DENIED_AFTER_DELIVERY,
)
from runner.model_client import ModelReply, ScriptedModelClient, ToolCallRequest
from runner.runner import run_task

TASKS: tuple[BenchmarkTask, ...] = (
    CUSTOMER_REFUND_WITHIN_POLICY,
    CUSTOMER_REFUND_OUTSIDE_POLICY,
    ORDER_CANCELLATION_DENIED_AFTER_DELIVERY,
)


def _correct_model_for(task: BenchmarkTask) -> ScriptedModelClient:
    if task is CUSTOMER_REFUND_WITHIN_POLICY:
        return ScriptedModelClient(
            [
                ModelReply(
                    finish_reason="tool_calls",
                    tool_calls=(ToolCallRequest("c1", "customer", "get_customer", {"customer_id": "CUST-001"}),),
                ),
                ModelReply(
                    finish_reason="tool_calls",
                    tool_calls=(ToolCallRequest("c2", "order", "get_order", {"order_id": "ORD-1001"}),),
                ),
                ModelReply(
                    finish_reason="tool_calls",
                    tool_calls=(ToolCallRequest("c3", "policy", "check_refund_policy", {"order_id": "ORD-1001"}),),
                ),
                ModelReply(
                    finish_reason="tool_calls",
                    tool_calls=(
                        ToolCallRequest(
                            "c4",
                            "refund",
                            "create_refund",
                            {
                                "order_id": "ORD-1001",
                                "requesting_customer_id": "CUST-001",
                                "amount_cents": 4200,
                                "reason": "damaged_item",
                            },
                        ),
                    ),
                ),
                ModelReply(
                    finish_reason="tool_calls",
                    tool_calls=(
                        ToolCallRequest(
                            "c5", "ticket", "update_ticket", {"ticket_id": "TICK-9001", "status": "resolved"}
                        ),
                    ),
                ),
                ModelReply(finish_reason="stop", content="Your refund has been issued."),
            ]
        )
    if task is CUSTOMER_REFUND_OUTSIDE_POLICY:
        return ScriptedModelClient(
            [
                ModelReply(
                    finish_reason="tool_calls",
                    tool_calls=(ToolCallRequest("c1", "customer", "get_customer", {"customer_id": "CUST-002"}),),
                ),
                ModelReply(
                    finish_reason="tool_calls",
                    tool_calls=(ToolCallRequest("c2", "order", "get_order", {"order_id": "ORD-2001"}),),
                ),
                ModelReply(
                    finish_reason="tool_calls",
                    tool_calls=(ToolCallRequest("c3", "policy", "check_refund_policy", {"order_id": "ORD-2001"}),),
                ),
                ModelReply(
                    finish_reason="tool_calls",
                    tool_calls=(
                        ToolCallRequest(
                            "c4", "ticket", "update_ticket", {"ticket_id": "TICK-9002", "status": "resolved"}
                        ),
                    ),
                ),
                ModelReply(finish_reason="stop", content="This order is outside our 30-day refund window."),
            ]
        )
    return ScriptedModelClient(
        [
            ModelReply(
                finish_reason="tool_calls",
                tool_calls=(ToolCallRequest("c1", "customer", "get_customer", {"customer_id": "CUST-009"}),),
            ),
            ModelReply(
                finish_reason="tool_calls",
                tool_calls=(ToolCallRequest("c2", "order", "get_order", {"order_id": "ORD-9001"}),),
            ),
            ModelReply(
                finish_reason="tool_calls",
                tool_calls=(
                    ToolCallRequest(
                        "c3", "ticket", "update_ticket", {"ticket_id": "TICK-9009", "status": "resolved"}
                    ),
                ),
            ),
            ModelReply(finish_reason="stop", content="This order has already been delivered and can't be cancelled."),
        ]
    )


def _regressed_model_for_refund_within_policy() -> ScriptedModelClient:
    # Skips the refund step entirely: the candidate resolves the ticket without
    # ever issuing the refund the task's contract requires.
    return ScriptedModelClient(
        [
            ModelReply(
                finish_reason="tool_calls",
                tool_calls=(ToolCallRequest("c1", "customer", "get_customer", {"customer_id": "CUST-001"}),),
            ),
            ModelReply(
                finish_reason="tool_calls",
                tool_calls=(
                    ToolCallRequest(
                        "c2", "ticket", "update_ticket", {"ticket_id": "TICK-9001", "status": "resolved"}
                    ),
                ),
            ),
            ModelReply(finish_reason="stop", content="Your ticket has been resolved."),
        ]
    )


# A real disagreement case: no live model backend exists yet to run judges for
# real (see runner/worker.py's judge_model_caller), so this is hand-seeded onto
# the regressed candidate execution to give the judge-results view something
# genuine to show — two judges assessing different things, correctly reaching
# different verdicts about the same run.
REGRESSED_REFUND_JUDGE_VERDICTS: tuple[JudgeVerdictCreate, ...] = (
    JudgeVerdictCreate(
        judge_name="policy_judge",
        rubric_version="1",
        label="fail",
        confidence=0.9,
        rationale="The agent never checked refund eligibility or issued the refund the customer was owed.",
    ),
    JudgeVerdictCreate(
        judge_name="response_quality_judge",
        rubric_version="1",
        label="pass",
        confidence=0.6,
        rationale="The reply itself is polite and clearly worded, even though it doesn't reflect the missing refund.",
    ),
)


async def _run_and_record(
    store: Store,
    run_id,
    version,
    task: BenchmarkTask,
    model: ScriptedModelClient,
    judge_verdicts: tuple[JudgeVerdictCreate, ...] = (),
) -> None:
    result = await run_task(version, task, model, execution_id=uuid4())
    execution_result, _ = score_execution(task, result)

    execution = await store.create_execution(run_id, TaskExecutionCreate(task_id=task.task_id, task_seed=0))
    for event in result.trace.to_storage():
        await store.append_trace_event(execution.id, event)
    await store.record_result(execution.id, execution_result)
    for verdict in judge_verdicts:
        await store.append_judge_verdict(execution.id, verdict)


async def seed(store: Store) -> tuple[str, str]:
    #tool_schema_hash differs between baseline/candidate so they get genuinely distinct
    #content-hashed identities, not the same version twice
    baseline_version = await store.create_agent_version(
        AgentVersionCreate(
            name="support-agent",
            git_sha="baseline0000000",
            model="demo-model",
            system_prompt="You are a customer support agent.",
            tool_schema_hash="demo-schema-hash-baseline",
            config={},
        )
    )
    candidate_version = await store.create_agent_version(
        AgentVersionCreate(
            name="support-agent",
            git_sha="candidate000000",
            model="demo-model",
            system_prompt="You are a customer support agent.",
            tool_schema_hash="demo-schema-hash-candidate",
            config={},
        )
    )

    baseline_run = await store.create_run(
        EvaluationRunCreate(
            agent_version_id=baseline_version.id,
            suite_id="customer-support-v1",
            suite_version="1",
            suite_manifest_hash="demo-manifest-hash",
            seed=1,
        )
    )
    candidate_run = await store.create_run(
        EvaluationRunCreate(
            agent_version_id=candidate_version.id,
            suite_id="customer-support-v1",
            suite_version="1",
            suite_manifest_hash="demo-manifest-hash",
            seed=1,
        )
    )

    for task in TASKS:
        await _run_and_record(store, baseline_run.id, baseline_version, task, _correct_model_for(task))
        is_regressed_task = task is CUSTOMER_REFUND_WITHIN_POLICY
        candidate_model = (
            _regressed_model_for_refund_within_policy() if is_regressed_task else _correct_model_for(task)
        )
        await _run_and_record(
            store,
            candidate_run.id,
            candidate_version,
            task,
            candidate_model,
            judge_verdicts=REGRESSED_REFUND_JUDGE_VERDICTS if is_regressed_task else (),
        )

    return str(baseline_run.id), str(candidate_run.id)
