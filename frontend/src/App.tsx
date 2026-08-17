import { useState } from "react";
import ComparisonPage from "./components/ComparisonPage";
import JudgeResultsPage from "./components/JudgeResultsPage";
import TaskDetailPage from "./components/TaskDetailPage";
import TraceReplayPage from "./components/TraceReplayPage";
import "./App.css";

type Tab = "comparison" | "trace" | "task" | "judges";

interface TraceRequest {
  executionId: string;
  highlightEventId: string | null;
}

function App() {
  const [tab, setTab] = useState<Tab>("comparison");
  const [traceRequest, setTraceRequest] = useState<TraceRequest | null>(null);
  const [taskDetailExecutionId, setTaskDetailExecutionId] = useState<string | null>(null);
  const [judgeResultsExecutionId, setJudgeResultsExecutionId] = useState<string | null>(null);

  function handleViewTrace(executionId: string, highlightEventId: string | null) {
    setTraceRequest({ executionId, highlightEventId });
    setTab("trace");
  }

  function handleViewTaskDetail(executionId: string) {
    setTaskDetailExecutionId(executionId);
    setTab("task");
  }

  function handleViewJudgeResults(executionId: string) {
    setJudgeResultsExecutionId(executionId);
    setTab("judges");
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
        <button type="button" className={tab === "judges" ? "tab-active" : ""} onClick={() => setTab("judges")}>
          Judge Results
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
          onViewJudgeResults={handleViewJudgeResults}
        />
      )}
      {tab === "judges" && (
        <JudgeResultsPage
          key={judgeResultsExecutionId ?? "manual"}
          initialExecutionId={judgeResultsExecutionId ?? undefined}
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
