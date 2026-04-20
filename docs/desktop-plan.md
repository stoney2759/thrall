# Thrall Desktop — Plan

**Status:** Shelved. Backend phases complete first.  
**Repo:** `thrall-desktop` (separate, merged into monorepo at official release)

---

## Vision

The desktop app is Thrall's primary interface. No Telegram setup required.
Download → Install → Open → Talk. Two minutes to running.

Telegram, Discord, Slack remain optional transports enabled via config.
The web dashboard is the same React frontend served by the Python backend for remote access.

---

## Two Deployment Contexts

```
Local (desktop)
  Tauri app → ws://localhost → Thrall on same machine
  Token stored in OS keyring

Remote (VPS — any OS)
  Tauri app → wss:// (TLS via nginx/Caddy) → Thrall on server
  User pastes token into first-run wizard, stored in OS keyring
```

---

## Security Model

**Token-based authentication — cross-platform:**

- Thrall generates a random 32-byte token on first run
- Stored in `.env` as `DESKTOP_TOKEN` (plaintext on server side, in-memory only at runtime)
- Desktop app stores token in OS keyring via Tauri `keyring` crate:
  - Windows  → DPAPI
  - macOS    → Keychain
  - Linux    → libsecret / KWallet
- Every WebSocket connection sends: `Authorization: Bearer <token>`
- Backend validates on connect — reject immediately if invalid
- Token never written to disk in plaintext on the client side
- Revocable: delete and regenerate via `/restart` or dedicated command

**TLS for remote:**
- Handled by reverse proxy (nginx or Caddy) — not in Python
- Python backend serves plain WebSocket, proxy terminates TLS
- Same token auth applies regardless of local or remote

---

## Tech Stack

```
thrall-desktop/
├── src-tauri/        Rust — process manager, keyring, sidecar, tray, hotkeys
├── src/              React + TypeScript + Tailwind CSS + Zustand
│   ├── components/
│   ├── panels/
│   ├── platform/     platform.ts abstraction (desktop vs web no-ops)
│   └── styles/
├── package.json
├── tauri.conf.json
└── README.md
```

- **Tauri 2.0** — native shell, ~5MB distributable, aligns with Rust roadmap
- **React + TypeScript** — shared with web dashboard
- **Tailwind CSS** — rapid, consistent, LLM-product aesthetic
- **Zustand** — lightweight state
- **WebSocket** — real-time event feed from Thrall backend
- **keyring crate** — OS secret store abstraction (one API, three OS implementations)

---

## Design Language

Inspired by Claude.ai, ChatGPT, Gemini — familiar to the tinkerer audience:

- Left sidebar — narrow, icon + label nav, grouped sections
- Top bar — logo, Thrall status, active model, token cost, tasks running
- Large content area — clean, breathing room, content-forward
- Dark-first — near-black backgrounds, subtle surface layering (not pure black)
- Typography — Inter (sans), monospace for technical output
- No heavy borders — depth from background shade differences
- Real-time feel — live indicators, WebSocket-driven updates

---

## Desktop App Panels

**Primary interface:**
- Chat — talk to Thrall directly (replaces Telegram as default transport)

**Mission control:**
- Control — Thrall status, active tasks, worker activity
- Scheduler — running jobs, cron, history
- Agents — catalog, active agents, spawn
- Memory — episodic + semantic browser
- Audit — tool gate log, security events
- Cost — token usage, provider spend
- Workspace — file browser, editor
- Config — edit config.toml + .env with validation (no manual file editing)

**Not included:**
- Org tree (Thrall 1.0 concept, irrelevant to 2.0 hierarchy)
- Redundant chat-in-dashboard (web dashboard defers to Telegram)

---

## Native OS Features (Desktop Only)

- System tray — Thrall lives in tray, minimizes there
- Native toast notifications — task complete, approval needed, scheduler fired
- Process manager — start/stop/restart Thrall backend from the app
- Auto-launch on Windows startup
- Global hotkey — surface window from anywhere
- Local config editor — edit config.toml + .env with validation
- Drag-and-drop files into workspace
- Offline awareness — detects if backend died, offers restart

---

## platform.ts Abstraction

Native features are gated behind a thin abstraction:

```typescript
// desktop: real implementation via Tauri invoke()
// web: no-ops or browser equivalents
platform.notify(title, body)
platform.openInTray()
platform.restartBackend()
platform.readToken()
```

Web dashboard gets no-ops. One React codebase serves both.

---

## Phased Build Order

```
Phase A — transports/desktop/ + server/app.py
          WebSocket transport, token validation, event stream
          REST routes for panels

Phase B — Tauri shell
          Boots Python as sidecar, basic window, proven connectivity
          Connection status indicator only

Phase C — First-run wizard
          Local vs remote connection choice
          API key entry, model selection, Thrall name
          Token generation and keyring storage

Phase D — Chat panel
          Primary interface — talks to Thrall via desktop transport
          Message history, streaming responses

Phase E — Mission control panels
          Control, Scheduler, Agents, Memory, Audit, Cost, Workspace, Config

Phase F — Native OS features
          Tray, notifications, global hotkey, auto-start, drag-and-drop

Phase G — Web dashboard parity
          Same React frontend served by backend at localhost:8000
          No native features — platform.ts no-ops
```

End of Phase D = something a tinkerer can download and use immediately.
Phases E–G = what makes it compelling to keep, share, and star.

---

## Release Strategy

- `thrall` and `thrall-desktop` ship as separate repos during development
- At official public release: evaluate monorepo vs coordinated dual-repo release
- Installer bundles both — user downloads one thing, gets everything
