import { useEffect, useState } from 'react';
import { RefreshCw, X } from 'lucide-react';

interface AgentTask {
  id: string;
  profile: string;
  status: string;
  brief: string;
  created_at: string;
}

const STATUS_COLORS: Record<string, string> = {
  running: 'bg-green-900/40 text-green-400',
  pending: 'bg-yellow-900/40 text-yellow-400',
  done:    'bg-zinc-800 text-zinc-400',
  failed:  'bg-red-900/40 text-red-400',
};

export default function AgentsPanel() {
  const [agents, setAgents] = useState<AgentTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [killing, setKilling] = useState<Set<string>>(new Set());

  async function load() {
    setLoading(true);
    setErr(null);
    try {
      const r = await fetch('/api/agents');
      if (!r.ok) throw new Error(`${r.status}`);
      setAgents(await r.json() as AgentTask[]);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }

  async function kill(id: string) {
    setKilling(prev => new Set(prev).add(id));
    setAgents(prev => prev.filter(a => a.id !== id));
    try {
      await fetch(`/api/agents/${id}`, { method: 'DELETE' });
    } finally {
      setKilling(prev => { const s = new Set(prev); s.delete(id); return s; });
    }
  }

  useEffect(() => {
    void load();
    const t = setInterval(() => void load(), 5_000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="p-6 max-w-2xl">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-primary font-semibold">Agents</h2>
        <button
          onClick={() => void load()}
          title="Refresh"
          className={`text-muted hover:text-primary transition-colors ${loading ? 'animate-spin' : ''}`}
        >
          <RefreshCw size={14} />
        </button>
      </div>

      {err && <p className="text-red-400 text-sm mb-4">Failed to load: {err}</p>}

      {!loading && agents.length === 0 && !err && (
        <p className="text-muted text-sm">No active agents.</p>
      )}

      <div className="space-y-3">
        {agents.map((a) => (
          <div key={a.id} className="bg-surface rounded-xl border border-border p-4">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-primary text-sm font-medium">{a.profile}</span>
              <div className="flex items-center gap-2">
                <span
                  className={`text-xs px-2 py-0.5 rounded-full ${STATUS_COLORS[a.status] ?? 'bg-zinc-800 text-zinc-400'}`}
                >
                  {a.status}
                </span>
                {(a.status === 'running' || a.status === 'pending') && (
                  <button
                    onClick={() => void kill(a.id)}
                    disabled={killing.has(a.id)}
                    title="Kill task"
                    className="text-zinc-600 hover:text-red-400 transition-colors disabled:opacity-40"
                  >
                    <X size={14} />
                  </button>
                )}
              </div>
            </div>
            <p className="text-muted text-xs leading-relaxed">
              {a.brief.length > 140 ? `${a.brief.slice(0, 140)}…` : a.brief}
            </p>
            <p className="text-zinc-600 text-xs mt-1.5">
              {new Date(a.created_at).toLocaleTimeString()}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
