"""A ModelClient that solves a task from its own contract instead of live model calls.

Stands in for a real model backend so the worker can process any seed task, not just
one hand-scripted one. It's an oracle, not an agent: it walks task.expected_actions in
order as tool calls, then returns a final answer.

Known limitation: ExpectedAction.arguments is deliberately a partial subset used for
contract matching (score_actions only checks it's a subset of the actual call), not a
full call signature - some services need arguments a task doesn't record there at all
(RefundService.create_refund's requesting_customer_id/reason, for example). Tasks
needing those still fail here with a real, correctly-recorded contract mismatch rather
than a crash; deriving the full signature from initial_state/expected_final_state
would mean re-encoding per-task business logic here, which isn't worth it for what
this exists to prove (the runner/queue/worker path, not agent quality).
"""

from __future__ import annotations

from typing import Any

from benchmark.schema import BenchmarkTask
from runner.model_client import ModelReply, ToolCallRequest


class ReferenceAgentModelClient:
    def __init__(self, task: BenchmarkTask) -> None:
        self._actions = task.expected_actions
        self._step = 0

    async def complete(
        self, *, messages: list[dict[str, Any]], model: str, params: dict[str, Any]
    ) -> ModelReply:
        if self._step < len(self._actions):
            action = self._actions[self._step]
            self._step += 1
            return ModelReply(
                finish_reason="tool_calls",
                tool_calls=(
                    ToolCallRequest(f"c{self._step}", action.service, action.operation, dict(action.arguments)),
                ),
            )
        return ModelReply(finish_reason="stop", content="Resolved according to policy.")
