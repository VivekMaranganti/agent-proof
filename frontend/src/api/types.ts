// Mirrors backend/app/schemas.py. Field names are snake_case to match the
// FastAPI JSON output verbatim (no camelCase alias generator is configured
// there), so don't "fix" the casing here.

export type RegressionDisposition =
  | "stable_pass"
  | "stable_failure"
  | "improvement"
  | "regression"
  | "indeterminate";

export type TraceDivergenceType =
  | "wrong_tool"
  | "invalid_tool_argument"
  | "tool_error"
  | "premature_termination"
  | "final_answer_mismatch";

export interface TraceAttribution {
  task_id: string;
  baseline_execution_id: string;
  candidate_execution_id: string;
  baseline_event_id: string | null;
  candidate_event_id: string | null;
  divergence_type: TraceDivergenceType;
  evidence: Record<string, unknown>;
}

export interface PairedTaskComparison {
  task_id: string;
  disposition: RegressionDisposition;
  baseline_execution_id: string;
  candidate_execution_id: string;
  baseline_passed: boolean | null;
  candidate_passed: boolean | null;
  latency_delta_ms: number | null;
  cost_delta_usd: number | null;
  attribution: TraceAttribution | null;
}

export interface RunComparison {
  baseline_run_id: string;
  candidate_run_id: string;
  compared_tasks: number;
  regressions: number;
  improvements: number;
  results: PairedTaskComparison[];
}

export type EventType =
  | "model_request"
  | "model_response"
  | "tool_call"
  | "tool_result"
  | "retry"
  | "error"
  | "final_answer";

// payload shape depends on event_type; see backend/app/trace.py's *Payload classes.
export interface TraceEvent {
  id: string;
  sequence_no: number;
  event_type: EventType;
  payload: Record<string, unknown>;
  parent_event_id: string | null;
  duration_ms: number | null;
  execution_id: string;
  created_at: string;
}

export type ExecutionStatus = "pending" | "running" | "passed" | "failed" | "errored";

export interface TaskExecution {
  task_id: string;
  task_seed: number;
  id: string;
  run_id: string;
  status: ExecutionStatus;
  passed: boolean | null;
  final_output: string | null;
  latency_ms: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  estimated_cost_usd: number | null;
  missing_expected_actions: string[];
  forbidden_actions_seen: string[];
  final_state_mismatches: string[];
  created_at: string;
  finished_at: string | null;
}

export interface ExpectedActionContract {
  service: string;
  operation: string;
  arguments: Record<string, unknown>;
}

export interface ForbiddenActionContract {
  service: string;
  operation: string;
  reason: string;
  arguments: Record<string, unknown>;
}

export interface TaskContract {
  task_id: string;
  input: string;
  initial_state: Record<string, unknown>;
  expected_actions: ExpectedActionContract[];
  forbidden_actions: ForbiddenActionContract[];
  expected_final_state: Record<string, unknown>;
  tags: string[];
  difficulty: string;
}

export type JudgeLabel = "pass" | "fail" | "uncertain";

export interface JudgeVerdict {
  id: string;
  execution_id: string;
  judge_name: string;
  rubric_version: string;
  label: JudgeLabel;
  confidence: number;
  rationale: string;
  created_at: string;
}
