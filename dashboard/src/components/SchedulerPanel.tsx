import { useEffect, useState } from 'react';
import { RefreshCw, Plus, Trash2, Power } from 'lucide-react';

type JobType = 'cron' | 'heartbeat' | 'job';
type Tab = 'overview' | JobType;

interface Job {
  id: string;
  type: string;
  schedule: string;
  schedule_summary: string;
  task: string;
  enabled: boolean;
  last_run: string | null;
  agent: string | null;
}

// ── Stat card ────────────────────────────────────────────────────────────────

function StatCard({ label, enabled, total }: { label: string; enabled: number; total: number }) {
  return (
    <div className="bg-surface border border-border rounded-xl p-4">
      <p className="text-muted text-xs mb-1">{label}</p>
      <p className="text-primary text-2xl font-semibold">{enabled}</p>
      <p className="text-zinc-600 text-xs mt-0.5">{total} total</p>
    </div>
  );
}

// ── Overview tab ─────────────────────────────────────────────────────────────

function Overview({ jobs }: { jobs: Job[] }) {
  const byType = (t: string) => jobs.filter((j) => j.type === t);
  const enabledCount = (t: string) => byType(t).filter((j) => j.enabled).length;

  const recent = [...jobs]
    .filter((j) => j.last_run)
    .sort((a, b) => (b.last_run! > a.last_run! ? 1 : -1))
    .slice(0, 6);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-3 gap-3">
        <StatCard label="Cron" enabled={enabledCount('cron')} total={byType('cron').length} />
        <StatCard label="Heartbeat" enabled={enabledCount('heartbeat')} total={byType('heartbeat').length} />
        <StatCard label="Jobs" enabled={enabledCount('job')} total={byType('job').length} />
      </div>

      {recent.length > 0 && (
        <div>
          <p className="text-muted text-xs uppercase tracking-wider mb-3">Recent runs</p>
          <div className="space-y-2">
            {recent.map((j) => (
              <div key={j.id} className="flex items-center justify-between text-xs gap-4">
                <span className="text-primary truncate">{j.schedule_summary}</span>
                <span className="text-zinc-600 flex-shrink-0">{j.last_run!.slice(0, 16)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {jobs.length === 0 && (
        <p className="text-muted text-sm">No scheduled jobs.</p>
      )}
    </div>
  );
}

// ── Jobs tab (cron / heartbeat / job) ────────────────────────────────────────

function JobsTab({
  jobs,
  type,
  onRefresh,
}: {
  jobs: Job[];
  type: JobType;
  onRefresh: () => void;
}) {
  const [showForm, setShowForm] = useState(false);
  const [schedule, setSchedule] = useState('');
  const [task, setTask] = useState('');
  const [agent, setAgent] = useState('');
  const [creating, setCreating] = useState(false);
  const [createErr, setCreateErr] = useState<string | null>(null);

  const filtered = jobs.filter((j) => j.type === type);

  const placeholder =
    type === 'heartbeat'
      ? 'Interval — e.g. 30m, 1h, every 15 minutes'
      : 'Schedule — e.g. every day at 9am, 0 9 * * 1-5';

  async function create() {
    if (!schedule.trim() || !task.trim()) return;
    setCreating(true);
    setCreateErr(null);
    try {
      const r = await fetch('/api/scheduler/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          schedule: schedule.trim(),
          task: task.trim(),
          agent: agent.trim() || null,
          type,
        }),
      });
      if (!r.ok) {
        const body = (await r.json()) as { error?: string };
        throw new Error(body.error ?? String(r.status));
      }
      setSchedule('');
      setTask('');
      setAgent('');
      setShowForm(false);
      onRefresh();
    } catch (e) {
      setCreateErr(String(e));
    } finally {
      setCreating(false);
    }
  }

  async function toggle(id: string) {
    await fetch(`/api/scheduler/jobs/${id}/toggle`, { method: 'PATCH' });
    onRefresh();
  }

  async function remove(id: string) {
    await fetch(`/api/scheduler/jobs/${id}`, { method: 'DELETE' });
    onRefresh();
  }

  return (
    <div className="space-y-4">
      {/* Create form */}
      {showForm ? (
        <div className="bg-surface border border-border rounded-xl p-4 space-y-3">
          <input
            value={schedule}
            onChange={(e) => setSchedule(e.target.value)}
            placeholder={placeholder}
            className="w-full bg-elevated rounded-lg border border-border px-3 py-2 text-sm text-primary placeholder-muted outline-none focus:border-accent/50"
          />
          <textarea
            value={task}
            onChange={(e) => setTask(e.target.value)}
            placeholder="Task description"
            rows={2}
            className="w-full bg-elevated rounded-lg border border-border px-3 py-2 text-sm text-primary placeholder-muted outline-none resize-none focus:border-accent/50"
          />
          <input
            value={agent}
            onChange={(e) => setAgent(e.target.value)}
            placeholder="Agent profile (optional)"
            className="w-full bg-elevated rounded-lg border border-border px-3 py-2 text-sm text-primary placeholder-muted outline-none focus:border-accent/50"
          />
          {createErr && (
            <p className="text-red-400 text-xs leading-relaxed">{createErr}</p>
          )}
          <div className="flex gap-2">
            <button
              onClick={() => void create()}
              disabled={creating || !schedule.trim() || !task.trim()}
              className="flex-1 bg-accent hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm rounded-lg py-1.5 transition-colors"
            >
              {creating ? 'Parsing schedule…' : 'Create'}
            </button>
            <button
              onClick={() => { setShowForm(false); setCreateErr(null); }}
              className="px-3 py-1.5 text-muted hover:text-primary rounded-lg border border-border text-sm transition-colors"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <button
          onClick={() => setShowForm(true)}
          className="flex items-center gap-1.5 text-muted hover:text-primary text-sm transition-colors"
        >
          <Plus size={14} />
          <span>Add {type}</span>
        </button>
      )}

      {/* List */}
      {filtered.length === 0 && !showForm && (
        <p className="text-muted text-sm">No {type} jobs.</p>
      )}

      <div className="space-y-2">
        {filtered.map((j) => (
          <div
            key={j.id}
            className={`bg-surface rounded-xl border p-4 transition-opacity ${
              j.enabled ? 'border-border' : 'border-border/40 opacity-55'
            }`}
          >
            <div className="flex items-start justify-between gap-2 mb-1.5">
              <span className="text-primary text-sm font-medium leading-snug">
                {j.schedule_summary}
              </span>
              <div className="flex items-center gap-2 flex-shrink-0">
                <button
                  onClick={() => void toggle(j.id)}
                  title={j.enabled ? 'Disable' : 'Enable'}
                  className={`transition-colors ${
                    j.enabled
                      ? 'text-green-400 hover:text-zinc-500'
                      : 'text-zinc-600 hover:text-green-400'
                  }`}
                >
                  <Power size={13} />
                </button>
                <button
                  onClick={() => void remove(j.id)}
                  title="Delete"
                  className="text-zinc-600 hover:text-red-400 transition-colors"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            </div>
            <p className="text-muted text-xs leading-relaxed">
              {j.task.length > 120 ? `${j.task.slice(0, 120)}…` : j.task}
            </p>
            <div className="flex items-center gap-3 mt-1.5">
              {j.agent && (
                <span className="text-zinc-600 text-xs">agent: {j.agent}</span>
              )}
              {j.last_run && (
                <span className="text-zinc-600 text-xs">
                  last: {j.last_run.slice(0, 16)}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Root panel ────────────────────────────────────────────────────────────────

const TABS: { id: Tab; label: string }[] = [
  { id: 'overview',   label: 'Overview' },
  { id: 'cron',       label: 'Cron' },
  { id: 'heartbeat',  label: 'Heartbeat' },
  { id: 'job',        label: 'Jobs' },
];

export default function SchedulerPanel() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>('overview');

  async function load() {
    setLoading(true);
    setErr(null);
    try {
      const r = await fetch('/api/scheduler');
      if (!r.ok) throw new Error(String(r.status));
      setJobs((await r.json()) as Job[]);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);

  return (
    <div className="p-6 max-w-2xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-primary font-semibold">Scheduler</h2>
        <button
          onClick={() => void load()}
          title="Refresh"
          className={`text-muted hover:text-primary transition-colors ${loading ? 'animate-spin' : ''}`}
        >
          <RefreshCw size={14} />
        </button>
      </div>

      {/* Tab bar */}
      <div className="flex gap-0 mb-6 border-b border-border">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-4 py-2 text-sm transition-colors -mb-px ${
              tab === t.id
                ? 'text-primary border-b-2 border-accent'
                : 'text-muted hover:text-primary'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {err && <p className="text-red-400 text-sm mb-4">Failed to load: {err}</p>}

      {!loading && (
        <>
          {tab === 'overview'  && <Overview jobs={jobs} />}
          {tab === 'cron'      && <JobsTab jobs={jobs} type="cron"      onRefresh={() => void load()} />}
          {tab === 'heartbeat' && <JobsTab jobs={jobs} type="heartbeat" onRefresh={() => void load()} />}
          {tab === 'job'       && <JobsTab jobs={jobs} type="job"       onRefresh={() => void load()} />}
        </>
      )}
    </div>
  );
}
