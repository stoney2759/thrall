# EXPERIENCE

Thrall's accumulated failure patterns and workarounds.
Append only — never overwrite. One entry per pattern.
Read on demand during self-improve sessions. Never auto-loaded into context.

---

## Entry Format

```
## [YYYY-MM-DD] <short title>

**What failed:** <description of the failure>
**Workaround:** <what was done instead>
**Hit count:** <number of times this pattern has been encountered>
**Status:** open | resolved
```

---

<!-- Entries below this line -->

## [2026-04-30] Use filesystem_ls for directory listings — not find/tree/shell

**What failed:** When asked to "list files in a directory", Thrall used `filesystem_find`, `filesystem_tree`, or a recursive shell command instead of `filesystem_ls`. This crawled into `.git/objects/` and similar deep trees, producing thousands of lines split across multiple Telegram messages.
**Workaround:** Always use `filesystem_ls` with the target path for directory listings. It is non-recursive and shows only immediate children. Use `filesystem_tree` only when the user explicitly asks for a tree view. Use `filesystem_find` only when searching by name/pattern across subdirectories.
**Hit count:** 1
**Status:** open

## [2026-04-30] On Windows, use filesystem tools for file verification — not shell ls/dir

**What failed:** When asked to verify a file exists or list directory contents, Thrall called `shell_run` with `ls` or `dir`. On Windows, `ls` is not a valid CMD command and returns "not recognized". Even `dir` is unnecessary when filesystem tools exist.
**Workaround:** Use `filesystem_ls` to list a directory, `filesystem_stat` to check if a file exists, `filesystem_cat` or `filesystem_read` to read contents. Only use `shell_run` when executing programs or commands that have no filesystem tool equivalent.
**Hit count:** 2
**Status:** resolved

## [2026-05-04] Mid-task narration creates fake user checkpoints

**What failed:** Within approved execution, Thrall sent messages like "Let me find the actual location of X first:" — announcing intent without delivering anything, then waiting for user acknowledgement before proceeding. Every request became a two-part interaction: announce → user says ok → execute.
**Workaround:** Execute within approved work. Report results, not intentions. Never end a message with "first:" or "let me check:" without immediately following with tool calls and results in the same turn.
**Hit count:** 1
**Status:** open

## [2026-05-06] New workspace projects must be self-contained from day one

**What failed:** Created a full multi-file project (thrall-runner) with no thrall.md, no docs/, and no pytest rootdir config. Next session starts cold with no context and pytest walks up to the install root's pytest.ini instead of the project's own config.
**Workaround:** When scaffolding any new project folder in workspace/, always create: (1) `thrall.md` — what it is, current state, what's built, what's next; (2) `docs/` with at least one architecture file; (3) `[tool.pytest.ini_options]` in `pyproject.toml` or a local `pytest.ini` so pytest treats the project folder as rootdir.
**Hit count:** 1
**Status:** open

## [2026-05-06] Relative cwd in shell tools resolves against install root, not workspace

**What failed:** `shell_run` and `powershell_run` were called with `cwd="thrall-runner"` (relative path). Python's `subprocess` resolves this against the process working directory (the Thrall install root), not the configured `workspace_dir`. Result: WinError 267 (invalid directory) on every attempt. Fallback attempts with `Set-Location 'thrall-runner'` also failed for the same reason.
**Workaround:** Always use the full absolute path for `cwd` on workspace projects — e.g. `C:\Users\jared\Coding Folder\thrall\workspace\thrall-runner`. Never pass a bare folder name as `cwd`.
**Root fix:** `os.chdir(workspace)` added to `bootstrap/startup.py:_init_workspace()` — process working directory is now `workspace/` at launch. Relative cwd values resolve correctly from there.
**Hit count:** 1
**Status:** resolved

## [2026-05-04] Re-searching for files created in the same session

**What failed:** After creating a file via `filesystem_write`, Thrall searched for its location as if it were unknown — running "Let me find the actual location of X first". The path was in his own tool call history from the same session.
**Workaround:** Trust your own tool results. A file you wrote is at the path you wrote it to. Check session tool history before running any discovery search. Never treat self-created files as unknown.
**Hit count:** 1
**Status:** open
