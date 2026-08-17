import type { RunComparison, TaskContract, TaskExecution, TraceEvent } from "./types";

const DEFAULT_API_BASE_URL = "http://localhost:8000";

function apiBaseUrl(): string {
  return import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL;
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function fetchComparison(
  baselineRunId: string,
  candidateRunId: string,
): Promise<RunComparison> {
  const url = `${apiBaseUrl()}/api/v1/comparisons/${encodeURIComponent(baselineRunId)}/${encodeURIComponent(candidateRunId)}`;
  const response = await fetch(url);
  if (!response.ok) {
    const detail = await response.text();
    throw new ApiError(response.status, detail || response.statusText);
  }
  return (await response.json()) as RunComparison;
}

export async function fetchTrace(executionId: string): Promise<TraceEvent[]> {
  const url = `${apiBaseUrl()}/api/v1/executions/${encodeURIComponent(executionId)}/trace`;
  const response = await fetch(url);
  if (!response.ok) {
    const detail = await response.text();
    throw new ApiError(response.status, detail || response.statusText);
  }
  return (await response.json()) as TraceEvent[];
}

export async function fetchExecution(executionId: string): Promise<TaskExecution> {
  const url = `${apiBaseUrl()}/api/v1/executions/${encodeURIComponent(executionId)}`;
  const response = await fetch(url);
  if (!response.ok) {
    const detail = await response.text();
    throw new ApiError(response.status, detail || response.statusText);
  }
  return (await response.json()) as TaskExecution;
}

export async function fetchTaskContract(taskId: string): Promise<TaskContract> {
  const url = `${apiBaseUrl()}/api/v1/tasks/${encodeURIComponent(taskId)}`;
  const response = await fetch(url);
  if (!response.ok) {
    const detail = await response.text();
    throw new ApiError(response.status, detail || response.statusText);
  }
  return (await response.json()) as TaskContract;
}
