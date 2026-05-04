import { useEffect, useRef, useState } from 'react';
import { RefreshCw, ChevronDown, ChevronRight } from 'lucide-react';

type LogFile = 'main' | 'errors' | 'memory';
type MinLevel = 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR';

interface LogEntry {
  ts: string;
  level: string;
  module: string;
  message: string;
  trace: string;
  // memory error log shape
  error?: string;
  timestamp?: string;
}

const LEVEL_COLORS: Record<string, string> = {
  DEBUG:    'text-zinc-500 bg-zinc-800',
  INFO:     'text-blue-400 bg-blue-900/30',
  WARNING:  'text-yellow-400 bg-yellow-900/30',
  ERROR:    'text-red-400 bg-red-900/30',
  CRITICAL: 'text-red-300 bg-red-900/50',
};

interface EntryRowProps {
  entry: LogEntry;
}

function EntryRow({ entry }: EntryRowProps) {
  const [open, setOpen] = useState(false);

  // Normalise memory error log shape
  const ts = entry.ts ?? entry.timestamp?.slice(0, 19).replace('T', ' ') ?? '';
  const level = entry.level ?? 'ERROR';
  const module = entry.module ?? 'state';
  const message = entry.message ?? entry.error ?? '';
  const trace = entry.trace ?? '';
  const hasTrace = trace.length > 0;

  const levelColor = LEVEL_COLORS[level.toUpperCase()] ?? 'text-zinc-400 bg-zinc-800';

  return (
    <div className="border-b border-border/50 last:border-0">
      <div
        className={`flex items-start gap-2.5 px-4 py-2.5 text-xs ${hasTrace ? 'cursor-pointer hover:bg-elevated/40' : ''}`}
        onClick={() => hasTrace && setOpen((o) => !o)}
      >
        {/* Expand chevron */}
        <span className="flex-shrink-0 mt-0.5 text-zinc-600 w-3">
          {hasTrace ? (open ? <ChevronDown size={11} /> : <ChevronRight size={11} />) : null}
        </span>

        {/* Timestamp */}
        <span className="text-zinc-600 flex-shrink-0 font-mono tabular-nums">
          {ts.slice(11)}
        </span>

        {/* Level badge */}
        <span className={`flex-shrink-0 px-1.5 py-0.5 rounded text-xs font-medium uppercase tracking-wide ${levelColor}`}>
          {level}
        </span>

        {/* Module */}
        <span className="text-zinc-500 flex-shrink-0 max-w-[140px] truncate font-mono">
          {module}
        </span>

        {/* Message */}
        <span className="text-primary leading-relaxed min-w-0 break-words">
          {message}
        </span>
      </div>

      {/* Traceback */}
      {open && trace && (
        <pre className="px-10 pb-3 text-xs text-zinc-500 font-mono whitespace-pre-wrap leading-relaxed">
          {trace}
        </pre>
      )}
    </div>
  );
}

const FILES: { id: LogFile; label: string }[] = [
  { id: 'main',   label: 'Main' },
  { id: 'errors', label: 'Errors' },
  { id: 'memory', label: 'In-memory' },
];

const LEVELS: { id: MinLevel; label: string }[] = [
  { id: 'DEBUG',   label: 'All' },
  { id: 'INFO',    label: 'INFO+' },
  { id: 'WARNING', label: 'WARN+' },
  { id: 'ERROR',   label: 'Error' },
];

export default function LogsPanel() {
  const [entries, setEntries] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [file, setFile] = useState<LogFile>('main');
  const [minLevel, setMinLevel] = useState<MinLevel>('INFO');
  const [autoRefresh, setAutoRefresh] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  async function load(f = file, lvl = minLevel) {
    setLoading(true);
    setErr(null);
    try {
      const params = new URLSearchParams({ file: f, lines: '150', min_level: lvl });
      const r = await fetch(`/api/logs?${params.toString()}`);
      if (!r.ok) throw new Error(String(r.status));
      setEntries((await r.json()) as LogEntry[]);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  useEffect(() => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    if (autoRefresh) {
      intervalRef.current = setInterval(() => void load(), 5_000);
    }
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [autoRefresh, file, minLevel]);

  function changeFile(f: LogFile) {
    setFile(f);
    void load(f, minLevel);
  }

  function changeLevel(lvl: MinLevel) {
    setMinLevel(lvl);
    void load(file, lvl);
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-4 px-6 py-4 border-b border-border flex-shrink-0 flex-wrap gap-y-2">
        <h2 className="text-primary font-semibold mr-2">Logs</h2>

        {/* File tabs */}
        <div className="flex gap-1">
          {FILES.map((f) => (
            <button
              key={f.id}
              onClick={() => changeFile(f.id)}
              className={`px-2.5 py-1 rounded text-xs transition-colors ${
                file === f.id
                  ? 'bg-accent/20 text-accent'
                  : 'text-muted hover:text-primary'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>

        {/* Level filter */}
        <div className="flex gap-1">
          {LEVELS.map((l) => (
            <button
              key={l.id}
              onClick={() => changeLevel(l.id)}
              className={`px-2.5 py-1 rounded text-xs transition-colors ${
                minLevel === l.id
                  ? 'bg-elevated text-primary'
                  : 'text-muted hover:text-primary'
              }`}
            >
              {l.label}
            </button>
          ))}
        </div>

        <div className="ml-auto flex items-center gap-3">
          {/* Auto-refresh toggle */}
          <button
            onClick={() => setAutoRefresh((v) => !v)}
            className={`text-xs px-2.5 py-1 rounded transition-colors ${
              autoRefresh
                ? 'bg-green-900/30 text-green-400'
                : 'text-muted hover:text-primary'
            }`}
          >
            {autoRefresh ? 'Live' : 'Live'}
          </button>

          <button
            onClick={() => void load()}
            title="Refresh"
            className={`text-muted hover:text-primary transition-colors ${loading ? 'animate-spin' : ''}`}
          >
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

      {/* Error state */}
      {err && <p className="text-red-400 text-sm px-6 py-4">Failed to load: {err}</p>}

      {/* Log entries */}
      <div className="flex-1 overflow-y-auto font-mono">
        {!loading && entries.length === 0 && !err && (
          <p className="text-muted text-sm px-6 py-6">No log entries.</p>
        )}
        {entries.map((e, i) => (
          <EntryRow key={i} entry={e} />
        ))}
      </div>

      {/* Footer */}
      <div className="px-6 py-2 border-t border-border flex-shrink-0 flex items-center justify-between">
        <span className="text-zinc-600 text-xs">{entries.length} entries</span>
        {autoRefresh && <span className="text-green-600 text-xs">Refreshing every 5s</span>}
      </div>
    </div>
  );
}
