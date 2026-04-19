// ============================================================
// StatusBar.tsx
//
// Polls /health and /llm/health on mount and every 30s.
// Displays system readiness to operator at all times.
// ============================================================

import React, { useEffect, useState, useCallback } from "react";
import { getHealth, getLlmHealth } from "../api/client";
import type { HealthResponse, LlmHealthResponse } from "../api/types";

export function StatusBar() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [llm, setLlm] = useState<LlmHealthResponse | null>(null);
  const [healthErr, setHealthErr] = useState(false);
  const [llmErr, setLlmErr] = useState(false);

  const poll = useCallback(async () => {
    const [h, l] = await Promise.all([getHealth(), getLlmHealth()]);
    if (h.ok) { setHealth(h.data); setHealthErr(false); }
    else setHealthErr(true);
    if (l.ok) { setLlm(l.data); setLlmErr(false); }
    else setLlmErr(true);
  }, []);

  useEffect(() => {
    poll();
    const t = setInterval(poll, 30_000);
    return () => clearInterval(t);
  }, [poll]);

  return (
    <div className="status-bar">
      <div className="status-item">
        <span className={`status-dot ${healthErr ? "offline" : "online"}`} />
        <span className="status-label">KERNEL</span>
        <span className="status-detail">
          {healthErr ? "OFFLINE" : health ? "OK" : "…"}
        </span>
      </div>
      <div className="status-divider" />
      <div className="status-item">
        <span className={`status-dot ${llmErr ? "offline" : llm?.configured ? "online" : "warn"}`} />
        <span className="status-label">LLM</span>
        <span className="status-detail">
          {llmErr
            ? "OFFLINE"
            : !llm
            ? "…"
            : llm.configured
            ? `${llm.provider?.toUpperCase() ?? "?"}`
            : "NOT CONFIGURED"}
        </span>
      </div>
      {llm?.default_model && (
        <>
          <div className="status-divider" />
          <div className="status-item">
            <span className="status-label">MODEL</span>
            <span className="status-detail">{llm.default_model}</span>
          </div>
        </>
      )}
    </div>
  );
}
