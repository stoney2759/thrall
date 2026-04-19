import React, { useEffect, useCallback } from "react";
import { PlaceholderView } from "../../components/PlaceholderView";
import { useAppStore } from "../../state/store";
import { listNodes } from "../../api/client";

interface Props { activeView: string; }

function AgentsListView() {
  const store = useAppStore();
  const agents = store.orgNodes.filter((n) => n.type === "AGENT");

  const refresh = useCallback(async () => {
    const r = await listNodes();
    if (r.ok) store.setOrgNodes(r.data.nodes);
  }, [store.setOrgNodes]);

  useEffect(() => { refresh(); }, [refresh]);

  return (
    <div className="nodes-table-view">
      <div className="view-header">
        <span className="view-title">ALL AGENTS</span>
        <span className="view-count">{agents.length} agents</span>
        <button className="btn-ghost btn-sm" onClick={refresh}>↻ Refresh</button>
      </div>
      {agents.length === 0 ? (
        <div className="empty-state">No agent nodes found. Add agents via the Org hierarchy.</div>
      ) : (
        <table className="data-table">
          <thead>
            <tr><th>NAME</th><th>ROLE</th><th>PARENT</th><th>STATUS</th></tr>
          </thead>
          <tbody>
            {agents.map((a) => (
              <tr key={a.id}>
                <td className="td-primary">{a.name}</td>
                <td className="td-dim">{a.role_title || "—"}</td>
                <td className="td-mono td-dim">{a.parent_id ? a.parent_id.slice(0, 12) + "…" : "—"}</td>
                <td><span className={a.enabled !== false ? "status-enabled" : "status-disabled"}>
                  {a.enabled !== false ? "ENABLED" : "DISABLED"}
                </span></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export function AgentsApp({ activeView }: Props) {
  switch (activeView) {
    case "list":   return <AgentsListView />;
    case "active": return <AgentsListView />;
    case "detail": return <PlaceholderView app="Agents" view="Detail" message="Agent detail view coming soon." />;
    default:       return <AgentsListView />;
  }
}
