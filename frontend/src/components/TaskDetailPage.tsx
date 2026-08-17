import { useEffect, useState, type FormEvent } from "react";
import { ApiError, fetchExecution, fetchTaskContract } from "../api/client";
import type {
  ExecutionStatus,
  ExpectedActionContract,
  ForbiddenActionContract,
  TaskContract,
  TaskExecution,
} from "../api/types";

const STATUS_LABEL: Record<ExecutionStatus, string> = {
  pending: "Pending",
  running: "Running",
  passed: "Passed",
  failed: "Failed",
  errored: "Errored",
};

function ActionLine({ action }: { action: ExpectedActionContract | ForbiddenActionContract }) {
  return (
    <code>
      {action.service}.{action.operation}({JSON.stringify(action.arguments)})
    </code>
  );
}

function MismatchList({ title, items, emptyLabel }: { title: string; items: string[]; emptyLabel: string }) {
  return (
    <div className="mismatch-group">
      <h3>{title}</h3>
      {items.length === 0 ? (
        <p className="mismatch-clean">✓ {emptyLabel}</p>
      ) : (
        <ul className="mismatch-list">
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export interface TaskDetailPageProps {
  initialExecutionId?: string;
  onViewTrace: (executionId: string, highlightEventId: string | null) => void;
}

export default function TaskDetailPage({ initialExecutionId, onViewTrace }: TaskDetailPageProps) {
  const [executionId, setExecutionId] = useState(initialExecutionId ?? "");
  const [execution, setExecution] = useState<TaskExecution | null>(null);
  const [contract, setContract] = useState<TaskContract | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function loadDetail(id: string) {
    if (!id.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const loadedExecution = await fetchExecution(id.trim());
      const loadedContract = await fetchTaskContract(loadedExecution.task_id);
      setExecution(loadedExecution);
      setContract(loadedContract);
    } catch (err) {
      setExecution(null);
      setContract(null);
      setError(err instanceof ApiError ? err.message : "Could not load this execution.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (initialExecutionId) {
      void loadDetail(initialExecutionId);
    }
    // Only run for the initial deep-link; App.tsx remounts this component (via key)
    // whenever a new deep link is requested, so this never needs to re-run itself.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    void loadDetail(executionId);
  }

  return (
    <section className="task-detail-page">
      <h1>Task detail</h1>
      <form className="comparison-form" onSubmit={handleSubmit}>
        <label>
          Execution ID
          <input
            value={executionId}
            onChange={(e) => setExecutionId(e.target.value)}
            placeholder="00000000-0000-0000-0000-000000000000"
            spellCheck={false}
          />
        </label>
        <button type="submit" disabled={loading}>
          {loading ? "Loading…" : "Load"}
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      {execution && contract && (
        <>
          <div className="task-detail-header">
            <span className={`execution-status-badge execution-status-${execution.status}`}>
              {STATUS_LABEL[execution.status]}
            </span>
            <code className="task-id">{execution.task_id}</code>
            <button type="button" onClick={() => onViewTrace(execution.id, null)}>
              View trace
            </button>
          </div>

          <dl className="summary">
            <div>
              <dt>Latency</dt>
              <dd>{execution.latency_ms ?? "—"}ms</dd>
            </div>
            <div>
              <dt>Tokens (in/out)</dt>
              <dd>
                {execution.input_tokens ?? "—"} / {execution.output_tokens ?? "—"}
              </dd>
            </div>
            <div>
              <dt>Cost</dt>
              <dd>${execution.estimated_cost_usd ?? "—"}</dd>
            </div>
          </dl>

          <h2>Contract score</h2>
          <MismatchList
            title="Expected actions"
            items={execution.missing_expected_actions}
            emptyLabel="Every expected action was taken."
          />
          <MismatchList
            title="Forbidden actions"
            items={execution.forbidden_actions_seen}
            emptyLabel="No forbidden action was taken."
          />
          <MismatchList
            title="Final state"
            items={execution.final_state_mismatches}
            emptyLabel="Final state matched the contract."
          />

          <h2>Task input</h2>
          <p className="task-input">{contract.input}</p>

          <h2>Final response</h2>
          <p className="task-input">{execution.final_output ?? "(no final response provided)"}</p>

          <h2>Contract</h2>
          <div className="contract-columns">
            <div>
              <h3>Expected actions</h3>
              <ul className="action-list">
                {contract.expected_actions.map((action, index) => (
                  <li key={index}>
                    <ActionLine action={action} />
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h3>Forbidden actions</h3>
              <ul className="action-list">
                {contract.forbidden_actions.map((action, index) => (
                  <li key={index}>
                    <ActionLine action={action} />
                    <p className="forbidden-reason">{action.reason}</p>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
