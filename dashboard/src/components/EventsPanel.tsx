// ============================================================
// EventsPanel.tsx
//
// Displays audit events from GET /events.
// Polling every 10s. Read-only. No event suppression.
// ============================================================

import React, { useEffect, useState, useCallback } from "react";
import { listEvents } from "../api/client";
import type { EventDTO } from "../api/types";

const EVENT_TYPE_CLASS: Record<string, string> = {
  NODE_CREATED: "evt-create",
  NODE_UPDATED: "evt-update",
  NODE_DISABLED: "evt-warn",
  APPROVAL_SUBMITTED: "evt-approval",
  APPROVAL_APPROVED: "evt-ok",
  APPROVAL_DENIED: "evt-deny",
  CHAT: "evt-chat",
  ERROR: "evt-error",
};

function formatTs(iso: string) {
  try {
    return new Date(iso).toLocaleTimeString("en-US", {
      hour12: false,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function EventsPanel() {
  const [events, setEvents] = useState<EventDTO[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchEvents = useCallback(async () => {
    setLoading(true);
    const result = await listEvents();
    setLoading(false);
    if (!result.ok) {
      setError(result.error);
      return;
    }
    setError(null);
    // Most recent first
    setEvents([...result.data.events].reverse());
  }, []);

  useEffect(() => {
    fetchEvents();
    const interval = setInterval(fetchEvents, 10_000);
    return () => clearInterval(interval);
  }, [fetchEvents]);

  return (
    <div className="panel events-panel">
      <div className="panel-header">
        <span className="panel-title">EVENT LOG</span>
        <span className="panel-count">{events.length} EVENTS</span>
        <button className="btn-ghost btn-sm" onClick={fetchEvents} disabled={loading}>
          {loading ? "…" : "↻"}
        </button>
      </div>
      <div className="panel-body events-body">
        {error && <div className="panel-error">FETCH ERROR: {error}</div>}
        {!error && events.length === 0 && !loading && (
          <div className="empty-state">No events recorded.</div>
        )}
        {events.map((evt) => (
          <div key={evt.id} className="event-row">
            <span className="event-ts">{formatTs(evt.ts)}</span>
            <span className={`event-type ${EVENT_TYPE_CLASS[evt.event_type] ?? "evt-default"}`}>
              {evt.event_type}
            </span>
            <span className="event-msg">{evt.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
