// ============================================================
// OrgTreePanel.tsx
//
// Org hierarchy tree with:
// - + add buttons per node (COO → Chief, Chief → Dept/Agent, Dept → Agent)
// - Inline creation modal
// - Resizable panel width via drag handle
// - Reset Org button in panel header
// ============================================================

import React, { useMemo, useState, useRef, useCallback } from "react";
import type { NodeDTO } from "../api/types";
import { addChief, addDepartment, addAgent } from "../api/client";

const NODE_TYPE_LABELS: Record<string, string> = {
  HUMAN: "HUMAN",
  COO: "THRALL",
  CHIEF: "CHIEF",
  DEPARTMENT: "DEPT",
  AGENT: "AGENT",
};

const NODE_TYPE_CLASS: Record<string, string> = {
  HUMAN: "node-human",
  COO: "node-coo",
  CHIEF: "node-chief",
  DEPARTMENT: "node-dept",
  AGENT: "node-agent",
};

const CREATABLE_CHILDREN: Record<string, string[]> = {
  COO:        ["CHIEF"],
  CHIEF:      ["DEPARTMENT", "AGENT"],
  DEPARTMENT: ["AGENT"],
};

interface TreeNode extends NodeDTO {
  children: TreeNode[];
}

function buildTree(nodes: NodeDTO[]): TreeNode[] {
  const map = new Map<string, TreeNode>();
  nodes.forEach((n) => map.set(n.id, { ...n, children: [] }));
  const roots: TreeNode[] = [];
  map.forEach((node) => {
    if (node.parent_id && map.has(node.parent_id)) {
      map.get(node.parent_id)!.children.push(node);
    } else {
      roots.push(node);
    }
  });
  return roots;
}

// ── Add Node Modal ──────────────────────────────────────────

interface AddNodeModalProps {
  parentNode: NodeDTO;
  childType: string;
  onClose: () => void;
  onCreated: () => void;
}

function AddNodeModal({ parentNode, childType, onClose, onCreated }: AddNodeModalProps) {
  const [name, setName] = useState("");
  const [roleTitle, setRoleTitle] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!name.trim()) return;
    setSubmitting(true);
    setError(null);

    let result;
    if (childType === "CHIEF") {
      result = await addChief({
        name: name.trim(),
        role_title: roleTitle.trim() || "Chief",
        description: description.trim(),
      });
    } else if (childType === "DEPARTMENT") {
      result = await addDepartment({
        chief_id: parentNode.id,
        name: name.trim(),
        description: description.trim(),
      });
    } else if (childType === "AGENT") {
      result = await addAgent({
        parent_id: parentNode.id,
        name: name.trim(),
        role_title: roleTitle.trim() || "Agent",
        description: description.trim(),
      });
    }

    setSubmitting(false);
    if (!result || !result.ok) {
      setError(result ? result.error : "Unknown error");
      return;
    }
    onCreated();
    onClose();
  };

  const typeLabel = NODE_TYPE_LABELS[childType] ?? childType;
  const showRole = childType === "CHIEF" || childType === "AGENT";

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-box" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <span className="modal-title">
            ADD <span className={`node-badge node-${childType.toLowerCase()}`}>{typeLabel}</span>
          </span>
          <span className="modal-parent-hint">under {parentNode.name}</span>
          <button className="btn-close" onClick={onClose}>✕</button>
        </div>

        {error && <div className="modal-error">✕ {error}</div>}

        <div className="modal-body">
          <div className="form-field">
            <label>NAME <span className="required">*</span></label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={`e.g. ${childType === "CHIEF" ? "Engineering" : childType === "DEPARTMENT" ? "Frontend" : "Builder"}`}
              autoFocus
              autoComplete="off"
              onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
            />
          </div>

          {showRole && (
            <div className="form-field">
              <label>ROLE TITLE <span className="optional">(optional)</span></label>
              <input
                type="text"
                value={roleTitle}
                onChange={(e) => setRoleTitle(e.target.value)}
                placeholder={childType === "CHIEF" ? "e.g. CTO" : "e.g. Researcher"}
                autoComplete="off"
              />
            </div>
          )}

          <div className="form-field">
            <label>DESCRIPTION <span className="optional">(optional)</span></label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Brief description"
              autoComplete="off"
            />
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn-ghost" onClick={onClose} disabled={submitting}>CANCEL</button>
          <button className="btn-primary" onClick={handleSubmit} disabled={submitting || !name.trim()}>
            {submitting ? "CREATING…" : `CREATE ${typeLabel}`}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Type Chooser ────────────────────────────────────────────

interface TypeChooserProps {
  parentNode: NodeDTO;
  onChoose: (type: string) => void;
  onClose: () => void;
}

function TypeChooser({ parentNode, onChoose, onClose }: TypeChooserProps) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-box modal-box-sm" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <span className="modal-title">ADD UNDER {parentNode.name}</span>
          <button className="btn-close" onClick={onClose}>✕</button>
        </div>
        <div className="type-chooser-body">
          <button className="type-choice-btn" onClick={() => onChoose("DEPARTMENT")}>
            <span className="node-badge node-dept">DEPT</span>
            <div>
              <div className="type-choice-label">Department</div>
              <div className="type-choice-desc">Operational unit under this Chief</div>
            </div>
          </button>
          <button className="type-choice-btn" onClick={() => onChoose("AGENT")}>
            <span className="node-badge node-agent">AGENT</span>
            <div>
              <div className="type-choice-label">Agent</div>
              <div className="type-choice-desc">Task executor directly under this Chief</div>
            </div>
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Node Row ────────────────────────────────────────────────

interface AddState {
  parentNode: NodeDTO;
  childType: string | null;
}

function NodeRow({
  node,
  depth,
  onSelect,
  selectedId,
  onAddClick,
}: {
  node: TreeNode;
  depth: number;
  onSelect: (n: NodeDTO) => void;
  selectedId: string | null;
  onAddClick: (parent: NodeDTO, type: string | null) => void;
}) {
  const typeLabel = NODE_TYPE_LABELS[node.type] ?? node.type;
  const typeClass = NODE_TYPE_CLASS[node.type] ?? "node-default";
  const isSelected = node.id === selectedId;
  const creatableChildren = CREATABLE_CHILDREN[node.type];

  const handleAddClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!creatableChildren) return;
    if (creatableChildren.length === 1) {
      onAddClick(node, creatableChildren[0]);
    } else {
      onAddClick(node, null);
    }
  };

  return (
    <>
      <div
        className={`tree-row ${isSelected ? "selected" : ""}`}
        style={{ paddingLeft: `${16 + depth * 24}px` }}
        onClick={() => onSelect(node)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => e.key === "Enter" && onSelect(node)}
      >
        {depth > 0 && <span className="tree-connector">└─</span>}
        <span className={`node-badge ${typeClass}`}>{typeLabel}</span>
        <span className="node-name">{node.name}</span>
        {node.role_title && <span className="node-role">{node.role_title}</span>}
        {!node.enabled && <span className="node-disabled-tag">DISABLED</span>}

        {creatableChildren && (
          <button
            className="tree-add-btn"
            onClick={handleAddClick}
            title="Add child node"
            aria-label="Add child node"
          >
            +
          </button>
        )}
      </div>
      {node.children.map((child) => (
        <NodeRow
          key={child.id}
          node={child}
          depth={depth + 1}
          onSelect={onSelect}
          selectedId={selectedId}
          onAddClick={onAddClick}
        />
      ))}
    </>
  );
}

// ── Main Panel ──────────────────────────────────────────────

interface OrgTreePanelProps {
  nodes: NodeDTO[];
  selectedNodeId: string | null;
  onSelectNode: (node: NodeDTO) => void;
  onRefresh: () => void;
  onResetOrg: () => void;
  width: number;
  onWidthChange: (w: number) => void;
}

export function OrgTreePanel({
  nodes,
  selectedNodeId,
  onSelectNode,
  onRefresh,
  onResetOrg,
  width,
  onWidthChange,
}: OrgTreePanelProps) {
  const tree = useMemo(() => buildTree(nodes), [nodes]);
  const [addState, setAddState] = useState<AddState | null>(null);

  const dragging = useRef(false);
  const startX = useRef(0);
  const startW = useRef(0);

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    dragging.current = true;
    startX.current = e.clientX;
    startW.current = width;

    const onMove = (ev: MouseEvent) => {
      if (!dragging.current) return;
      const delta = ev.clientX - startX.current;
      const newW = Math.max(200, Math.min(600, startW.current + delta));
      onWidthChange(newW);
    };
    const onUp = () => {
      dragging.current = false;
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }, [width, onWidthChange]);

  const handleAddClick = (parentNode: NodeDTO, childType: string | null) => {
    setAddState({ parentNode, childType });
  };

  const handleChoose = (type: string) => {
    if (addState) setAddState({ ...addState, childType: type });
  };

  const handleClose = () => setAddState(null);

  const handleCreated = () => {
    onRefresh();
    setAddState(null);
  };

  return (
    <>
      <div className="panel org-tree-panel" style={{ width }}>
        <div className="panel-header">
          <span className="panel-title">ORG HIERARCHY</span>
          <span className="panel-count">{nodes.length} NODES</span>
          <button className="btn-ghost btn-sm" onClick={onRefresh} title="Refresh">↻</button>
          <button className="btn-reset-org" onClick={onResetOrg} title="Reset Org">⚠ RESET</button>
        </div>
        <div className="panel-body tree-body">
          {tree.length === 0 ? (
            <div className="empty-state">No nodes loaded.</div>
          ) : (
            tree.map((root) => (
              <NodeRow
                key={root.id}
                node={root}
                depth={0}
                onSelect={onSelectNode}
                selectedId={selectedNodeId}
                onAddClick={handleAddClick}
              />
            ))
          )}
        </div>

        <div className="tree-resize-handle" onMouseDown={onMouseDown} title="Drag to resize" />
      </div>

      {addState && addState.childType === null && (
        <TypeChooser
          parentNode={addState.parentNode}
          onChoose={handleChoose}
          onClose={handleClose}
        />
      )}
      {addState && addState.childType !== null && (
        <AddNodeModal
          parentNode={addState.parentNode}
          childType={addState.childType}
          onClose={handleClose}
          onCreated={handleCreated}
        />
      )}
    </>
  );
}
