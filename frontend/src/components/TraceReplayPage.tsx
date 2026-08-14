import { useEffect, useState, type FormEvent } from "react";
import { ApiError, fetchTrace } from "../api/client";
import type { TraceEvent } from "../api/types";

const EVENT_LABEL: Record<TraceEvent["event_type"], string> = {
  model_request: "Model request",
  model_response: "Model response",
  tool_call: "Tool call",
  tool_result: "Tool result",
  retry: "Retry",
  error: "Error",
  final_answer: "Final answer",
};

function truncate(text: string, max = 80): string {
  return text.length > max ? `${text.slice(0, max)}…` : text;
}

function describeStep(event: TraceEvent): string {
  const payload = event.payload;
  switch (event.event_type) {
    case "model_request":
      return `${payload.model} · ${(payload.messages as unknown[]).length} message(s)`;
    case "model_response": {
      const toolCalls = payload.tool_calls as unknown[];
      if (toolCalls.length > 0) return `requested ${toolCalls.length} tool call(s)`;
      return payload.content ? truncate(String(payload.content)) : `finished: ${payload.finish_reason}`;
    }
    case "tool_call":
      return `${payload.service}.${payload.operation}(${JSON.stringify(payload.arguments)})`;
    case "tool_result":
      return truncate(JSON.stringify(payload.result));
    case "retry":
      return `attempt ${payload.attempt}: ${payload.reason}`;
    case "error":
      return `${payload.error_type}: ${payload.message}`;
    case "final_answer":
      return truncate(String(payload.content));
    default:
      return "";
  }
}

function StepDetail({ event }: { event: TraceEvent }) {
  return (
    <div className="step-detail">
      <div className="step-detail-meta">
        <span>seq {event.sequence_no}</span>
        <span>{event.id}</span>
        {event.duration_ms !== null && <span>{event.duration_ms}ms</span>}
        {event.parent_event_id && <span>parent {event.parent_event_id}</span>}
      </div>
      <pre>{JSON.stringify(event.payload, null, 2)}</pre>
    </div>
  );
}

export interface TraceReplayPageProps {
  initialExecutionId?: string;
  initialHighlightEventId?: string;
}

export default function TraceReplayPage({ initialExecutionId, initialHighlightEventId }: TraceReplayPageProps) {
  const [executionId, setExecutionId] = useState(initialExecutionId ?? "");
  const [highlightEventId, setHighlightEventId] = useState(initialHighlightEventId ?? "");
  const [events, setEvents] = useState<TraceEvent[] | null>(null);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function loadTrace(id: string, highlightId: string) {
    if (!id.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const result = await fetchTrace(id.trim());
      setEvents(result);
      const highlightIndex = highlightId ? result.findIndex((event) => event.id === highlightId) : -1;
      setSelectedIndex(highlightIndex >= 0 ? highlightIndex : 0);
    } catch (err) {
      setEvents(null);
      setError(err instanceof ApiError ? err.message : "Could not load this trace.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (initialExecutionId) {
      void loadTrace(initialExecutionId, initialHighlightEventId ?? "");
    }
    // Only run for the initial deep-link; App.tsx remounts this component (via key)
    // whenever a new deep link is requested, so this never needs to re-run itself.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    void loadTrace(executionId, highlightEventId);
  }

  const selected = events?.[selectedIndex] ?? null;
  const highlightedId = highlightEventId.trim() || initialHighlightEventId;

  return (
    <section className="trace-replay-page">
      <h1>Trace replay</h1>
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
        <label>
          Highlight event ID (optional)
          <input
            value={highlightEventId}
            onChange={(e) => setHighlightEventId(e.target.value)}
            placeholder="00000000-0000-0000-0000-000000000000"
            spellCheck={false}
          />
        </label>
        <button type="submit" disabled={loading}>
          {loading ? "Loading…" : "Load trace"}
        </button>
      </form>

      {error && <p className="error">{error}</p>}

      {events && events.length === 0 && <p>This execution has no recorded trace events.</p>}

      {events && events.length > 0 && (
        <div className="trace-replay-body">
          <div className="trace-nav">
            <button type="button" onClick={() => setSelectedIndex((i) => Math.max(0, i - 1))} disabled={selectedIndex === 0}>
              ← Prev
            </button>
            <span>
              Step {selectedIndex + 1} of {events.length}
            </span>
            <button
              type="button"
              onClick={() => setSelectedIndex((i) => Math.min(events.length - 1, i + 1))}
              disabled={selectedIndex === events.length - 1}
            >
              Next →
            </button>
          </div>

          <ol className="trace-steps">
            {events.map((event, index) => (
              <li key={event.id}>
                <button
                  type="button"
                  className={
                    "trace-step" +
                    (index === selectedIndex ? " trace-step-selected" : "") +
                    (event.id === highlightedId ? " trace-step-highlighted" : "")
                  }
                  onClick={() => setSelectedIndex(index)}
                >
                  <span className={`event-badge event-${event.event_type}`}>{EVENT_LABEL[event.event_type]}</span>
                  <span className="trace-step-summary">{describeStep(event)}</span>
                </button>
              </li>
            ))}
          </ol>

          {selected && <StepDetail event={selected} />}
        </div>
      )}
    </section>
  );
}
