import React from "react";
import { PlaceholderView } from "../../components/PlaceholderView";

interface Props { activeView: string; }

function GovernanceOverview() {
  return (
    <div className="control-overview">
      <div className="view-header">
        <span className="view-title">GOVERNANCE</span>
      </div>
      <div className="stat-grid">
        <div className="stat-card">
          <div className="stat-label">APPROVAL GATE</div>
          <div className="stat-value stat-ok">ACTIVE</div>
          <div className="stat-detail">All mutations require explicit approval</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">EXECUTION GATE</div>
          <div className="stat-value stat-ok">ENFORCED</div>
          <div className="stat-detail">No side-effects bypass kernel authority</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">HIERARCHY RULES</div>
          <div className="stat-value stat-ok">LOCKED</div>
          <div className="stat-detail">UI cannot invent or override node authority</div>
        </div>
      </div>
    </div>
  );
}

export function GovernanceApp({ activeView }: Props) {
  switch (activeView) {
    case "overview": return <GovernanceOverview />;
    case "rules":    return <PlaceholderView app="Governance" view="Rules" message="Rule definition interface coming soon." />;
    case "audit":    return <PlaceholderView app="Governance" view="Audit" message="Governance audit trail coming soon." />;
    default:         return <GovernanceOverview />;
  }
}
