import { useRef, useState } from 'react';
import { MessageSquare, Trash2, Pencil, Check, X } from 'lucide-react';
import { useStore } from '../store';
import type { Session } from '../store';

function groupByDate(sessions: Session[]): { label: string; items: Session[] }[] {
  const now = Date.now();
  const DAY = 86_400_000;

  const groups: Record<string, Session[]> = {
    Today: [],
    Yesterday: [],
    'This week': [],
    'This month': [],
    Older: [],
  };

  for (const s of sessions) {
    const age = now - s.createdAt;
    if (age < DAY) groups['Today'].push(s);
    else if (age < 2 * DAY) groups['Yesterday'].push(s);
    else if (age < 7 * DAY) groups['This week'].push(s);
    else if (age < 30 * DAY) groups['This month'].push(s);
    else groups['Older'].push(s);
  }

  return Object.entries(groups)
    .filter(([, items]) => items.length > 0)
    .map(([label, items]) => ({ label, items }));
}

function formatTime(ts: number): string {
  const d = new Date(ts);
  const now = new Date();
  const sameDay =
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate();
  if (sameDay) {
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
}

interface SessionCardProps {
  session: Session;
  active: boolean;
  onOpen: (id: string) => void;
  onDelete: (id: string) => void;
  onRename: (id: string, name: string) => void;
}

function SessionCard({ session, active, onOpen, onDelete, onRename }: SessionCardProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(session.name);
  const inputRef = useRef<HTMLInputElement>(null);

  const lastMsg = session.messages[session.messages.length - 1];
  const preview = lastMsg?.content.slice(0, 80) ?? 'No messages yet';

  function startEdit(e: React.MouseEvent) {
    e.stopPropagation();
    setDraft(session.name);
    setEditing(true);
    setTimeout(() => inputRef.current?.select(), 0);
  }

  function commitEdit(e?: React.MouseEvent) {
    e?.stopPropagation();
    if (draft.trim()) onRename(session.id, draft.trim());
    setEditing(false);
  }

  function cancelEdit(e: React.MouseEvent) {
    e.stopPropagation();
    setEditing(false);
  }

  return (
    <div
      onClick={() => !editing && onOpen(session.id)}
      className={`group flex items-start gap-3 p-4 rounded-xl border cursor-pointer transition-colors ${
        active
          ? 'border-accent/40 bg-accent/5'
          : 'border-border bg-surface hover:border-border/80 hover:bg-elevated/40'
      }`}
    >
      {/* Icon */}
      <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5 ${
        active ? 'bg-accent/20' : 'bg-elevated'
      }`}>
        <MessageSquare size={14} className={active ? 'text-accent' : 'text-muted'} />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        {editing ? (
          <div className="flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
            <input
              ref={inputRef}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') commitEdit();
                if (e.key === 'Escape') setEditing(false);
              }}
              className="flex-1 bg-elevated border border-accent/40 rounded px-2 py-0.5 text-sm text-primary outline-none"
              autoFocus
            />
            <button onClick={commitEdit} className="text-green-400 hover:text-green-300 transition-colors">
              <Check size={13} />
            </button>
            <button onClick={cancelEdit} className="text-muted hover:text-primary transition-colors">
              <X size={13} />
            </button>
          </div>
        ) : (
          <div className="flex items-center justify-between gap-2">
            <span className={`text-sm font-medium truncate ${active ? 'text-accent' : 'text-primary'}`}>
              {session.name}
            </span>
            <div className="flex items-center gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
              <button
                onClick={startEdit}
                title="Rename"
                className="text-zinc-600 hover:text-primary transition-colors"
              >
                <Pencil size={12} />
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); onDelete(session.id); }}
                title="Delete"
                className="text-zinc-600 hover:text-red-400 transition-colors"
              >
                <Trash2 size={12} />
              </button>
            </div>
          </div>
        )}

        <p className="text-muted text-xs leading-relaxed mt-0.5 truncate">
          {preview.length >= 80 ? `${preview}…` : preview}
        </p>

        <div className="flex items-center gap-2 mt-1.5">
          <span className="text-zinc-600 text-xs">{formatTime(session.createdAt)}</span>
          <span className="text-zinc-700 text-xs">·</span>
          <span className="text-zinc-600 text-xs">
            {session.messages.length} {session.messages.length === 1 ? 'message' : 'messages'}
          </span>
        </div>
      </div>
    </div>
  );
}

export default function SessionsPanel() {
  const {
    sessions,
    activeSessionId,
    switchSession,
    deleteSession,
    renameSession,
    newSession,
    setPanel,
  } = useStore();

  const [search, setSearch] = useState('');

  const filtered = search.trim()
    ? sessions.filter(
        (s) =>
          s.name.toLowerCase().includes(search.toLowerCase()) ||
          s.messages.some((m) => m.content.toLowerCase().includes(search.toLowerCase())),
      )
    : sessions;

  const sorted = [...filtered].sort((a, b) => b.createdAt - a.createdAt);
  const groups = groupByDate(sorted);

  function openSession(id: string) {
    switchSession(id);
    setPanel('chat');
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-4 px-6 py-4 border-b border-border flex-shrink-0">
        <h2 className="text-primary font-semibold">Sessions</h2>

        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search sessions…"
          className="bg-elevated border border-border rounded-lg px-3 py-1.5 text-xs text-primary placeholder-muted outline-none focus:border-accent/50 w-52"
        />

        <div className="ml-auto flex items-center gap-3">
          <span className="text-zinc-600 text-xs">{sessions.length} sessions</span>
          <button
            onClick={() => { newSession(); setPanel('chat'); }}
            className="px-3 py-1.5 rounded-lg bg-accent hover:bg-accent-hover text-white text-xs transition-colors"
          >
            New session
          </button>
        </div>
      </div>

      {/* Session list */}
      <div className="flex-1 overflow-y-auto p-6">
        {filtered.length === 0 && (
          <p className="text-muted text-sm">
            {search ? 'No sessions match that search.' : 'No sessions yet.'}
          </p>
        )}

        <div className="space-y-6 max-w-2xl">
          {groups.map(({ label, items }) => (
            <div key={label}>
              <p className="text-zinc-600 text-xs uppercase tracking-wider mb-3">{label}</p>
              <div className="space-y-2">
                {items.map((s) => (
                  <SessionCard
                    key={s.id}
                    session={s}
                    active={s.id === activeSessionId}
                    onOpen={openSession}
                    onDelete={deleteSession}
                    onRename={renameSession}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
