// ============================================================
// ApprovalsPanel.tsx
//
// Displays pending approvals from GET /approvals/pending.
// Approve/Deny: requires decided_by_node_id + actor_id (humanNode).
// Always re-fetches after decision — never caches local state.
// ALLOW / DENY rendered verbatim from backend response.
// ============================================================

import React, { useEffect, useState, useCallback } from "react";
import { listPendingApprovals, approveRequest, denyRequest } from "../api/client";
import { useAppStore } from "../state/store";
import type { ApprovalDTO } from "../api/types";

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

interface ApprovalRowProps {
  approval: ApprovalDTO;
  humanNodeId: string;
  onDecision: () => void;
}

function ApprovalRow({ approval, humanNodeId, onDecision }: ApprovalRowProps) {
  const [acting, setActing] = useState<"approve" | "deny" | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);

  const handleApprove = async () => {
    setActing("approve");
    setFeedback(null);
    const result = await approveRequest({
      approval_id: approval.id,
      decided_by_node_id: humanNodeId,
      actor_id: humanNodeId,
      apply_immediately: true,
    });
    setActing(null);
    if (!result.ok) {
      setFeedback(`ERROR: ${result.error}`);
      return;
    }
    // Verbatim backend message
    setFeedback(result.data.message ?? (result.data.ok ? "APPROVED" : "FAILED"));
    setTimeout(onDecision, 800);
  };

  const handleDeny = async () => {
    setActing("deny");
    setFeedback(null);
    const result = await denyRequest({
      approval_id: approval.id,
      decided_by_node_id: humanNodeId,
      actor_id: humanNodeId,
      reason: "Denied via UI",
    });
    setActing(null);
    if (!result.ok) {
      setFeedback(`ERROR: ${result.error}`);
      return;
    }
    setFeedback(result.data.message ?? "DENIED");
    setTimeout(onDecision, 800);
  };

  return (
    <div className="approval-row">
      <div className="approval-meta">
        <span className="approval-kind">{approval.kind || "UNKNOWN"}</span>
        <span className="approval-ts">{formatDt(approval.created_at)}</span>
        <span className={`approval-status status-${approval.status}`}>{approval.status}</span>
      </div>
      {approval.summary && (
        <div className="approval-summary">{approval.summary}</div>
      )}
      <div className="approval-id">ID: {approval.id}</div>
      {feedback ? (
        <div className={`approval-feedback ${feedback.startsWith("ERROR") ? "feedback-error" : "feedback-ok"}`}>
          {feedback}
        </div>
      ) : (
        <div className="approval-actions">
          <button
            className="btn-approve"
            onClick={handleApprove}
            disabled={!!acting}
          >
            {acting === "approve" ? "…" : "APPROVE"}
          </button>
          <button
            className="btn-deny"
            onClick={handleDeny}
            disabled={!!acting}
          >
            {acting === "deny" ? "…" : "DENY"}
          </button>
        </div>
      )}
    </div>
  );
}

export function ApprovalsPanel() {
  const { humanNode } = useAppStore();
  const [approvals, setApprovals] = useState<ApprovalDTO[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchApprovals = useCallback(async () => {
    setLoading(true);
    setError(null);
    const result = await listPendingApprovals();
    setLoading(false);
    if (!result.ok) {
      setError(result.error);
      return;
    }
    setApprovals(result.data.approvals);
  }, []);

  useEffect(() => {
    fetchApprovals();
    const interval = setInterval(fetchApprovals, 15_000);
    return () => clearInterval(interval);
  }, [fetchApprovals]);

  return (
    <div className="panel approvals-panel">
      <div className="panel-header">
        <span className="panel-title">APPROVALS</span>
        <span className="panel-count">
          {approvals.length} PENDING
        </span>
        <button className="btn-ghost btn-sm" onClick={fetchApprovals} disabled={loading}>
          {loading ? "…" : "↻"}
        </button>
      </div>
      <div className="panel-body">
        {error && (
          <div className="panel-error">FETCH ERROR: {error}</div>
        )}
        {!error && approvals.length === 0 && !loading && (
          <div className="empty-state">No pending approvals.</div>
        )}
        {approvals.map((a) => (
          <ApprovalRow
            key={a.id}
            approval={a}
            humanNodeId={humanNode?.id ?? ""}
            onDecision={fetchApprovals}
          />
        ))}
      </div>
    </div>
  );
}
