# TOOLS

Complete tool reference. Tools are called natively by the reasoning loop.

## Large Data Rule
When a tool result will exceed 10,000 chars (web pages, JSON blobs, DOM state, large files), always use `save_path` to write it to a file first, then read only the relevant section. Never pull large data through context — it accumulates across iterations and burns the token budget. One pass, write to file, parse from file.

## Batch Tasks Rule
When a task involves multiple items (races, files, URLs, pages), process them **one at a time sequentially** — never all at once in a single loop.

- Fetch item 1 → save to file → confirm done → fetch item 2 → save → confirm → repeat.
- Never accumulate results from multiple items in context simultaneously.
- After all items are saved, do one final aggregation pass reading from files.
- This keeps per-iteration context small regardless of how many items there are.

**This applies to: race tips, batch scraping, multi-file operations, multi-URL extraction, any task with N > 1 items.**

## Honest Reporting Rule
- If you change approach from what was asked — a different tool, a workaround, a skipped or substituted step — say so in your final report: what you tried, what failed, what you did instead. Never substitute silently.
- Report sizes, counts, cell contents and file contents from the saved file as it is now (re-read it), never from memory of an earlier step.

---

## Filesystem
- `filesystem_read` — read a file
- `filesystem_write` — write or create a file
- `filesystem_edit` — patch a file in place
- `filesystem_append` — append to a file
- `filesystem_cat` — print file contents
- `filesystem_ls` — list directory contents
- `filesystem_glob` — find files by pattern
- `filesystem_grep` — search content across files
- `filesystem_tree` — directory tree view
- `filesystem_stat` — file metadata
- `filesystem_find` — find files by name or type
- `filesystem_diff` — diff two files

## Web
- `web_search` — search the web
- `web_fetch` — fetch raw content from a URL
- `web_scrape` — extract structured content from a page
- `web_browse` — interact with a page dynamically

## Browser
- `browser_navigate` — navigate to a URL; returns page title and status
- `browser_screenshot` — take a screenshot and return a visual description via vision
- `browser_click` — click an element by text, role, or CSS selector
- `browser_fill` — fill an input by label, placeholder, or selector
- `browser_extract` — extract text, links, tables, or all content from the current page. mode=js + js_expression evaluates arbitrary JavaScript (e.g. `window.__PRELOADED_STATE__`). **Use save_path for any large data extraction** — this writes the full output to a file and returns only a summary, bypassing the context cap. Never pull raw JS state blobs without save_path — they will be truncated and useless.
- `browser_close` — close the browser session
- `browser_scrape_structured` — auto-detect and extract structured tabular data from a page or URL. Handles HTML tables, repeated card/list elements, and multi-page pagination. Returns CSV (default) or JSON. Params: `url` (optional, navigates first), `selector` (optional CSS override), `max_pages` (default 1), `next_selector` (pagination button override), `max_rows` (default 1000), `output` (csv|json), `save_path` (workspace-relative file path to write output)

## Code
- `code_execute` — run Python; returns stdout, stderr, exit code

## Shell
- `shell_run` — run a shell command; returns output. On Windows, avoid using `ls` or `dir` for file verification; use filesystem tools instead.
- `powershell_run` — run a PowerShell command via `powershell -NoProfile -Command`. Use for Windows-native operations, PowerShell cmdlets, and file system work. Prefer over `shell_run` for Windows file verification tasks.

## Git
- `git_run` — run a git command in the workspace repository

## Video
- `video_download` — download videos or extract info using yt-dlp
- `video_ffmpeg` — process video/audio files using ffmpeg (probe, convert, extract audio, trim, thumbnail)

## Documents
- `documents_read_pdf` — read a PDF file
- `documents_read_docx` — read a DOCX file
- `documents_read_csv` — read a CSV or Excel (.xlsx) file; returns pipe-separated rows. Params: `path`, `max_rows` (default 500), `include_header`, `sheet` (xlsx only)

## Audio
- `audio_generate` — synthesise speech from text via TTS provider

## Clipboard
- `clipboard_read` — read current clipboard contents
- `clipboard_write` — write text to clipboard
- `clipboard_save` — save a named snippet
- `clipboard_load` — load a named snippet
- `clipboard_snippets` — list saved snippets

## System
- `system_info` — return OS, CPU, memory, disk, and uptime
- `thrall_restart` — restart Thrall itself (always asks the user first); make no tool calls after it

## Profile
- `profile_switch` — switch the active personality profile

## Memory
- `memory_read` — retrieve from episodic or semantic memory
- `memory_write` — persist to episodic or semantic memory

## Agents
- `agents_spawn` — spawn an agent on a task; returns task_id
- `agents_result` — get result of a spawned agent
- `agents_await_all` — wait for multiple agents and collect results
- `agents_list` — list running and recent agents
- `agents_create` — design and save a new named agent
- `agents_prepare` — assign tools to a catalog agent

## Scheduler
- `scheduler_add` — add a scheduled or recurring job
- `scheduler_list` — list all scheduled jobs
- `scheduler_delete` — delete a scheduled job

## Transcription
- `transcription_run` — transcribe audio to text via Whisper (openrouter or groq)

## Vision
- `vision_analyze` — describe an image using the configured vision model

## Interaction
- `interaction_ask_user` — pause mid-task, send a question to the user, and wait for their reply before continuing
- `interaction_monitor` — run a command and stream its output; stops early when a pattern is matched or timeout is reached

## Notebook
- `notebook_read` — read a Jupyter notebook (.ipynb); returns all cells with source and outputs
- `notebook_edit` — replace, insert, or delete a cell in a notebook (clears stale outputs on edit)

## IDE
- `ide_diagnostics` — run a linter/type-checker (ruff → mypy → pylint auto-selected) and return diagnostics

## MCP (deferred tools)
- `mcp_search` — tools from connected MCP servers are hidden until loaded. The "MCP Servers" list in context shows what exists. Call `mcp_search` with the server name plus what you want to do (e.g. `github issue create`), then call the loaded tools — they stay loaded while you use them and unload after ~15 messages idle. If a tool you used earlier is gone, just search again. Use `select:server__tool` for an exact name.
- App-style MCP servers (editors, office apps) usually run headless: open/new → edit → save/export to a file path. If a server exposes a command list plus a run-command tool, list the commands first rather than guessing ids.
