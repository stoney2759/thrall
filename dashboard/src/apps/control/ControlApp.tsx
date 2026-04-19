import React, { useEffect, useState, useCallback } from "react";
import { PlaceholderView } from "../../components/PlaceholderView";
import { getHealth, getLlmHealth } from "../../api/client";
import type { HealthResponse, LlmHealthResponse } from "../../api/types";

interface Props { activeView: string; }

function OverviewView() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [llm, setLlm] = useState<LlmHealthResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const poll = useCallback(async () => {
    setLoading(true);
    const [h, l] = await Promise.all([getHealth(), getLlmHealth()]);
    if (h.ok) setHealth(h.data);
    if (l.ok) setLlm(l.data);
    setLoading(false);
  }, []);

  useEffect(() => { poll(); }, [poll]);

  return (
    <div className="control-overview">
      <div className="view-header">
        <span className="view-title">SYSTEM OVERVIEW</span>
        <button className="btn-ghost btn-sm" onClick={poll} disabled={loading}>↻ Refresh</button>
      </div>
      <div className="stat-grid">
        <div className="stat-card">
          <div className="stat-label">KERNEL STATUS</div>
          <div className={`stat-value ${health ? "stat-ok" : "stat-unknown"}`}>
            {loading ? "…" : health ? "OPERATIONAL" : "UNREACHABLE"}
          </div>
          {health && <div className="stat-detail">{health.project_root}</div>}
        </div>
        <div className="stat-card">
          <div className="stat-label">LLM STATUS</div>
          <div className={`stat-value ${llm?.configured ? "stat-ok" : "stat-warn"}`}>
            {loading ? "…" : !llm ? "UNKNOWN" : llm.configured ? "CONFIGURED" : "NOT CONFIGURED"}
          </div>
          {llm && <div className="stat-detail">{llm.provider} / {llm.default_model || "no model"}</div>}
        </div>
        <div className="stat-card">
          <div className="stat-label">CONFIG PATH</div>
          <div className="stat-value stat-mono">
            {loading ? "…" : health?.config_path ?? "—"}
          </div>
        </div>
      </div>
    </div>
  );
}

export function ControlApp({ activeView }: Props) {
  switch (activeView) {
    case "overview":  return <OverviewView />;
    case "jobs":      return <PlaceholderView app="Control" view="Jobs" message="Job queue management coming soon." />;
    case "cron":      return <PlaceholderView app="Control" view="Cron" message="Cron scheduling coming soon." />;
    case "health":    return <OverviewView />;
    case "activity":  return <PlaceholderView app="Control" view="Activity" message="Activity monitor coming soon." />;
    default:          return <OverviewView />;
  }
}
