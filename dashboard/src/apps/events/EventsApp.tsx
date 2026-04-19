import React, { useEffect, useState, useCallback, useMemo } from "react";
import { EventsPanel } from "../../components/EventsPanel";
import { listEvents } from "../../api/client";
import type { EventDTO } from "../../api/types";

// ── Shared with EventsPanel ─────────────────────────────────

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

function formatDt(iso: string) {
  try {
    return new Date(iso).toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
  } catch {
    return iso;
  }
}

// ── Audit view ──────────────────────────────────────────────

function EventsAuditPanel() {
  const [events, setEvents] = useState<EventDTO[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState("");
  const [actorFilter, setActorFilter] = useState("");

  const fetchEvents = useCallback(async () => {
    setLoading(true);
    const result = await listEvents();
    setLoading(false);
    if (!result.ok) {
      setError(result.error);
      return;
    }
    setError(null);
    setEvents([...result.data.events].reverse());
  }, []);

  useEffect(() => {
    fetchEvents();
  }, [fetchEvents]);

  const eventTypes = useMemo(
    () => Array.from(new Set(events.map((e) => e.event_type))).sort(),
    [events]
  );

  const actors = useMemo(
    () => Array.from(new Set(events.map((e) => e.actor_node_id).filter(Boolean))).sort(),
    [events]
  );

  const filtered = useMemo(() => {
    return events.filter((e) => {
      if (typeFilter && e.event_type !== typeFilter) return false;
      if (actorFilter && e.actor_node_id !== actorFilter) return false;
      return true;
    });
  }, [events, typeFilter, actorFilter]);

  return (
    <div className="panel events-panel">
      <div className="panel-header">
        <span className="panel-title">AUDIT TRAIL</span>
        <span className="panel-count">{filtered.length} / {events.length} EVENTS</span>
        <button className="btn-ghost btn-sm" onClick={fetchEvents} disabled={loading}>
          {loading ? "…" : "↻"}
        </button>
      </div>

      <div className="audit-filters">
        <select
          className="audit-filter-select"
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
        >
          <option value="">All types</option>
          {eventTypes.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <select
          className="audit-filter-select"
          value={actorFilter}
          onChange={(e) => setActorFilter(e.target.value)}
        >
          <option value="">All actors</option>
          {actors.map((a) => (
            <option key={a} value={a}>{a}</option>
          ))}
        </select>
        {(typeFilter || actorFilter) && (
          <button
            className="btn-ghost btn-sm"
            onClick={() => { setTypeFilter(""); setActorFilter(""); }}
          >
            CLEAR
          </button>
        )}
      </div>

      <div className="panel-body events-body">
        {error && <div className="panel-error">FETCH ERROR: {error}</div>}
        {!error && filtered.length === 0 && !loading && (
          <div className="empty-state">No events match the current filters.</div>
        )}
        {filtered.map((evt) => (
          <div key={evt.id} className="event-row audit-row">
            <span className="event-ts">{formatDt(evt.ts)}</span>
            <span className={`event-type ${EVENT_TYPE_CLASS[evt.event_type] ?? "evt-default"}`}>
              {evt.event_type}
            </span>
            {evt.actor_node_id && (
              <span className="event-actor">{evt.actor_node_id}</span>
            )}
            {evt.subject_node_id && evt.subject_node_id !== evt.actor_node_id && (
              <span className="event-subject">→ {evt.subject_node_id}</span>
            )}
            <span className="event-msg">{evt.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── App dispatcher ──────────────────────────────────────────

interface Props { activeView: string; }

export function EventsApp({ activeView }: Props) {
  switch (activeView) {
    case "live":  return <EventsPanel />;
    case "audit": return <EventsAuditPanel />;
    default:      return <EventsPanel />;
  }
}
