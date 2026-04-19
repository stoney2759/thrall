// ============================================================
// NodeDetailSidebar.tsx
//
// Read-only display of a selected NodeDTO.
// Delete with two-stage confirmation + cascade option.
// HUMAN and COO nodes are protected — no delete shown.
// ============================================================

import React, { useState } from "react";
import type { NodeDTO } from "../api/types";
import { deleteNode } from "../api/client";

interface NodeDetailSidebarProps {
  node: NodeDTO | null;
  onClose: () => void;
  onDeleted: () => void;
}

const TYPE_DESCRIPTIONS: Record<string, string> = {
  HUMAN: "Root authority node. All governance flows from here.",
  COO: "Thrall node. Governed AI COO operating under Human authority.",
  CHIEF: "Chief node. Department head reporting to COO.",
  DEPARTMENT: "Department node. Operational unit under a Chief.",
  AGENT: "Agent node. Task executor under a Department or Chief.",
};

const PROTECTED_TYPES = new Set(["HUMAN", "COO"]);

type DeleteStage = "idle" | "confirm" | "deleting";

export function NodeDetailSidebar({ node, onClose, onDeleted }: NodeDetailSidebarProps) {
  const [deleteStage, setDeleteStage] = useState<DeleteStage>("idle");
  const [cascade, setCascade] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  if (!node) return null;

  const canDelete = !PROTECTED_TYPES.has(node.type);

  const resetDelete = () => {
    setDeleteStage("idle");
    setDeleteError(null);
    setCascade(false);
  };

  const handleClose = () => {
    resetDelete();
    onClose();
  };

  const handleDeleteClick = () => {
    setDeleteStage("confirm");
    setDeleteError(null);
    setCascade(false);
  };

  const handleConfirmDelete = async () => {
    setDeleteStage("deleting");
    setDeleteError(null);

    const result = await deleteNode(node.id, cascade);

    if (!result.ok) {
      const msg = result.error.toLowerCase();
      const isChildrenError =
        msg.includes("child") ||
        msg.includes("subtree") ||
        msg.includes("cascade") ||
        msg.includes("has children");

      setDeleteError(
        isChildrenError
          ? "This node has children. Enable cascade to delete the entire subtree."
          : result.error
      );
      setDeleteStage("confirm");
      if (isChildrenError) setCascade(true);
      return;
    }

    onDeleted();
    onClose();
  };

  return (
    <div className="node-sidebar">
      <div className="sidebar-header">
        <span className="sidebar-title">NODE DETAIL</span>
        <button className="btn-close" onClick={handleClose} aria-label="Close">✕</button>
      </div>

      <div className="sidebar-body">
        <div className="detail-row">
          <span className="detail-label">NAME</span>
          <span className="detail-value">{node.name}</span>
        </div>
        <div className="detail-row">
          <span className="detail-label">TYPE</span>
          <span className="detail-value">
            <span className={`node-badge node-${node.type.toLowerCase()}`}>{node.type}</span>
          </span>
        </div>
        {node.role_title && (
          <div className="detail-row">
            <span className="detail-label">ROLE</span>
            <span className="detail-value">{node.role_title}</span>
          </div>
        )}
        <div className="detail-row">
          <span className="detail-label">ID</span>
          <span className="detail-value detail-id">{node.id}</span>
        </div>
        {node.parent_id && (
          <div className="detail-row">
            <span className="detail-label">PARENT</span>
            <span className="detail-value detail-id">{node.parent_id}</span>
          </div>
        )}
        <div className="detail-row">
          <span className="detail-label">STATUS</span>
          <span className={`detail-value ${node.enabled !== false ? "status-enabled" : "status-disabled"}`}>
            {node.enabled !== false ? "ENABLED" : "DISABLED"}
          </span>
        </div>
        {node.description && (
          <div className="detail-row detail-row-block">
            <span className="detail-label">DESCRIPTION</span>
            <span className="detail-value">{node.description}</span>
          </div>
        )}

        <div className="detail-type-desc">
          {TYPE_DESCRIPTIONS[node.type] ?? ""}
        </div>

        {/* ── Delete Zone ───────────────────────────────── */}
        {canDelete && (
          <div className="delete-zone">
            {deleteStage === "idle" && (
              <button className="btn-delete-node" onClick={handleDeleteClick}>
                DELETE NODE
              </button>
            )}

            {(deleteStage === "confirm" || deleteStage === "deleting") && (
              <div className="delete-confirm-box">
                <div className="delete-confirm-title">⚠ DELETE {node.name}?</div>
                <div className="delete-confirm-desc">
                  This action cannot be undone. The node will be permanently removed.
                </div>

                {deleteError && (
                  <div className="delete-error">{deleteError}</div>
                )}

                <label className="cascade-toggle">
                  <input
                    type="checkbox"
                    checked={cascade}
                    onChange={(e) => setCascade(e.target.checked)}
                    disabled={deleteStage === "deleting"}
                  />
                  <span>Cascade — also delete all child nodes</span>
                </label>

                {cascade && (
                  <div className="cascade-warning">
                    All departments, agents, and sub-nodes under {node.name} will also be deleted.
                  </div>
                )}

                <div className="delete-confirm-actions">
                  <button
                    className="btn-ghost btn-sm"
                    onClick={resetDelete}
                    disabled={deleteStage === "deleting"}
                  >
                    CANCEL
                  </button>
                  <button
                    className="btn-delete-confirm"
                    onClick={handleConfirmDelete}
                    disabled={deleteStage === "deleting"}
                  >
                    {deleteStage === "deleting" ? "DELETING…" : "CONFIRM DELETE"}
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {!canDelete && (
          <div className="delete-protected">
            <span>⊘</span> {node.type} nodes are protected and cannot be deleted.
          </div>
        )}
      </div>
    </div>
  );
}
