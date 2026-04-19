// ============================================================
// Dashboard.tsx
//
// Main shell post-bootstrap.
// Panels: OrgTree | ThrallChat | Approvals | Events
// NodeDetailSidebar: opens on node selection
// ============================================================

import React, { useState, useCallback, useEffect } from "react";
import { useAppStore } from "../state/store";
import { OrgTreePanel } from "../components/OrgTreePanel";
import { ThrallChatPanel } from "../components/ThrallChatPanel";
import { ApprovalsPanel } from "../components/ApprovalsPanel";
import { EventsPanel } from "../components/EventsPanel";
import { NodeDetailSidebar } from "../components/NodeDetailSidebar";
import { StatusBar } from "../components/StatusBar";
import { listNodes } from "../api/client";
import type { NodeDTO } from "../api/types";

type ActiveTab = "chat" | "approvals" | "events";

export function Dashboard() {
  const store = useAppStore();
  const [selectedNode, setSelectedNode] = useState<NodeDTO | null>(null);
  const [activeTab, setActiveTab] = useState<ActiveTab>("chat");

  const refreshNodes = useCallback(async () => {
    const result = await listNodes();
    if (result.ok) store.setOrgNodes(result.data.nodes);
  }, [store]);

  useEffect(() => {
    refreshNodes();
  }, [refreshNodes]);

  return (
    <div className="dashboard">
      <header className="dash-header">
        <div className="dash-logo">
          <span className="logo-mark">◈</span>
          <span className="logo-text">OPENTHRALL</span>
        </div>
        <div className="dash-identity">
          {store.humanNode && (
            <span className="identity-tag">
              <span className="identity-label">HUMAN</span>
              <span className="identity-name">{store.humanNode.name}</span>
            </span>
          )}
          {store.cooNode && (
            <span className="identity-tag">
              <span className="identity-label">THRALL</span>
              <span className="identity-name">{store.cooNode.name}</span>
            </span>
          )}
        </div>
        <StatusBar />
        <button className="btn-ghost btn-sm" onClick={refreshNodes} title="Refresh org">↻ SYNC</button>
      </header>

      <div className="dash-body">
        {/* Left: Org Tree */}
        <aside className="dash-sidebar-left">
          <OrgTreePanel
            nodes={store.orgNodes}
            selectedNodeId={selectedNode?.id ?? null}
            onSelectNode={setSelectedNode}
          />
        </aside>

        {/* Center: Tabbed panels */}
        <main className="dash-main">
          <div className="tab-bar">
            <button
              className={`tab ${activeTab === "chat" ? "active" : ""}`}
              onClick={() => setActiveTab("chat")}
            >
              THRALL CHANNEL
            </button>
            <button
              className={`tab ${activeTab === "approvals" ? "active" : ""}`}
              onClick={() => setActiveTab("approvals")}
            >
              APPROVALS
            </button>
            <button
              className={`tab ${activeTab === "events" ? "active" : ""}`}
              onClick={() => setActiveTab("events")}
            >
              EVENT LOG
            </button>
          </div>
          <div className="tab-content">
            {activeTab === "chat" && <ThrallChatPanel />}
            {activeTab === "approvals" && <ApprovalsPanel />}
            {activeTab === "events" && <EventsPanel />}
          </div>
        </main>

        {/* Right: Node detail */}
        {selectedNode && (
          <aside className="dash-sidebar-right">
            <NodeDetailSidebar
              node={selectedNode}
              onClose={() => setSelectedNode(null)}
            />
          </aside>
        )}
      </div>
    </div>
  );
}
