import { useEffect, useState, type FormEvent } from "react";
import { ApiError, fetchJudgeVerdicts } from "../api/client";
import type { JudgeLabel, JudgeVerdict } from "../api/types";

const LABEL_TEXT: Record<JudgeLabel, string> = {
  pass: "Pass",
  fail: "Fail",
  uncertain: "Uncertain",
};

function formatJudgeName(judgeName: string): string {
  return judgeName
    .split("_")
    .map((word) => word[0].toUpperCase() + word.slice(1))
    .join(" ");
}

function VerdictCard({ verdict }: { verdict: JudgeVerdict }) {
  return (
    <div className="verdict-card">
      <div className="verdict-card-header">
        <span className="verdict-judge-name">{formatJudgeName(verdict.judge_name)}</span>
        <span className={`judge-label-badge judge-label-${verdict.label}`}>{LABEL_TEXT[verdict.label]}</span>
      </div>
      <div className="verdict-meta">
        <span>confidence {Math.round(verdict.confidence * 100)}%</span>
        <span>rubric v{verdict.rubric_version}</span>
      </div>
      <p className="verdict-rationale">{verdict.rationale}</p>
    </div>
  );
}

export interface JudgeResultsPageProps {
  initialExecutionId?: string;
}

export default function JudgeResultsPage({ initialExecutionId }: JudgeResultsPageProps) {
  const [executionId, setExecutionId] = useState(initialExecutionId ?? "");
  const [verdicts, setVerdicts] = useState<JudgeVerdict[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function loadVerdicts(id: string) {
    if (!id.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const result = await fetchJudgeVerdicts(id.trim());
      setVerdicts(result);
    } catch (err) {
      setVerdicts(null);
      setError(err instanceof ApiError ? err.message : "Could not load judge results for this execution.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (initialExecutionId) {
      void loadVerdicts(initialExecutionId);
    }
    // Only run for the initial deep-link; App.tsx remounts this component (via key)
    // whenever a new deep link is requested, so this never needs to re-run itself.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    void loadVerdicts(executionId);
  }

  const distinctLabels = verdicts ? new Set(verdicts.map((verdict) => verdict.label)) : new Set();
  const judgesDisagree = distinctLabels.size > 1;

  return (
    <section className="judge-results-page">
      <h1>Judge results</h1>
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

      {verdicts && verdicts.length === 0 && (
        <p>
          No judge verdicts recorded for this execution. Judges are opt-in per run, so most executions
          won't have any yet.
        </p>
      )}

      {verdicts && verdicts.length > 0 && (
        <>
          {judgesDisagree && (
            <p className="disagreement-banner">⚠ Judges disagree on this execution — labels aren't unanimous.</p>
          )}
          <div className="verdict-cards">
            {verdicts.map((verdict) => (
              <VerdictCard key={verdict.id} verdict={verdict} />
            ))}
          </div>
        </>
      )}
    </section>
  );
}
