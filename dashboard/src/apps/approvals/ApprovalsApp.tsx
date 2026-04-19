import React, { useEffect, useState, useCallback } from "react";
import { ApprovalsPanel } from "../../components/ApprovalsPanel";
import { listApprovalHistory } from "../../api/client";
import type { ApprovalDTO } from "../../api/types";

// ── History helpers ─────────────────────────────────────────

function formatDt(iso: string) {
  try {
    return new Date(iso).toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  } catch {
    return iso;
  }
}

function ApprovalsHistoryPanel() {
  const [history, setHistory] = useState<ApprovalDTO[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchHistory = useCallback(async () => {
    setLoading(true);
    setError(null);
    const result = await listApprovalHistory();
    setLoading(false);
    if (!result.ok) {
      setError(result.error);
      return;
    }
    // Most recent first
    setHistory([...result.data.approvals].reverse());
  }, []);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  return (
    <div className="panel approvals-panel">
      <div className="panel-header">
        <span className="panel-title">APPROVAL HISTORY</span>
        <span className="panel-count">{history.length} DECIDED</span>
        <button className="btn-ghost btn-sm" onClick={fetchHistory} disabled={loading}>
          {loading ? "…" : "↻"}
        </button>
      </div>
      <div className="panel-body">
        {error && <div className="panel-error">FETCH ERROR: {error}</div>}
        {!error && history.length === 0 && !loading && (
          <div className="empty-state">No decided approvals yet.</div>
        )}
        {history.map((a) => (
          <div key={a.id} className="approval-row">
            <div className="approval-meta">
              <span className="approval-kind">{a.kind || "UNKNOWN"}</span>
              <span className="approval-ts">{formatDt(a.created_at)}</span>
              <span className={`approval-status status-${a.status}`}>{a.status}</span>
            </div>
            {a.summary && <div className="approval-summary">{a.summary}</div>}
            {a.decided_by_node_id && (
              <div className="approval-id">
                Decided by: {a.decided_by_node_id}
                {a.reason ? ` — ${a.reason}` : ""}
              </div>
            )}
            <div className="approval-id">ID: {a.id}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── App dispatcher ──────────────────────────────────────────

interface Props { activeView: string; }

export function ApprovalsApp({ activeView }: Props) {
  switch (activeView) {
    case "pending": return <ApprovalsPanel />;
    case "history": return <ApprovalsHistoryPanel />;
    default:        return <ApprovalsPanel />;
  }
}
