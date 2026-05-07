# Thrall

A permanent, stateful autonomous agent with a desktop webapp, voice, vision, and real tool use.

Thrall is not a chatbot wrapper. It's an executive layer with memory, tools, and judgment. It reasons, acts, spawns sub-agents, and remembers across sessions. Run it from the desktop app, CLI, or Telegram — your choice.

---

## What It Does

- **Desktop webapp** — React/Vite dashboard with concurrent isolated sessions, live over WebSocket
- **Autonomous reasoning loop** — parallel tool execution, up to 100 iterations in approved mode
- **55 native tools** — filesystem, web, browser automation, code execution, media, vision, memory, scheduling, clipboard, documents, notebooks, IDE diagnostics, and more
- **14 core catalog agents** — named specialists Thrall delegates to automatically
- **MCP integration** — connect any Model Context Protocol server (GitHub, Gmail, Google Calendar, Drive, and more)
- **Four-layer persistent memory** — identity, session, episodic, and semantic
- **Five-gate security model** — input sanitization, context control, tool permissions, output scrubbing, memory validation
- **Scheduled jobs** — natural language cron and heartbeat intervals
- **Voice I/O** — speech-to-text (Groq/OpenAI/OpenRouter) + text-to-speech (ElevenLabs/OpenAI) with cost gating and caching
- **Vision** — image and video frame analysis via dedicated vision model
- **Video pipeline** — download (yt-dlp), process (ffmpeg), transcribe, extract frames, analyse
- **Browser automation** — full Playwright session with screenshot + vision description flow
- **Multi-transport** — desktop webapp, CLI, Telegram, Discord/Slack (wired, disabled by default)

---

## Stack

- Python 3.12+
- FastAPI + React/Vite — desktop webapp (primary interface)
- [OpenRouter](https://openrouter.ai) — primary LLM provider (OpenAI, Anthropic, Google, DeepSeek, and more)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Playwright](https://playwright.dev/python/) — browser automation
- ElevenLabs / OpenAI — TTS
- yt-dlp + ffmpeg — video pipeline
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) — Telegram transport (optional)

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/stoney2759/thrall.git
cd thrall
python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate  # Unix
pip install -r requirements.txt
```

### 2. Configure

```bash
cp config/config.example.toml config/config.toml
cp .env.example .env
```

Edit `config/config.toml`:
- Set your Telegram user ID in `[transports.telegram] allowed_user_ids`
- Set your GitHub username in `[user]`
- Choose your LLM model under `[llm]`
- Enable any MCP servers under `[[mcp.servers]]`

Edit `.env`:
- `OPENROUTER_API_KEY` — required, primary LLM provider
- `THRALL_DESKTOP_TOKEN` — secures the desktop WebSocket endpoint
- `SERPER_API_KEY` or `BRAVE_API_KEY` — web search
- `GROQ_API_KEY` — fast speech-to-text (free tier)
- `ELEVENLABS_API_KEY` — text-to-speech
- `TELEGRAM_BOT_TOKEN` — only needed if using Telegram transport

### 3. Run

```powershell
# Windows — full stack (API + Dashboard + Telegram)
.\start.ps1

# Desktop webapp only (recommended starting point)
.\start-api.ps1
.\start-dashboard.ps1

# Telegram only
.\start-telegram.ps1
```

Open `http://localhost:8000` to access the dashboard.

---

## Commands

| Command | Description |
|---|---|
| `/help` | List all commands |
| `/status` | Active tasks, cost, model, uptime |
| `/approve` | Approve a pending proposal and execute the plan |
| `/stop` | Cancel the currently running task |
| `/model <name>` | Switch LLM model |
| `/tasks` | List active agent tasks |
| `/jobs` | List scheduled jobs |
| `/cron <schedule> <task>` | Add a scheduled job (e.g. `/cron 9am every Monday <task>`) |
| `/heartbeat <interval> <task>` | Add a recurring interval job (e.g. `/heartbeat 30m <task>`) |
| `/deljob <id>` | Delete a scheduled job |
| `/compact` | Compact session memory — summarises and trims context |
| `/cost` | Token usage and spend breakdown |
| `/clear` | Clear session memory |
| `/memory [list\|search <query>]` | Inspect session memory |
| `/health` | System health, errors, and diagnostics |
| `/restart` | Reload config and reinitialise all services |
| `/profile [name]` | Switch Thrall's active personality profile |
| `/watch <url>` | Download, transcribe, extract frames, and analyse a video |
| `/voice` | Toggle voice response mode (Telegram) |

---

## Tools (55)

### Filesystem (12)
`filesystem_read` `filesystem_write` `filesystem_edit` `filesystem_append` `filesystem_glob` `filesystem_grep` `filesystem_find` `filesystem_cat` `filesystem_ls` `filesystem_tree` `filesystem_stat` `filesystem_diff`

### Web (4)
`web_fetch` `web_search` `web_scrape` `web_browse`

### Browser Automation (6)
`browser_navigate` `browser_screenshot` `browser_click` `browser_fill` `browser_extract` `browser_close`

Full Playwright session with persistent user profile support. Screenshots feed directly into vision analysis.

### Code & Shell (3)
`code_execute` — Python subprocess sandbox  
`shell_run` — Shell command, cwd defaults to workspace  
`powershell_run` — Windows-native PowerShell execution

### Agents (7)
`agents_create` `agents_spawn` `agents_result` `agents_await_all` `agents_list` `agents_prepare` `workers_spawn`

Spawn named catalog agents or ephemeral workers. Parallel execution via asyncio.

### Memory (2)
`memory_read` `memory_write` — episodic and semantic layers, keyword search supported

### Audio & Media (4)
`audio_generate` — TTS via ElevenLabs or OpenAI, with caching and cost gate  
`transcription_run` — Speech-to-text (mp3, wav, m4a, ogg, flac)  
`video_download` — yt-dlp wrapper, supports metadata/audio-only extraction  
`video_ffmpeg` — probe, convert, extract audio, trim, thumbnail, extract frames, concat, compress, GIF

### Vision (1)
`vision_analyze` — Image analysis via dedicated vision model (not the coordinator model)

### Git (1)
`git_run` — Any git command; destructive operations require `confirmed=true`

### Clipboard (5)
`clipboard_read` `clipboard_write` `clipboard_save` `clipboard_load` `clipboard_snippets`

### Scheduler (3)
`scheduler_add` `scheduler_list` `scheduler_delete` — cron and heartbeat job management

### Documents (2)
`documents_read_pdf` — PDF text extraction with page range support  
`documents_read_docx` — Word document extraction with heading structure

### Notebook (2)
`notebook_read` `notebook_edit` — Jupyter `.ipynb` read and cell editing

### IDE (1)
`ide_diagnostics` — Auto-selects ruff → mypy → pylint; force a specific tool with `tool=`

### Interaction (2)
`interaction_ask_user` — Blocking user prompt, waits for reply  
`interaction_monitor` — Run command and collect output, stops at pattern match or timeout

### System (2)
`system_info` — CPU, memory, disk, processes  
`profile_switch` — Switch active personality profile

---

## Agent Catalog

Thrall ships with 14 core agents. The system accepts any `.toml` agent definition dropped into `components/agents/catalog/` — Thrall picks it up automatically.

| Agent | Purpose |
|-------|---------|
| `analyst` | Research and summarise a topic or codebase area |
| `coder` | Implement a scoped code change |
| `python-coder` | Python-specific implementation |
| `typescript-coder` | TypeScript-specific implementation |
| `rust-coder` | Rust-specific implementation |
| `research-scout` | Fast targeted research across web or codebase |
| `todo-worker` | Work through a task list autonomously |
| `summariser` | Condense long content into structured summaries |
| `mcp-setup` | Guide MCP server discovery, install, and wiring |
| `agent-hunter` | Find the right agent for a task from the catalog |
| `video-downloader` | Download video from a URL via yt-dlp |
| `video-processor` | Extract frames and analyse video content |
| `youtube-transcriber` | Download and transcribe a YouTube video |
| `viral-signal-extractor` | Extract timestamp-cited virality signals (hooks, open loops, payoffs, CTAs) from video transcripts into structured JSON |

---

## Memory

Four layers, all configurable via `config/config.toml`:

| Layer | Backend options | Location |
|-------|----------------|----------|
| Identity | Files (always) | `identity/` — SOUL.md, IDENTITY.md, RULES.md, PERSONALITY.md |
| Session | In-process | RAM only — cleared on restart |
| Episodic | jsonl · session · redis | `memory/episodes/` |
| Semantic | jsonl · session · qdrant | `memory/knowledge/` |

- Auto-compacts at 200,000 tokens
- Episodic TTL: 7 days
- Synthesis interval: every 6 hours

---

## Security

Five gates, always enforced:

| Gate | Role |
|------|------|
| `input_gate` | Auth check, rate limiting (30 req/min), prompt injection sanitization |
| `context_gate` | Identity tamper detection, catalog injection, session assembly |
| `profile_gate` | Scans personality profiles for injection attempts before loading |
| `tool_gate` | Per-tool allow/deny per caller |
| `output_gate` | Scrubs API keys, tokens, secrets before any response is sent |
| `memory_gate` | Validates episodes and facts before long-term storage |

Secret display: `mask` (sk-or*...*a26) · `redact` (fully hidden) · `off`  
Audit log: append-only, 50MB max, 7-day retention.

---

## MCP Integrations

| Server | Status | Purpose |
|--------|--------|---------|
| github | Enabled | Repos, issues, PRs, code search |
| gmail | Disabled | Read, send, search email |
| google-calendar | Disabled | Events and scheduling |
| google-drive | Disabled | Files and documents |
| brave-search | Disabled | Web search via Brave API |

Enable any server in `config/config.toml` (`enabled = true`) and add credentials to `.env`.

---

## Architecture

```
Desktop WebSocket / CLI / Telegram
         ↓
    coordinator.py  (agentic loop — parallel tool execution via asyncio)
         ↓
  context_gate.py  (identity + memory + catalog injection)
         ↓
    LLM  (OpenRouter → any provider)
         ↓
  tool_gate → tool registry → 55 tools / MCP servers
                                    ↓
                          task pool → catalog agents (parallel)
```

### LLM Providers

Abstracted behind `interfaces/llm.py` — switch provider without touching code.

| Provider | Key env var |
|----------|-------------|
| OpenRouter (primary) | `OPENROUTER_API_KEY` |
| OpenAI | `OPENAI_API_KEY` |
| Anthropic | `ANTHROPIC_API_KEY` |
| Google | `GOOGLE_API_KEY` |

Agent worker tiers: `tier_capable` (Gemini 2.5 Flash) · `tier_lightweight` (gpt-4o-mini) · `tier_premium` (gpt-5-nano)

---

## License

MIT
