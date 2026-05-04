import { useEffect, useRef, useState } from 'react';
import { RefreshCw, Trash2, ChevronDown, ChevronRight } from 'lucide-react';

type MemoryTab = 'episodes' | 'knowledge';

interface Episode {
  id: string;
  session_id: string;
  role: string;
  content: string;
  tags: string[];
  timestamp: string;
}

interface KnowledgeFact {
  id: string;
  content: string;
  source: string;
  confidence: number;
  tags: string[];
  created_at: string;
  updated_at: string;
}

const ROLE_COLORS: Record<string, string> = {
  user:      'bg-blue-900/30 text-blue-400',
  thrall:    'bg-accent/20 text-accent',
  assistant: 'bg-accent/20 text-accent',
};

function Tag({ label }: { label: string }) {
  return (
    <span className="px-1.5 py-0.5 rounded bg-elevated text-zinc-500 text-xs">
      {label}
    </span>
  );
}

function EpisodeCard({
  episode,
  onDelete,
}: {
  episode: Episode;
  onDelete: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const long = episode.content.length > 140;

  async function remove() {
    setDeleting(true);
    try {
      await fetch(`/api/memory/episodes/${episode.id}`, { method: 'DELETE' });
      onDelete(episode.id);
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="bg-surface rounded-xl border border-border p-4">
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span
            className={`text-xs px-2 py-0.5 rounded-full font-medium ${
              ROLE_COLORS[episode.role] ?? 'bg-zinc-800 text-zinc-400'
            }`}
          >
            {episode.role}
          </span>
          <span className="text-zinc-600 text-xs font-mono">
            {episode.timestamp.slice(0, 16).replace('T', ' ')}
          </span>
        </div>
        <button
          onClick={() => void remove()}
          disabled={deleting}
          title="Delete"
          className="text-zinc-600 hover:text-red-400 transition-colors flex-shrink-0 disabled:opacity-40"
        >
          <Trash2 size={13} />
        </button>
      </div>

      <div
        className={long ? 'cursor-pointer' : ''}
        onClick={() => long && setOpen((o) => !o)}
      >
        <p className="text-primary text-sm leading-relaxed">
          {open || !long ? episode.content : `${episode.content.slice(0, 140)}…`}
        </p>
        {long && (
          <span className="text-zinc-600 text-xs flex items-center gap-0.5 mt-1">
            {open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
            {open ? 'collapse' : 'expand'}
          </span>
        )}
      </div>

      {episode.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {episode.tags.map((t) => <Tag key={t} label={t} />)}
        </div>
      )}

      <p className="text-zinc-700 text-xs mt-2 font-mono truncate">
        session: {episode.session_id.slice(0, 8)}…
      </p>
    </div>
  );
}

function KnowledgeCard({
  fact,
  onDelete,
}: {
  fact: KnowledgeFact;
  onDelete: (id: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const long = fact.content.length > 200;

  async function remove() {
    setDeleting(true);
    try {
      await fetch(`/api/memory/knowledge/${fact.id}`, { method: 'DELETE' });
      onDelete(fact.id);
    } finally {
      setDeleting(false);
    }
  }

  const confPct = Math.round(fact.confidence * 100);
  const confColor =
    confPct >= 90 ? 'text-green-400' : confPct >= 70 ? 'text-yellow-400' : 'text-red-400';

  return (
    <div className="bg-surface rounded-xl border border-border p-4">
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2 flex-wrap min-w-0">
          <span className="text-zinc-500 text-xs truncate max-w-[180px]" title={fact.source}>
            {fact.source}
          </span>
          <span className={`text-xs font-medium ${confColor}`}>{confPct}%</span>
          <span className="text-zinc-600 text-xs">
            {fact.created_at.slice(0, 10)}
          </span>
        </div>
        <button
          onClick={() => void remove()}
          disabled={deleting}
          title="Delete"
          className="text-zinc-600 hover:text-red-400 transition-colors flex-shrink-0 disabled:opacity-40"
        >
          <Trash2 size={13} />
        </button>
      </div>

      <div
        className={long ? 'cursor-pointer' : ''}
        onClick={() => long && setOpen((o) => !o)}
      >
        <p className="text-primary text-sm leading-relaxed">
          {open || !long ? fact.content : `${fact.content.slice(0, 200)}…`}
        </p>
        {long && (
          <span className="text-zinc-600 text-xs flex items-center gap-0.5 mt-1">
            {open ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
            {open ? 'collapse' : 'expand'}
          </span>
        )}
      </div>

      {fact.tags.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {fact.tags.map((t) => <Tag key={t} label={t} />)}
        </div>
      )}
    </div>
  );
}

export default function MemoryPanel() {
  const [tab, setTab] = useState<MemoryTab>('episodes');
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [knowledge, setKnowledge] = useState<KnowledgeFact[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  async function load(t = tab, q = search) {
    setLoading(true);
    setErr(null);
    try {
      const params = new URLSearchParams({ search: q, limit: '200' });
      const r = await fetch(`/api/memory/${t}?${params.toString()}`);
      if (!r.ok) throw new Error(String(r.status));
      const data = await r.json() as Episode[] | KnowledgeFact[];
      if (t === 'episodes') setEpisodes(data as Episode[]);
      else setKnowledge(data as KnowledgeFact[]);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, [tab]);

  function onSearch(val: string) {
    setSearch(val);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => void load(tab, val), 300);
  }

  function changeTab(t: MemoryTab) {
    setTab(t);
    setSearch('');
  }

  const count = tab === 'episodes' ? episodes.length : knowledge.length;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-4 px-6 py-4 border-b border-border flex-shrink-0">
        <h2 className="text-primary font-semibold">Memory</h2>

        {/* Tabs */}
        <div className="flex gap-1">
          {(['episodes', 'knowledge'] as MemoryTab[]).map((t) => (
            <button
              key={t}
              onClick={() => changeTab(t)}
              className={`px-3 py-1 rounded text-xs capitalize transition-colors ${
                tab === t
                  ? 'bg-accent/20 text-accent'
                  : 'text-muted hover:text-primary'
              }`}
            >
              {t}
            </button>
          ))}
        </div>

        {/* Search */}
        <input
          value={search}
          onChange={(e) => onSearch(e.target.value)}
          placeholder="Search…"
          className="ml-2 bg-elevated border border-border rounded-lg px-3 py-1.5 text-xs text-primary placeholder-muted outline-none focus:border-accent/50 w-48"
        />

        <div className="ml-auto flex items-center gap-3">
          <span className="text-zinc-600 text-xs">{count} entries</span>
          <button
            onClick={() => void load()}
            title="Refresh"
            className={`text-muted hover:text-primary transition-colors ${loading ? 'animate-spin' : ''}`}
          >
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {err && <p className="text-red-400 text-sm mb-4">Failed to load: {err}</p>}

        {!loading && count === 0 && !err && (
          <p className="text-muted text-sm">
            {search ? 'No results for that search.' : `No ${tab} yet.`}
          </p>
        )}

        <div className="space-y-3 max-w-2xl">
          {tab === 'episodes' &&
            episodes.map((e) => (
              <EpisodeCard
                key={e.id}
                episode={e}
                onDelete={(id) => setEpisodes((prev) => prev.filter((x) => x.id !== id))}
              />
            ))}

          {tab === 'knowledge' &&
            knowledge.map((f) => (
              <KnowledgeCard
                key={f.id}
                fact={f}
                onDelete={(id) => setKnowledge((prev) => prev.filter((x) => x.id !== id))}
              />
            ))}
        </div>
      </div>
    </div>
  );
}
