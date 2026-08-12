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
