# Thrall

A permanent, stateful autonomous agent — built to run on Telegram and get real work done.

Thrall is not a chatbot wrapper. It's an executive layer with memory, tools, and judgment. It reasons, acts, spawns sub-agents, and remembers across sessions.

---

## What It Does

- **Autonomous reasoning loop** — up to 10 tool iterations per turn before responding
- **28 native tools** — filesystem, web search/fetch/scrape, code execution, memory read/write, agent spawning, shell, scheduler
- **MCP integration** — connect any Model Context Protocol server (GitHub, Gmail, Google Calendar, Drive, and more)
- **Persistent memory** — session, episodic, and semantic layers
- **Scheduled jobs** — natural language cron (`/cron 9am every Monday <task>`) and heartbeat intervals
- **Catalog agents** — named specialist agents that Thrall delegates to automatically
- **Telegram native** — voice, images, commands, all handled
- **Multi-transport** — Telegram (primary), CLI, Discord/Slack (wired, disabled by default)

---

## Stack

- Python 3.12+
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- [OpenRouter](https://openrouter.ai) (primary LLM provider — supports OpenAI, Anthropic, Google)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- FastAPI + React/Vite dashboard (optional)

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/stoney2759/thrall.git
cd thrall
python -m venv venv
venv/Scripts/activate  # Windows
# source venv/bin/activate  # Unix
pip install -r requirements.txt
```

### 2. Configure

```bash
cp config/config.example.toml config/config.toml
cp .env.example .env
```

Edit `config/config.toml`:
- Set your Telegram user ID in `allowed_user_ids`
- Set your GitHub username in `[user]`
- Enable any MCP servers you want under `[[mcp.servers]]`

Edit `.env`:
- Add your `TELEGRAM_BOT_TOKEN` (from [@BotFather](https://t.me/BotFather))
- Add at least one LLM provider key (`OPENROUTER_API_KEY` recommended)
- Add search key (`SERPER_API_KEY` or `BRAVE_API_KEY`) for web search
- Add MCP integration keys as needed

### 3. Run

```bash
python telegram_server.py
```

Or on Windows:
```powershell
.\start.ps1
```

---

## Commands

| Command | Description |
|---|---|
| `/help` | List all commands |
| `/status` | Active tasks, cost, model |
| `/model <name>` | Switch LLM model |
| `/tasks` | List active agent tasks |
| `/jobs` | List scheduled jobs |
| `/cron <schedule> <task>` | Add a scheduled job |
| `/heartbeat <interval> <task>` | Add a recurring job |
| `/deljob <id>` | Delete a job |
| `/compact` | Compact session memory |
| `/cost` | Token usage and spend |
| `/clear` | Clear session memory |
| `/health` | System health and errors |
| `/restart` | Reload config |

---

## MCP Integrations

Thrall supports any MCP-compatible server. Pre-configured entries (all disabled by default):

- **GitHub** — repos, issues, PRs, code search
- **Gmail** — read, send, search email
- **Google Calendar** — events, scheduling
- **Google Drive** — files and documents
- **Brave Search** — web search via Brave API

Enable any server in `config/config.toml` by setting `enabled = true` and adding the required credential to `.env`. Thrall's `mcp-setup` catalog agent can guide you through the process — just ask it to set up an integration by name.

---

## Architecture

```
Telegram → bot.py → coordinator.py (agentic loop)
                          ↓
                    context_gate.py (identity + memory + catalog)
                          ↓
                    LLM (OpenRouter/OpenAI/Anthropic/Google)
                          ↓
                    tool_gate → tool registry → tools / MCP servers
                                                      ↓
                                               task pool → catalog agents
```

---

## License

MIT
