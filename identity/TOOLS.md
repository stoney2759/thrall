# TOOLS

Complete tool reference. Tools are called natively by the reasoning loop.

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
- `browser_extract` — extract text, links, tables, or all content from the current page
- `browser_close` — close the browser session

## Code
- `code_execute` — run Python; returns stdout, stderr, exit code

## Shell
- `shell_run` — run a shell command; returns output. On Windows use forward slashes or escape backslashes in paths. For Windows-native operations prefix with `powershell -Command`.

## Git
- `git_run` — run a git command in the workspace repository

## Video
- `video_download` — download videos or extract info using yt-dlp
- `video_ffmpeg` — process video/audio files using ffmpeg (probe, convert, extract audio, trim, thumbnail)

## Documents
- `documents_read_pdf` — read a PDF file
- `documents_read_docx` — read a DOCX file

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
