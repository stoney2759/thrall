import React, { useState, useCallback, useEffect } from "react";
import { OrgTreePanel } from "../../components/OrgTreePanel";
import { NodeDetailSidebar } from "../../components/NodeDetailSidebar";
import { PlaceholderView } from "../../components/PlaceholderView";
import { WorkspaceApp } from "../workspace/WorkspaceApp";
import { useAppStore } from "../../state/store";
import { listNodes, resetOrg } from "../../api/client";
import type { NodeDTO } from "../../api/types";

interface Props { activeView: string; }

const DEFAULT_TREE_WIDTH = 300;

// ── Reset Org Modal ─────────────────────────────────────────

interface ResetOrgModalProps {
  onClose: () => void;
  onReset: () => void;
}

function ResetOrgModal({ onClose, onReset }: ResetOrgModalProps) {
  const [mode, setMode] = useState<"keep_bootstrap" | "blank">("keep_bootstrap");
  const [confirmText, setConfirmText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const REQUIRED = "DELETE_ORG";
  const isValid = confirmText === REQUIRED;

  const handleSubmit = async () => {
    if (!isValid || submitting) return;
    setSubmitting(true);
    setError(null);

    const result = await resetOrg({ mode, confirm_text: confirmText });

    setSubmitting(false);
    if (!result.ok) {
      setError(result.error);
      return;
    }
    onReset();
    onClose();
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-box modal-box-danger" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header modal-header-danger">
          <span className="modal-title">⚠ RESET ORG</span>
          <button className="btn-close" onClick={onClose} disabled={submitting}>✕</button>
        </div>

        {error && <div className="modal-error">✕ {error}</div>}

        <div className="modal-body">
          <div className="reset-warning-text">
            This will permanently delete org nodes. This action cannot be undone.
          </div>

          <div className="form-field">
            <label>RESET MODE</label>
            <div className="reset-mode-options">
              <label className={`reset-mode-opt ${mode === "keep_bootstrap" ? "selected" : ""}`}>
                <input
                  type="radio"
                  name="reset-mode"
                  value="keep_bootstrap"
                  checked={mode === "keep_bootstrap"}
                  onChange={() => setMode("keep_bootstrap")}
                  disabled={submitting}
                />
                <div>
                  <div className="reset-mode-label">Keep Bootstrap</div>
                  <div className="reset-mode-desc">Removes all nodes except Human and Thrall (COO)</div>
                </div>
              </label>
              <label className={`reset-mode-opt ${mode === "blank" ? "selected" : ""}`}>
                <input
                  type="radio"
                  name="reset-mode"
                  value="blank"
                  checked={mode === "blank"}
                  onChange={() => setMode("blank")}
                  disabled={submitting}
                />
                <div>
                  <div className="reset-mode-label">Blank</div>
                  <div className="reset-mode-desc">Removes ALL nodes. Org must be re-bootstrapped.</div>
                </div>
              </label>
            </div>
          </div>

          <div className="form-field">
            <label>
              TYPE <span className="confirm-required-text">DELETE_ORG</span> TO CONFIRM
            </label>
            <input
              type="text"
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              placeholder="DELETE_ORG"
              autoComplete="off"
              autoFocus
              disabled={submitting}
              className={confirmText.length > 0 && !isValid ? "input-invalid" : ""}
              onKeyDown={(e) => e.key === "Enter" && isValid && handleSubmit()}
            />
            {confirmText.length > 0 && !isValid && (
              <div className="input-hint">Must match exactly: DELETE_ORG</div>
            )}
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn-ghost" onClick={onClose} disabled={submitting}>CANCEL</button>
          <button
            className="btn-delete-confirm"
            onClick={handleSubmit}
            disabled={!isValid || submitting}
          >
            {submitting ? "RESETTING…" : "RESET ORG"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Hierarchy View ──────────────────────────────────────────

function HierarchyView() {
  const store = useAppStore();
  const [selectedNode, setSelectedNode] = useState<NodeDTO | null>(null);
  const [treeWidth, setTreeWidth] = useState(DEFAULT_TREE_WIDTH);
  const [showReset, setShowReset] = useState(false);

  const refresh = useCallback(async () => {
    const r = await listNodes();
    if (r.ok) store.setOrgNodes(r.data.nodes);
  }, [store.setOrgNodes]);

  useEffect(() => { refresh(); }, [refresh]);

  const handleDeleted = useCallback(async () => {
    setSelectedNode(null);
    await refresh();
  }, [refresh]);

  const handleReset = useCallback(async () => {
    setSelectedNode(null);
    await refresh();
  }, [refresh]);

  return (
    <>
      <div className="org-layout">
        <OrgTreePanel
          nodes={store.orgNodes}
          selectedNodeId={selectedNode?.id ?? null}
          onSelectNode={setSelectedNode}
          onRefresh={refresh}
          onResetOrg={() => setShowReset(true)}
          width={treeWidth}
          onWidthChange={setTreeWidth}
        />

        {selectedNode && (
          <div className="org-detail-wrap">
            <NodeDetailSidebar
              node={selectedNode}
              onClose={() => setSelectedNode(null)}
              onDeleted={handleDeleted}
            />
          </div>
        )}
      </div>

      {showReset && (
        <ResetOrgModal
          onClose={() => setShowReset(false)}
          onReset={handleReset}
        />
      )}
    </>
  );
}

// ── Nodes Table View ────────────────────────────────────────

function NodesView() {
  const store = useAppStore();

  const refresh = useCallback(async () => {
    const r = await listNodes();
    if (r.ok) store.setOrgNodes(r.data.nodes);
  }, [store.setOrgNodes]);

  useEffect(() => { refresh(); }, [refresh]);

  return (
    <div className="nodes-table-view">
      <div className="view-header">
        <span className="view-title">ALL NODES</span>
        <span className="view-count">{store.orgNodes.length} total</span>
        <button className="btn-ghost btn-sm" onClick={refresh}>↻ Refresh</button>
      </div>
      <table className="data-table">
        <thead>
          <tr>
            <th>NAME</th>
            <th>TYPE</th>
            <th>ROLE</th>
            <th>PARENT</th>
            <th>STATUS</th>
          </tr>
        </thead>
        <tbody>
          {store.orgNodes.map((node) => (
            <tr key={node.id}>
              <td className="td-primary">{node.name}</td>
              <td><span className={`node-badge node-${node.type.toLowerCase()}`}>{node.type}</span></td>
              <td className="td-dim">{node.role_title || "—"}</td>
              <td className="td-mono td-dim">{node.parent_id ? node.parent_id.slice(0, 12) + "…" : "—"}</td>
              <td>
                <span className={node.enabled !== false ? "status-enabled" : "status-disabled"}>
                  {node.enabled !== false ? "ENABLED" : "DISABLED"}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function OrgApp({ activeView }: Props) {
  switch (activeView) {
    case "hierarchy": return <HierarchyView />;
    case "nodes":     return <NodesView />;
    case "workspace": return <WorkspaceApp activeView="browse" />;
    case "policies":  return <PlaceholderView app="Org" view="Policies" message="Policy management coming soon." />;
    default:          return <HierarchyView />;
  }
}
