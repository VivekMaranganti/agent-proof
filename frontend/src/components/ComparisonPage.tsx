import { useState, type FormEvent } from "react";
import { ApiError, fetchComparison } from "../api/client";
import type { PairedTaskComparison, RunComparison } from "../api/types";

const DISPOSITION_LABEL: Record<PairedTaskComparison["disposition"], string> = {
  stable_pass: "Stable pass",
  stable_failure: "Stable failure",
  improvement: "Improvement",
  regression: "Regression",
  indeterminate: "Indeterminate",
};

function passRate(results: PairedTaskComparison[], pick: (r: PairedTaskComparison) => boolean | null): string {
  if (results.length === 0) return "—";
  const known = results.filter((r) => pick(r) !== null);
  if (known.length === 0) return "—";
  const passed = known.filter((r) => pick(r) === true).length;
  return `${Math.round((passed / known.length) * 100)}%`;
}

function DeltaCell({ value, unit, lowerIsBetter }: { value: number | null; unit: string; lowerIsBetter: boolean }) {
  if (value === null) return <span className="delta-flat">—</span>;

  const isWorse = lowerIsBetter ? value > 0 : value < 0;
  const isBetter = lowerIsBetter ? value < 0 : value > 0;
  const cls = isWorse ? "delta-worse" : isBetter ? "delta-better" : "delta-flat";
  const sign = value > 0 ? "+" : "";

  return (
    <span className={cls}>
      {sign}
      {value}
      {unit}
    </span>
  );
}

function PassBadge({
  passed,
  executionId,
  onViewTaskDetail,
}: {
  passed: boolean | null;
  executionId: string;
  onViewTaskDetail: (executionId: string) => void;
}) {
  return (
    <button
      type="button"
      className={`pass-badge-button pass-badge ${passed === null ? "pass-unknown" : passed ? "pass-yes" : "pass-no"}`}
      onClick={() => onViewTaskDetail(executionId)}
      title="View task detail"
    >
      {passed === null ? "—" : passed ? "Pass" : "Fail"}
    </button>
  );
}

function AttributionNote({
  comparison,
  onViewTrace,
}: {
  comparison: PairedTaskComparison;
  onViewTrace: (executionId: string, highlightEventId: string | null) => void;
}) {
  if (!comparison.attribution) return null;
  const { divergence_type, baseline_event_id, candidate_event_id } = comparison.attribution;
  return (
    <details className="attribution">
      <summary>First divergence: {divergence_type.replace(/_/g, " ")}</summary>
      <dl>
        <dt>Baseline event</dt>
        <dd>{baseline_event_id ?? "(none — run ended early)"}</dd>
        <dt>Candidate event</dt>
        <dd>{candidate_event_id ?? "(none — run ended early)"}</dd>
      </dl>
      <div className="attribution-actions">
        <button type="button" onClick={() => onViewTrace(comparison.baseline_execution_id, baseline_event_id)}>
          View baseline trace
        </button>
        <button type="button" onClick={() => onViewTrace(comparison.candidate_execution_id, candidate_event_id)}>
          View candidate trace
        </button>
      </div>
    </details>
  );
}

export interface ComparisonPageProps {
  onViewTrace: (executionId: string, highlightEventId: string | null) => void;
  onViewTaskDetail: (executionId: string) => void;
}

export default function ComparisonPage({ onViewTrace, onViewTaskDetail }: ComparisonPageProps) {
  const [baselineRunId, setBaselineRunId] = useState("");
  const [candidateRunId, setCandidateRunId] = useState("");
  const [comparison, setComparison] = useState<RunComparison | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!baselineRunId.trim() || !candidateRunId.trim()) return;

    setLoading(true);
    setError(null);
    try {
      const result = await fetchComparison(baselineRunId.trim(), candidateRunId.trim());
      setComparison(result);
    } catch (err) {
      setComparison(null);
      setError(err instanceof ApiError ? err.message : "Could not load this comparison.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="comparison-page">
      <h1>Run comparison</h1>
      <form className="comparison-form" onSubmit={handleSubmit}>
        <label>
          Baseline run ID
          <input
            value={baselineRunId}
            onChange={(e) => setBaselineRunId(e.target.value)}
            placeholder="00000000-0000-0000-0000-000000000000"
            spellCheck={false}
          />
        </label>
        <label>
          Candidate run ID
          <input
            value={candidateRunId}
            onChange={(e) => setCandidateRunId(e.target.value)}
            placeholder="00000000-0000-0000-0000-000000000000"
            spellCheck={false}
          />
        </label>
        <button type="submit" disabled={loading}>
          {loading ? "Comparing…" : "Compare"}
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      {comparison && (
        <>
          <dl className="summary">
            <div>
              <dt>Compared tasks</dt>
              <dd>{comparison.compared_tasks}</dd>
            </div>
            <div>
              <dt>Regressions</dt>
              <dd className={comparison.regressions > 0 ? "delta-worse" : undefined}>{comparison.regressions}</dd>
            </div>
            <div>
              <dt>Improvements</dt>
              <dd className={comparison.improvements > 0 ? "delta-better" : undefined}>{comparison.improvements}</dd>
            </div>
            <div>
              <dt>Baseline pass rate</dt>
              <dd>{passRate(comparison.results, (r) => r.baseline_passed)}</dd>
            </div>
            <div>
              <dt>Candidate pass rate</dt>
              <dd>{passRate(comparison.results, (r) => r.candidate_passed)}</dd>
            </div>
          </dl>

          <table className="results-table">
            <thead>
              <tr>
                <th>Task</th>
                <th>Disposition</th>
                <th>Baseline</th>
                <th>Candidate</th>
                <th>Latency Δ</th>
                <th>Cost Δ</th>
              </tr>
            </thead>
            <tbody>
              {comparison.results.map((result) => (
                <tr key={result.task_id} data-disposition={result.disposition}>
                  <td className="task-id">
                    {result.task_id}
                    <AttributionNote comparison={result} onViewTrace={onViewTrace} />
                  </td>
                  <td>
                    <span className={`disposition-badge disposition-${result.disposition}`}>
                      {DISPOSITION_LABEL[result.disposition]}
                    </span>
                  </td>
                  <td>
                    <PassBadge
                      passed={result.baseline_passed}
                      executionId={result.baseline_execution_id}
                      onViewTaskDetail={onViewTaskDetail}
                    />
                  </td>
                  <td>
                    <PassBadge
                      passed={result.candidate_passed}
                      executionId={result.candidate_execution_id}
                      onViewTaskDetail={onViewTaskDetail}
                    />
                  </td>
                  <td>
                    <DeltaCell value={result.latency_delta_ms} unit="ms" lowerIsBetter />
                  </td>
                  <td>
                    <DeltaCell value={result.cost_delta_usd} unit="$" lowerIsBetter />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </section>
  );
}
