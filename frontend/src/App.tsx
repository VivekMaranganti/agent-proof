import { useState } from "react";
import ComparisonPage from "./components/ComparisonPage";
import TraceReplayPage from "./components/TraceReplayPage";
import "./App.css";

type Tab = "comparison" | "trace";

interface TraceRequest {
  executionId: string;
  highlightEventId: string | null;
}

function App() {
  const [tab, setTab] = useState<Tab>("comparison");
  const [traceRequest, setTraceRequest] = useState<TraceRequest | null>(null);

  function handleViewTrace(executionId: string, highlightEventId: string | null) {
    setTraceRequest({ executionId, highlightEventId });
    setTab("trace");
  }

  return (
    <>
      <nav className="tabs">
        <button type="button" className={tab === "comparison" ? "tab-active" : ""} onClick={() => setTab("comparison")}>
          Comparison
        </button>
        <button type="button" className={tab === "trace" ? "tab-active" : ""} onClick={() => setTab("trace")}>
          Trace Replay
        </button>
      </nav>

      {tab === "comparison" ? (
        <ComparisonPage onViewTrace={handleViewTrace} />
      ) : (
        <TraceReplayPage
          key={traceRequest ? `${traceRequest.executionId}:${traceRequest.highlightEventId ?? ""}` : "manual"}
          initialExecutionId={traceRequest?.executionId}
          initialHighlightEventId={traceRequest?.highlightEventId ?? undefined}
        />
      )}
    </>
  );
}

export default App;
