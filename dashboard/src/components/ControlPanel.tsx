import { useEffect, useRef, useState } from 'react';
import { RefreshCw, Square, Check, X } from 'lucide-react';
import { useStore } from '../store';

interface StatusData {
  status: string;
  version: string;
  model: string;
  config_model: string;
  model_overridden: boolean;
  tasks: number;
  cost_usd: number;
  uptime_seconds: number;
  reasoning_effort: string | null;
  errors: number;
}

function formatUptime(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60) % 60;
  const h = Math.floor(seconds / 3600);
  if (h === 0) return `${m}m`;
  return `${h}h ${m}m`;
}

interface RowProps {
  label: string;
  children: React.ReactNode;
  last?: boolean;
}

function Row({ label, children, last }: RowProps) {
  return (
    <div className={`flex items-center justify-between px-4 py-3 ${last ? '' : 'border-b border-border'}`}>
      <span className="text-muted text-sm">{label}</span>
      <span className="text-sm text-primary">{children}</span>
    </div>
  );
}

interface ModelEditorProps {
  current: string;
  overridden: boolean;
  configModel: string;
  sessionId: string | null;
  onSaved: () => void;
}

function ModelEditor({ current, overridden, configModel, sessionId: _sid, onSaved }: ModelEditorProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(current);
  const [saving, setSaving] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  function startEdit() {
    setDraft(current);
    setEditing(true);
    setTimeout(() => { inputRef.current?.select(); }, 0);
  }

  async function save() {
    if (!draft.trim() || draft.trim() === current) { setEditing(false); return; }
    setSaving(true);
    try {
      await fetch('/api/control/model', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: draft.trim() }),
      });
      setEditing(false);
      onSaved();
    } finally {
      setSaving(false);
    }
  }

  async function reset() {
    setSaving(true);
    try {
      await fetch('/api/control/model', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: null }),
      });
      setEditing(false);
      onSaved();
    } finally {
      setSaving(false);
    }
  }

  if (editing) {
    return (
      <div className="flex items-center gap-1.5">
        <input
          ref={inputRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') void save();
            if (e.key === 'Escape') setEditing(false);
          }}
          className="bg-elevated border border-accent/50 rounded px-2 py-0.5 text-xs text-primary font-mono outline-none w-56"
          autoFocus
        />
        <button onClick={() => void save()} disabled={saving} className="text-green-400 hover:text-green-300 transition-colors">
          <Check size={13} />
        </button>
        <button onClick={() => setEditing(false)} className="text-muted hover:text-primary transition-colors">
          <X size={13} />
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <button
        onClick={startEdit}
        title="Click to change model"
        className="font-mono text-xs text-primary hover:text-accent transition-colors truncate max-w-[200px]"
      >
        {current}
      </button>
      {overridden && (
        <button
          onClick={() => void reset()}
          title={`Reset to config default (${configModel})`}
          className="text-zinc-600 hover:text-muted text-xs transition-colors"
        >
          reset
        </button>
      )}
    </div>
  );
}

export default function ControlPanel() {
  const { sessionId } = useStore();
  const [data, setData] = useState<StatusData | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [stopping, setStopping] = useState(false);

  async function load() {
    setLoading(true);
    setErr(null);
    try {
      const r = await fetch('/api/status');
      if (!r.ok) throw new Error(String(r.status));
      setData((await r.json()) as StatusData);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }

  async function stopTask() {
    if (!sessionId || stopping) return;
    setStopping(true);
    try {
      await fetch('/api/control/stop', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId }),
      });
      setTimeout(() => void load(), 500);
    } finally {
      setStopping(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  // Auto-refresh every 3s while a task is active
  useEffect(() => {
    if (!data || data.tasks === 0) return;
    const t = setInterval(() => void load(), 3_000);
    return () => clearInterval(t);
  }, [data?.tasks]);

  return (
    <div className="p-6 max-w-2xl">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-primary font-semibold">Control</h2>
        <button
          onClick={() => void load()}
          title="Refresh"
          className={`text-muted hover:text-primary transition-colors ${loading ? 'animate-spin' : ''}`}
        >
          <RefreshCw size={14} />
        </button>
      </div>

      {err && <p className="text-red-400 text-sm mb-4">Failed to load: {err}</p>}

      {data && (
        <div className="space-y-4">
          <div className="bg-surface rounded-xl border border-border overflow-hidden">
            <Row label="Status">
              <span className={data.status === 'ok' ? 'text-green-400' : 'text-red-400'}>
                {data.status}
              </span>
            </Row>
            <Row label="Version">
              <span className="font-mono text-xs">{data.version}</span>
            </Row>
            <Row label="Model">
              <ModelEditor
                current={data.model}
                overridden={data.model_overridden}
                configModel={data.config_model}
                sessionId={sessionId}
                onSaved={() => void load()}
              />
            </Row>
            {data.reasoning_effort && (
              <Row label="Reasoning effort">
                <span className="font-mono text-xs">{data.reasoning_effort}</span>
              </Row>
            )}
            <Row label="Active tasks">
              <span className={data.tasks > 0 ? 'text-yellow-400' : ''}>{data.tasks}</span>
            </Row>
            <Row label="Session cost">
              ${(data.cost_usd ?? 0).toFixed(4)}
            </Row>
            <Row label="Uptime">
              {formatUptime(data.uptime_seconds)}
            </Row>
            <Row label="Errors logged" last>
              <span className={data.errors > 0 ? 'text-red-400' : 'text-zinc-600'}>
                {data.errors}
              </span>
            </Row>
          </div>

          {/* Stop button */}
          <button
            onClick={() => void stopTask()}
            disabled={data.tasks === 0 || stopping || !sessionId}
            className="flex items-center gap-2 px-4 py-2 rounded-lg border border-red-500/40 text-red-400 hover:bg-red-500/10 disabled:opacity-30 disabled:cursor-not-allowed transition-colors text-sm"
          >
            <Square size={13} />
            {stopping ? 'Stopping…' : 'Stop active task'}
          </button>

          {data.model_overridden && (
            <p className="text-zinc-600 text-xs">
              Model overridden from config default ({data.config_model}). Click "reset" to restore.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
