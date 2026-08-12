"""LLM judge scaffolding for evaluation criteria deterministic scoring can't cover.

A Judge renders a versioned rubric plus the task's evidence into a prompt,
calls a pluggable model, and parses the response into a structured
JudgeVerdict. The model call is injected as a `ModelCaller` so judges are
testable and provider-agnostic; nothing here talks to a real LLM API.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from benchmark.schema import BenchmarkTask
from judges.contracts import ToolCall

RUBRICS_DIR = Path(__file__).parent / "rubrics"

JudgeLabel = Literal["pass", "fail", "uncertain"]


class ModelCaller(Protocol):
    """Abstraction over an LLM call: rendered prompt in, raw text out."""

    def __call__(self, prompt: str) -> str: ...


class JudgeResponseError(ValueError):
    """Raised when a model's response can't be parsed into a JudgeVerdict."""


@dataclass(frozen=True)
class JudgeVerdict:
    task_id: str
    judge_name: str
    rubric_version: str
    label: JudgeLabel
    confidence: float
    rationale: str


_LABEL_PATTERN = re.compile(r"^LABEL:\s*(pass|fail|uncertain)\s*$", re.IGNORECASE | re.MULTILINE)
_CONFIDENCE_PATTERN = re.compile(r"^CONFIDENCE:\s*([01](?:\.\d+)?)\s*$", re.IGNORECASE | re.MULTILINE)
_RATIONALE_PATTERN = re.compile(r"^RATIONALE:\s*(.+)", re.IGNORECASE | re.DOTALL | re.MULTILINE)


def parse_judge_response(raw: str) -> tuple[JudgeLabel, float, str]:
    """Parse a model's `LABEL:` / `CONFIDENCE:` / `RATIONALE:` response."""

    label_match = _LABEL_PATTERN.search(raw)
    confidence_match = _CONFIDENCE_PATTERN.search(raw)
    rationale_match = _RATIONALE_PATTERN.search(raw)
    if not (label_match and confidence_match and rationale_match):
        raise JudgeResponseError(
            f"Could not parse LABEL/CONFIDENCE/RATIONALE from judge response: {raw!r}"
        )

    confidence = float(confidence_match.group(1))
    if not 0.0 <= confidence <= 1.0:
        raise JudgeResponseError(f"Confidence out of range [0, 1]: {confidence}")

    label = label_match.group(1).lower()
    rationale = rationale_match.group(1).strip()
    return label, confidence, rationale  # type: ignore[return-value]


@dataclass(frozen=True)
class Judge:
    """A rubric-driven LLM judge for one evaluation criterion.

    The rubric lives in `judges/rubrics/*.md` as reviewable text rather than
    a Python string, so it can be read and revised without touching code.
    Its first line must be `version: <id>`.
    """

    name: str
    rubric_path: Path

    @property
    def rubric(self) -> str:
        return self.rubric_path.read_text(encoding="utf-8")

    @property
    def rubric_version(self) -> str:
        first_line = self.rubric.splitlines()[0]
        return first_line.removeprefix("version:").strip()

    def build_prompt(
        self,
        task: BenchmarkTask,
        tool_calls: tuple[ToolCall, ...],
        final_response: str | None,
    ) -> str:
        calls_description = (
            "\n".join(f"- {call.service}.{call.operation}({call.arguments})" for call in tool_calls)
            or "(no tool calls)"
        )
        return (
            f"{self.rubric}\n\n"
            "## Task\n"
            f"{task.input}\n\n"
            "## Tool calls made\n"
            f"{calls_description}\n\n"
            "## Agent's final response to the customer\n"
            f"{final_response or '(no final response provided)'}\n\n"
            "Respond in exactly this format:\n"
            "LABEL: <pass|fail|uncertain>\n"
            "CONFIDENCE: <0.0-1.0>\n"
            "RATIONALE: <one or two sentences>\n"
        )

    def evaluate(
        self,
        task: BenchmarkTask,
        tool_calls: tuple[ToolCall, ...],
        final_response: str | None,
        model_caller: ModelCaller,
    ) -> JudgeVerdict:
        prompt = self.build_prompt(task, tool_calls, final_response)
        label, confidence, rationale = parse_judge_response(model_caller(prompt))
        return JudgeVerdict(
            task_id=task.task_id,
            judge_name=self.name,
            rubric_version=self.rubric_version,
            label=label,
            confidence=confidence,
            rationale=rationale,
        )


POLICY_JUDGE = Judge(name="policy_judge", rubric_path=RUBRICS_DIR / "policy_judge.md")
RESPONSE_QUALITY_JUDGE = Judge(
    name="response_quality_judge", rubric_path=RUBRICS_DIR / "response_quality_judge.md"
)
