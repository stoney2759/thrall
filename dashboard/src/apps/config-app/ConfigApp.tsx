// ============================================================
// ConfigApp.tsx — Live config viewer (read-only)
//
// system  — governance, security, debug flags + restart button
// nodes   — context load rules per node type × scope
// llm     — model tiers, cost mode, budget, escalation
//
// Config is READ-ONLY from the dashboard.
// Changes require editing config/config.toml and restarting.
// ============================================================

import React, { useEffect, useState, useCallback } from "react";
import { getConfig, adminRestart } from "../../api/client";

// ── Fetch helper ─────────────────────────────────────────────

type Cfg = Record<string, unknown>;

function nested(cfg: Cfg, key: string): Cfg {
  return (cfg[key] as Cfg) ?? {};
}

function str(v: unknown, fallback = "—"): string {
  if (v === null || v === undefined) return fallback;
  return String(v);
}

function bool(v: unknown): boolean {
  return v === true || v === "true";
}

// ── Shared card ──────────────────────────────────────────────

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="config-card">
      <div className="config-card-title">{title}</div>
      <div className="config-card-body">{children}</div>
    </div>
  );
}

function Row({ label, value, ok, warn }: { label: string; value: string; ok?: boolean; warn?: boolean }) {
  const cls = ok ? "cfg-val-ok" : warn ? "cfg-val-warn" : "cfg-val";
  return (
    <div className="config-row">
      <span className="cfg-label">{label}</span>
      <span className={cls}>{value}</span>
    </div>
  );
}

function BoolRow({ label, value, okWhenTrue = true }: { label: string; value: unknown; okWhenTrue?: boolean }) {
  const b = bool(value);
  const isOk = okWhenTrue ? b : !b;
  return <Row label={label} value={b ? "YES" : "NO"} ok={isOk} warn={!isOk} />;
}

// ── System view ──────────────────────────────────────────────

function SystemView({ cfg }: { cfg: Cfg }) {
  const gov = nested(cfg, "governance");
  const thr = nested(gov, "thresholds") as Cfg;
  const sec = nested(cfg, "security");
  const dbg = nested(cfg, "debug");
  const str2 = nested(cfg, "structural");

  const [restarting, setRestarting] = useState(false);
  const [restartMsg, setRestartMsg] = useState<string | null>(null);

  const handleRestart = async () => {
    if (!confirm("Restart the OpenThrall server?")) return;
    setRestarting(true);
    setRestartMsg(null);
    const r = await adminRestart();
    setRestarting(false);
    setRestartMsg(r.ok ? "Server restarting…" : r.error);
  };

  const authorityMode = str(gov.authority_mode);

  return (
    <div className="config-grid">
      <Card title="GOVERNANCE">
        <Row
          label="Authority Mode"
          value={authorityMode}
          ok={authorityMode === "MANUAL"}
          warn={authorityMode === "AUTONOMOUS"}
        />
        <Row label="Auto Budget Shift" value={`${str(thr.max_auto_budget_shift_percent)}%`} />
        <Row label="Auto Token Escalation" value={str(thr.max_auto_token_escalation)} />
        <BoolRow label="Self-Mod Requires User" value={thr.requires_user_for_self_modification} />
        <BoolRow label="Structural Changes Require User" value={thr.structural_changes_require_user} />
      </Card>

      <Card title="STRUCTURAL">
        <BoolRow label="Allow Chief Proposals" value={str2.allow_chief_proposals} />
        <BoolRow label="Require Peer Consensus" value={str2.require_peer_consensus} okWhenTrue={false} />
        <Row label="Max Proposals / Cycle" value={str(str2.max_proposals_per_cycle)} />
        <Row label="Cycle Seconds" value={str(str2.cycle_seconds)} />
      </Card>

      <Card title="SECURITY">
        <BoolRow label="Redact Secrets in Logs" value={sec.redact_secrets_in_logs} />
        <BoolRow label="Block Secrets in Workspace" value={sec.block_secrets_in_workspace_files} />
        <BoolRow label="Allow Web Browsing" value={sec.allow_web_browsing} okWhenTrue={false} />
        <BoolRow label="Allow Code Execution" value={sec.allow_code_execution} okWhenTrue={false} />
        <BoolRow label="Allow File Writes" value={sec.allow_file_writes} />
      </Card>

      <Card title="DEBUG">
        <BoolRow label="Debug Enabled" value={dbg.enabled} />
        <Row label="Log Path" value={str(dbg.log_jsonl_path)} />
        <BoolRow label="Include Prompt Preview" value={dbg.include_prompt_preview} />
        <BoolRow label="Include Raw LLM Response" value={dbg.include_raw_llm_response} />
      </Card>

      <Card title="SERVER">
        <div className="config-row">
          <span className="cfg-label">Config file changes require a restart to take effect.</span>
        </div>
        <div className="config-row" style={{ marginTop: 8 }}>
          <button
            className="btn-deny"
            onClick={handleRestart}
            disabled={restarting}
          >
            {restarting ? "Restarting…" : "⟳ RESTART SERVER"}
          </button>
          {restartMsg && (
            <span className="cfg-val" style={{ marginLeft: 10 }}>{restartMsg}</span>
          )}
        </div>
      </Card>
    </div>
  );
}

// ── Nodes / context rules view ───────────────────────────────

function NodesView({ cfg }: { cfg: Cfg }) {
  const ws = nested(cfg, "workspace");
  const rules = (ws.context_load_rules as Cfg[]) ?? [];

  const nodeTypes = Array.from(new Set(rules.map((r) => str(r.node_type)))).sort();
  const [filterType, setFilterType] = useState("");

  const filtered = filterType ? rules.filter((r) => str(r.node_type) === filterType) : rules;

  return (
    <div className="panel" style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div className="panel-header">
        <span className="panel-title">CONTEXT LOAD RULES</span>
        <span className="panel-count">{filtered.length} rules</span>
        <select
          className="audit-filter-select"
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
        >
          <option value="">All node types</option>
          {nodeTypes.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>
      <div className="panel-body" style={{ overflowY: "auto" }}>
        {rules.length === 0 && (
          <div className="empty-state">No context load rules defined.</div>
        )}
        <table className="data-table" style={{ fontSize: 11 }}>
          <thead>
            <tr>
              <th>NODE TYPE</th>
              <th>SCOPE</th>
              <th>ALLOWED FILES</th>
              <th>MAX CHARS</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((r, i) => (
              <tr key={i}>
                <td><span className={`node-badge node-${str(r.node_type).toLowerCase()}`}>{str(r.node_type)}</span></td>
                <td className="td-mono td-dim">{str(r.context_scope)}</td>
                <td>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 3 }}>
                    {((r.allowed_files as string[]) ?? []).map((f) => (
                      <span key={f} className="cfg-file-tag">{f}</span>
                    ))}
                  </div>
                </td>
                <td className="td-mono">{Number(r.max_total_chars).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── LLM view ─────────────────────────────────────────────────

function LlmView({ cfg }: { cfg: Cfg }) {
  const cost = nested(cfg, "cost");
  const tiers = nested(cost, "model_tiers") as Cfg;
  const esc = nested(cost, "escalation") as Cfg;

  return (
    <div className="config-grid">
      <Card title="MODEL TIERS">
        <Row label="Cheap" value={str(tiers.cheap)} />
        <Row label="Standard" value={str(tiers.standard)} />
        <Row label="Premium" value={str(tiers.premium)} />
      </Card>

      <Card title="COST POLICY">
        <Row label="Mode" value={str(cost.mode)} />
        <BoolRow label="Hard Limit Enforced" value={cost.hard_limit_enforced} />
        <Row label="Daily Budget (tokens)" value={Number(cost.daily_budget_tokens).toLocaleString()} />
        <Row label="Alert Threshold" value={`${str(cost.alert_threshold_percent)}%`} />
      </Card>

      <Card title="ESCALATION">
        <Row label="Confidence Threshold" value={str(cost.confidence_threshold ?? esc.confidence_threshold)} />
        <Row label="Max Escalations" value={str(cost.max_escalations ?? esc.max_escalations)} />
      </Card>
    </div>
  );
}

// ── App dispatcher ───────────────────────────────────────────

interface Props { activeView: string; }

export function ConfigApp({ activeView }: Props) {
  const [cfg, setCfg] = useState<Cfg | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const r = await getConfig();
    setLoading(false);
    if (!r.ok) { setError(r.error); return; }
    setCfg(r.data);
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return <div className="empty-state">Loading config…</div>;
  if (error)   return <div className="panel-error" style={{ margin: 16 }}>FETCH ERROR: {error}</div>;
  if (!cfg)    return <div className="empty-state">No config loaded.</div>;

  switch (activeView) {
    case "system": return <SystemView cfg={cfg} />;
    case "nodes":  return <NodesView cfg={cfg} />;
    case "llm":    return <LlmView cfg={cfg} />;
    default:       return <SystemView cfg={cfg} />;
  }
}
