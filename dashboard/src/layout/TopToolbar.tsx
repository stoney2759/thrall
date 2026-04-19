// ============================================================
// TopToolbar.tsx — Contextual toolbar driven by activeApp
// Left: app title + contextual tab views
// Right: identity indicators + health status
// ============================================================

import React, { useEffect, useState, useCallback } from "react";
import { useAppStore } from "../state/store";
import { TOOLBAR_VIEWS, APPS } from "../config/apps.config";
import { getHealth, getLlmHealth } from "../api/client";
import type { HealthResponse, LlmHealthResponse } from "../api/types";

function HealthIndicators() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [llm, setLlm] = useState<LlmHealthResponse | null>(null);
  const [err, setErr] = useState(false);

  const poll = useCallback(async () => {
    const [h, l] = await Promise.all([getHealth(), getLlmHealth()]);
    if (h.ok) { setHealth(h.data); setErr(false); }
    else setErr(true);
    if (l.ok) setLlm(l.data);
  }, []);

  useEffect(() => {
    poll();
    const t = setInterval(poll, 30_000);
    return () => clearInterval(t);
  }, [poll]);

  return (
    <div className="toolbar-health">
      <div className={`health-chip ${err ? "err" : "ok"}`}>
        <span className="health-dot" />
        <span>Health</span>
        <span className="health-val">{err ? "ERR" : health ? "OK" : "…"}</span>
      </div>
      {llm && (
        <div className={`health-chip ${llm.configured ? "ok" : "warn"}`}>
          <span className="health-dot" />
          <span>{llm.provider?.toUpperCase() ?? "LLM"}</span>
          <span className="health-val">{llm.configured ? llm.default_model || "OK" : "OFF"}</span>
        </div>
      )}
    </div>
  );
}

export function TopToolbar() {
  const { activeApp, activeView, setActiveView, humanNode, cooNode } = useAppStore();

  const appDef = APPS.find((a) => a.id === activeApp);
  const views = TOOLBAR_VIEWS[activeApp] ?? [];

  return (
    <header className="top-toolbar">
      {/* Left: app title + contextual tabs */}
      <div className="toolbar-left">
        <div className="toolbar-app-title">{appDef?.label ?? activeApp}</div>
        <div className="toolbar-divider-v" />
        <nav className="toolbar-tabs">
          {views.map((view) => (
            <button
              key={view.id}
              className={`toolbar-tab ${activeView === view.id ? "active" : ""}`}
              onClick={() => setActiveView(view.id)}
            >
              {view.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Right: identity + health */}
      <div className="toolbar-right">
        {humanNode && (
          <div className="toolbar-identity">
            <span className="identity-label">Human</span>
            <span className="identity-name">{humanNode.name}</span>
          </div>
        )}
        {cooNode && (
          <div className="toolbar-identity">
            <span className="identity-label">Thrall</span>
            <span className="identity-name">{cooNode.name}</span>
          </div>
        )}
        <HealthIndicators />
      </div>
    </header>
  );
}
