import { useState } from "react";
import ComparisonPage from "./components/ComparisonPage";
import TaskDetailPage from "./components/TaskDetailPage";
import TraceReplayPage from "./components/TraceReplayPage";
import "./App.css";

type Tab = "comparison" | "trace" | "task";

interface TraceRequest {
  executionId: string;
  highlightEventId: string | null;
}

function App() {
  const [tab, setTab] = useState<Tab>("comparison");
  const [traceRequest, setTraceRequest] = useState<TraceRequest | null>(null);
  const [taskDetailExecutionId, setTaskDetailExecutionId] = useState<string | null>(null);

  function handleViewTrace(executionId: string, highlightEventId: string | null) {
    setTraceRequest({ executionId, highlightEventId });
    setTab("trace");
  }

  function handleViewTaskDetail(executionId: string) {
    setTaskDetailExecutionId(executionId);
    setTab("task");
  }

  return (
    <>
      <nav className="tabs">
        <button type="button" className={tab === "comparison" ? "tab-active" : ""} onClick={() => setTab("comparison")}>
          Comparison
        </button>
        <button type="button" className={tab === "task" ? "tab-active" : ""} onClick={() => setTab("task")}>
          Task Detail
        </button>
        <button type="button" className={tab === "trace" ? "tab-active" : ""} onClick={() => setTab("trace")}>
          Trace Replay
        </button>
      </nav>

      {tab === "comparison" && (
        <ComparisonPage onViewTrace={handleViewTrace} onViewTaskDetail={handleViewTaskDetail} />
      )}
      {tab === "task" && (
        <TaskDetailPage
          key={taskDetailExecutionId ?? "manual"}
          initialExecutionId={taskDetailExecutionId ?? undefined}
          onViewTrace={handleViewTrace}
        />
      )}
      {tab === "trace" && (
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
