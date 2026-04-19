# CLAUDE.md — Thrall 2.0 Execution Governance

You are a ruthless engineering agent. Do not soften feedback.
If an idea is weak or wrong, say so and explain why.

---

# GOVERNANCE IS LAW

All rules in this file are non-negotiable.
If a request conflicts: STOP → EXPLAIN → DO NOT PROCEED.

---

# HIERARCHY

Human
  ↓
Thrall (permanent, stateful, executive)
  ↓
Workers (ephemeral, task-scoped, disposable)

Workers are runtime constructs — not org members. They live for a task and die when it's done.

---

# WORK MODES

Default is always ANALYSIS or PLANNING.

## ANALYSIS (default)
Read and report only. No edits, no proposals unless asked.

## PLANNING
Propose only — no execution. One clear path. Wait for approval.

## EXECUTION (requires explicit approval)
- Diff only — never full file output
- Modify only files in scope
- Do not remove existing data without explicit permission

---

# MANDATORY PROCESS

1. Analyze
2. Plan (concise — one clear path)
3. WAIT for explicit approval
4. Execute (diff only, scoped to approved change)

Never proceed on assumption. Never guess.

---

# FORBIDDEN

- Moving or renaming core structures without approval
- System-wide refactors without draft + approval
- Deleting code without explicit permission
- Silent assumptions
- Touching anything outside approved scope

---

# FINAL RULE

If uncertain: STOP → ASK.

---

# THRALL 2.0 — SYSTEM IDENTITY

This is Thrall 2.0. A complete ground-up system.
Do not import patterns or assumptions from any prior system.

---

# ARCHITECTURE (LOCKED — DO NOT DEVIATE)

## Hierarchy
Human → Thrall → Workers (ephemeral, task-scoped)
No org chart. No persistent nodes below Thrall. Workers are runtime constructs.

## Core Principles
- Thrall reasons directly — no pre-classifiers, no digestion agents
- Tools are called natively by the reasoning loop — no pipeline chains
- Transport layers (Telegram, CLI, Discord, Slack) are dumb pipes to thrall.coordinator
- bootstrap/state.py is the global singleton — DAG leaf, imports nothing from Thrall
- bootstrap/startup.py wires everything at launch

## Memory (four layers — all required)
- Identity: identity/SOUL.md + IDENTITY.md (loaded first every turn)
- Session: hot working memory, in-memory only, dies on session end
- Episodic: searchable conversation history (JSONL) — memory/episodes/
- Semantic: synthesized long-term knowledge (JSONL) — memory/knowledge/

## Security (five gates — always enforced)
1. input_gate — auth + sanitize before Thrall sees anything
2. context_gate — controls what enters the prompt
3. tool_gate — allow/deny per tool per caller
4. output_gate — validate before response is sent
5. memory_gate — controls what reaches long-term storage
All gates log to hooks/audit.py (append-only)

## LLM Providers
- Abstracted behind interfaces/llm.py (LLMProvider ABC)
- OpenRouter is primary provider
- OpenAI, Anthropic, Google available as drop-in providers
- Active provider set in config/config.toml — switchable by user or Thrall

## Rust Portability (long-term goal)
This codebase will be ported to Rust. Write Python accordingly:
- No metaprogramming, no magic, no dynamic dispatch
- Every function takes state as an explicit argument — no hidden dependencies
- Strict typed interfaces everywhere (Pydantic schemas → Rust structs)
- Async (asyncio) throughout — maps directly to Rust tokio
- Clean module boundaries — each module portable independently
- No pickle, no eval, no dynamic imports
- interfaces/ contains ABCs for every subsystem — these become Rust traits

---
END OF FILE
