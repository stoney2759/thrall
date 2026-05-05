import { useEffect, useMemo, useRef, useState } from 'react';
import { RefreshCw, ChevronDown, ChevronRight } from 'lucide-react';

type LogFile = 'main' | 'errors' | 'memory' | 'session';
type LevelFilter = '' | 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL';

interface LogEntry {
  ts: string;
  level: string;
  module: string;
  message: string;
  trace: string;
  error?: string;
  timestamp?: string;
}

interface SessionTurn {
  role: string;
  content: string;
}

interface SessionBlock {
  session_id: string;
  turns: number;
  tokens: number;
  context: SessionTurn[];
}

const LEVEL_COLORS: Record<string, string> = {
  DEBUG:    'text-zinc-500 bg-zinc-800',
  INFO:     'text-blue-400 bg-blue-900/30',
  WARNING:  'text-yellow-400 bg-yellow-900/30',
  ERROR:    'text-red-400 bg-red-900/30',
  CRITICAL: 'text-red-300 bg-red-900/50',
};

const ROLE_COLORS: Record<string, string> = {
  user:      'bg-blue-900/30 text-blue-400',
  assistant: 'bg-accent/20 text-accent',
  thrall:    'bg-accent/20 text-accent',
  system:    'bg-zinc-800 text-zinc-400',
  tool:      'bg-yellow-900/30 text-yellow-400',
};

function EntryRow({ entry }: { entry: LogEntry }) {
  const [open, setOpen] = useState(false);
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
        <span className="flex-shrink-0 mt-0.5 text-zinc-600 w-3">
          {hasTrace ? (open ? <ChevronDown size={11} /> : <ChevronRight size={11} />) : null}
        </span>
        <span className="text-zinc-600 flex-shrink-0 font-mono tabular-nums">{ts.slice(11)}</span>
        <span className={`flex-shrink-0 px-1.5 py-0.5 rounded text-xs font-medium uppercase tracking-wide ${levelColor}`}>
          {level}
        </span>
        <span className="text-zinc-500 flex-shrink-0 max-w-[140px] truncate font-mono">{module}</span>
        <span className="text-primary leading-relaxed min-w-0 break-words">{message}</span>
      </div>
      {open && trace && (
        <pre className="px-10 pb-3 text-xs text-zinc-500 font-mono whitespace-pre-wrap leading-relaxed">{trace}</pre>
      )}
    </div>
  );
}

function TurnRow({ turn }: { turn: SessionTurn }) {
  const [open, setOpen] = useState(false);
  const label = turn.role === 'assistant' ? 'Thrall' : turn.role;
  const roleColor = ROLE_COLORS[turn.role] ?? 'bg-zinc-800 text-zinc-400';
  const preview = turn.content.slice(0, 120) + (turn.content.length > 120 ? '…' : '');

  return (
    <div className="border-b border-border/50 last:border-0">
      <div
        className="flex items-start gap-2.5 px-4 py-2.5 text-xs cursor-pointer hover:bg-elevated/40"
        onClick={() => setOpen((o) => !o)}
      >
        <span className="flex-shrink-0 mt-0.5 text-zinc-600 w-3">
          {open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
        </span>
        <span className={`flex-shrink-0 px-1.5 py-0.5 rounded text-xs font-medium ${roleColor}`}>
          {label}
        </span>
        <span className="text-muted leading-relaxed min-w-0 break-words">
          {open ? turn.content : preview}
        </span>
      </div>
    </div>
  );
}

function SessionView({ blocks }: { blocks: SessionBlock[] }) {
  if (blocks.length === 0) {
    return <p className="text-muted text-sm px-6 py-6">No active sessions in memory.</p>;
  }
  return (
    <>
      {blocks.map((b) => (
        <div key={b.session_id} className="mb-6">
          <div className="px-4 py-2 bg-elevated/50 border-b border-border flex items-center gap-4">
            <span className="text-zinc-500 text-xs font-mono truncate">{b.session_id}</span>
            <span className="text-xs text-muted">{b.turns} turns</span>
            <span className="text-xs text-muted">~{b.tokens.toLocaleString()} tokens</span>
          </div>
          {b.context.map((turn, i) => <TurnRow key={i} turn={turn} />)}
        </div>
      ))}
    </>
  );
}

const FILES: { id: LogFile; label: string }[] = [
  { id: 'main',    label: 'Main' },
  { id: 'errors',  label: 'Errors' },
  { id: 'memory',  label: 'Runtime Errors' },
  { id: 'session', label: 'In-memory' },
];

const LEVELS: { id: LevelFilter; label: string }[] = [
  { id: '',        label: 'All' },
  { id: 'DEBUG',   label: 'Debug' },
  { id: 'INFO',    label: 'Info' },
  { id: 'WARNING', label: 'Warn' },
  { id: 'ERROR',   label: 'Error' },
];

export default function LogsPanel() {
  const [entries, setEntries] = useState<LogEntry[]>([]);
  const [sessions, setSessions] = useState<SessionBlock[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [file, setFile] = useState<LogFile>('main');
  const [levelFilter, setLevelFilter] = useState<LevelFilter>('');
  const [search, setSearch] = useState('');
  const [useRegex, setUseRegex] = useState(false);
  const [ascending, setAscending] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  async function load(f = file) {
    setLoading(true);
    setErr(null);
    try {
      if (f === 'session') {
        const r = await fetch('/api/memory/session');
        if (!r.ok) throw new Error(String(r.status));
        setSessions((await r.json()) as SessionBlock[]);
      } else {
        const params = new URLSearchParams({ file: f, lines: '500', min_level: 'DEBUG' });
        const r = await fetch(`/api/logs?${params.toString()}`);
        if (!r.ok) throw new Error(String(r.status));
        setEntries((await r.json()) as LogEntry[]);
      }
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
  }, [autoRefresh, file]);

  function changeFile(f: LogFile) {
    setFile(f);
    void load(f);
  }

  const displayEntries = useMemo(() => {
    let result = [...entries];
    if (levelFilter) {
      result = result.filter((e) => (e.level ?? '').toUpperCase() === levelFilter);
    }
    if (search.trim()) {
      if (useRegex) {
        try {
          const re = new RegExp(search, 'i');
          result = result.filter(
            (e) => re.test(e.message ?? '') || re.test(e.module ?? '') || re.test(e.trace ?? ''),
          );
        } catch { /* invalid regex — skip filter */ }
      } else {
        const q = search.toLowerCase();
        result = result.filter(
          (e) => (e.message ?? '').toLowerCase().includes(q) || (e.module ?? '').toLowerCase().includes(q),
        );
      }
    }
    if (ascending) result = [...result].reverse();
    return result;
  }, [entries, levelFilter, search, useRegex, ascending]);

  const isSession = file === 'session';

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-4 px-6 py-4 border-b border-border flex-shrink-0 flex-wrap gap-y-2">
        <h2 className="text-primary font-semibold mr-2">Logs</h2>

        <div className="flex gap-1">
          {FILES.map((f) => (
            <button
              key={f.id}
              onClick={() => changeFile(f.id)}
              className={`px-2.5 py-1 rounded text-xs transition-colors ${
                file === f.id ? 'bg-accent/20 text-accent' : 'text-muted hover:text-primary'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>

        {!isSession && (
          <div className="flex gap-1">
            {LEVELS.map((l) => (
              <button
                key={l.id}
                onClick={() => setLevelFilter(l.id)}
                className={`px-2.5 py-1 rounded text-xs transition-colors ${
                  levelFilter === l.id ? 'bg-elevated text-primary' : 'text-muted hover:text-primary'
                }`}
              >
                {l.label}
              </button>
            ))}
          </div>
        )}

        <div className="ml-auto flex items-center gap-2">
          {!isSession && (
            <>
              <div className="flex items-center bg-elevated border border-border rounded px-2 py-1 gap-1">
                <input
                  type="text"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search…"
                  className="bg-transparent text-xs text-zinc-400 placeholder-zinc-600 outline-none w-28"
                />
                <button
                  onClick={() => setUseRegex((v) => !v)}
                  title="Toggle regex"
                  className={`text-xs font-mono leading-none px-0.5 transition-colors ${useRegex ? 'text-accent' : 'text-zinc-600 hover:text-zinc-400'}`}
                >
                  .*
                </button>
              </div>
              <button
                onClick={() => setAscending((v) => !v)}
                title={ascending ? 'Oldest first (click for newest)' : 'Newest first (click for oldest)'}
                className="text-zinc-600 hover:text-zinc-400 transition-colors text-sm leading-none"
              >
                {ascending ? '↑' : '↓'}
              </button>
            </>
          )}
          <button
            onClick={() => setAutoRefresh((v) => !v)}
            className={`text-xs px-2.5 py-1 rounded transition-colors ${
              autoRefresh ? 'bg-green-900/30 text-green-400' : 'text-muted hover:text-primary'
            }`}
          >
            Live
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

      {err && <p className="text-red-400 text-sm px-6 py-4">Failed to load: {err}</p>}

      <div className="flex-1 overflow-y-auto font-mono">
        {isSession ? (
          !loading && <SessionView blocks={sessions} />
        ) : (
          <>
            {!loading && displayEntries.length === 0 && !err && (
              <p className="text-muted text-sm px-6 py-6">No log entries.</p>
            )}
            {displayEntries.map((e, i) => <EntryRow key={i} entry={e} />)}
          </>
        )}
      </div>

      <div className="px-6 py-2 border-t border-border flex-shrink-0 flex items-center justify-between">
        <span className="text-zinc-600 text-xs">
          {isSession
            ? `${sessions.reduce((n, b) => n + b.turns, 0)} turns across ${sessions.length} session(s)`
            : displayEntries.length < entries.length
              ? `${displayEntries.length} of ${entries.length} entries`
              : `${entries.length} entries`}
        </span>
        {autoRefresh && <span className="text-green-600 text-xs">Refreshing every 5s</span>}
      </div>
    </div>
  );
}
