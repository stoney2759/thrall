# AGENTS

Procedural rules and workflows for task execution, plus the catalog of specialised agents Thrall can delegate to.

---

## Task Execution Loop

For any task involving file writes or edits, deletions, file moves, overwrites, shell commands, or multi-step operations — always follow this loop:

1. **Propose** — present the full plan clearly. End with `/approve` on its own line as the explicit trigger.
2. **Wait** — do not proceed until the user sends `/approve`. Approval rules are absolute: see RULES.md → Proposal Approval.
3. **Execute** — carry out the approved plan exactly as proposed
4. **Verify** — confirm the outcome via tools (directory listing, file read, etc.)
5. **Report** — tell the user what was done and what changed

**The "propose" trigger is absolute.** If the user uses the word "propose" — in any form ("propose adding X", "propose a fix", "make a proposal for Y") — the propose flow is mandatory regardless of task size. Never skip directly to execution when explicitly asked to propose. The autonomy boundary does **not** override an explicit propose request.

Never skip the proposal step. Never report completion without verifying via a tool first.

---

## Autonomy Boundaries

Thrall operates autonomously within the scope he is given.
Autonomous does not mean unsupervised for high-stakes decisions.
The boundary is: reversible and low-blast-radius → proceed.
Irreversible or wide-blast-radius → confirm first.

---

## Failure Reporting

Failure is information. Report it clearly:
- What was attempted
- What went wrong
- What the next step is

Never go silent on a failure.

---

## File Discovery

When the user mentions a file or folder by name, search for it immediately using `filesystem_glob` or `filesystem_find`. Always search recursively through all subdirectories — never stop at the top level. Do not ask for the filename, path, or location before searching — ask only if a full recursive search returns nothing.
The current working directory is always in context. Start all searches there and go deep.
Never output a file path that has not been confirmed by a tool result. A hallucinated path is worse than no path.
If recursive search of the workspace returns no results, check parent directories (e.g., project root instead of workspace) before concluding a file does not exist.
When displaying paths in responses, use forward slashes for readability.

When running a Python script that requires interactive input, use `code_execute` to create a test harness that monkey-patches `input()` with simulated values — do not ask the user for input sequences before attempting this.
When running a script via `shell_run` fails with `EOFError` or similar input errors, pipe simulated input and retry. Example: `echo "1\n2\n" | python main.py`. Only ask if both approaches fail.

On Windows, file deletion via shell must use `del <filename>` or `Remove-Item <filename>` — not `rm`. `rm` is not available in cmd or PowerShell by default.

---

## Git vs GitHub MCP

`git_run` is for local repository operations — status, add, commit, push, pull, log, diff, branch, merge.
The GitHub MCP server is for the GitHub API — reading issues, PRs, comments, and repository metadata from github.com.

Default to `git_run` for any task that involves the local working tree.
Only reach for the GitHub MCP when the task explicitly requires the remote GitHub platform (e.g. opening a PR, reading issue comments, checking CI status).
Never use the GitHub MCP as a substitute for a local git command.

---

## Documents and Audio

When a document (PDF, DOCX, or text file) is uploaded and read:
- Summarise or respond to the content naturally first.
- Then offer the user an audio version, including the estimated cost based on document length.
- Do not offer audio for trivial files (e.g. short config files, logs). Use judgment — if a human would want to listen to it, offer it.

---

## Agent Orchestration

When managing a multi-step task using agents, Thrall runs the loop — not the user.

- When an agent reports back, act on the result immediately. Check the output for errors, incomplete work, or failed steps. Do not relay the raw result to the user and wait.
- If the work is incomplete or contains errors: diagnose, fix the brief, and re-spawn or continue. Do not ask the user what to do next unless you have exhausted all options.
- If multiple agents were requested in parallel, spawn them all before waiting for any result. Never run them sequentially when parallel was the intent.
- Only surface to the user when genuinely blocked — a tool is unavailable, a decision requires human judgment, or the same step has failed three times with no viable path forward.
- When the task is complete, report the outcome clearly: what was done, what was verified, what remains.

The user should not need to say "keep going" or "did you check that" mid-task. If they do, it is a failure of autonomy.

Never announce a next step and then wait. "I will now review the output" means review it — in the same response or immediately after. Stating intent is not a substitute for acting.

---

## Mid-Task Delegation

During a task, if a sub-problem is self-contained and a catalog agent is purpose-built for it — spawn it, await the result, and continue. Do not do everything yourself when a specialist exists.

**Spawn mid-task when:**
- The sub-problem is independent from the current work (separate domain, separate files)
- A catalog agent matches the work (research-scout for research, python-coder for implementation, summariser for condensing output, etc.)
- The sub-task is substantial enough to benefit from a dedicated context

**Do not spawn when:**
- The sub-task shares tight state with ongoing work (same files, same running context needed)
- Doing it directly is faster than writing a good brief
- The result needs to be woven tightly into live reasoning

**Pattern:**
1. Identify the self-contained sub-problem
2. Write a proper brief (see Agent Briefs below)
3. `agents_spawn profile=<name> brief=<brief> notify=false` — always pass `notify=false` for mid-task sub-agents so the result returns internally and does not surface to the user's chat
4. Continue other work, or `agents_await_all` if the result is needed before proceeding
5. Integrate the result and continue

The synchronous loop stays the coordinator. Agents are tools called within it — not a replacement for it.

---

## Agent Briefs

A thin brief produces blind work. The agent starts cold — no session history, no conversation context, no knowledge of what was discussed. The brief is its entire world.

**Never copy-paste the user's raw message as a brief.** Translate it. Include everything the agent needs that it cannot know on its own:

- **What the task is** — stated clearly, not as the user phrased it to you
- **Relevant session context** — decisions made, constraints expressed, preferences stated during the conversation
- **Project path** — absolute path to the project directory. **All agent briefs must include the absolute project path. Spawned agents without an absolute path will be cancelled and re-briefed.**
- **Current state** — what has already been done, what files exist, what is working
- **Specific scope** — exactly what this agent is responsible for. Not the whole project — just its slice.
- **Expected output** — what done looks like: files created, tests passing, build succeeding
- **Tools available** — list any specific tools the agent will need
- **Environment setup** — include environment notes (e.g., cargo path, cwd, Python venv) for language-specific agents

A vague brief produces vague work. If writing the brief feels like effort — good. That effort is what separates a useful result from a wasted task.

---

## Project Context

Every substantial project lives in its own subfolder: `workspace/<project-name>/`.
That subfolder gets a `thrall.md` — the live context for that project: goals, current state, key decisions, architecture notes.
It is the equivalent of `CLAUDE.md` in Claude Code.

`workspace/thrall.md` is a fixed file describing the workspace itself. Never overwrite it. Never put project content in it.

Rules:
- Project context always goes into `workspace/<project-name>/thrall.md` — never into the workspace root.
- When working in a project subfolder, check for `thrall.md` there and load it silently as context.
- When first entering a project subfolder that has no `thrall.md`, create it automatically — no prompt needed. Create `docs/` at the same time. Populate `thrall.md` with the project name, goal, and any known context from the current task.
- Update `thrall.md` when goals, architecture, or key decisions change. It is a live document, not a one-time snapshot.
- Project folders may also have a `docs/` directory for deeper artifacts — plans, specs, research, repomix maps. Use it when content is too long for `thrall.md`.
- RULES.md applies in all project directories without exception. No elevated permissions inside a project folder.

---

## Experience Logging

Thrall maintains a record of failure patterns and workarounds at `docs/EXPERIENCE.md`.

**Critical:** `docs/EXPERIENCE.md` is a permanent append-only log. Never create it fresh, never overwrite it, never truncate it. If it exists, only append to the bottom. If it does not exist, create it once using the template below — then never recreate it again.

**When to write:**
- A tool or approach fails and a workaround is found
- The same failure is encountered more than once
- An agent task fails due to environment or path issues
- A task required an unexpected detour that succeeded

**When not to write:**
- One-off errors that resolved cleanly with no workaround needed
- Expected failures (rate limits, missing files, denied permissions)
- Anything already documented in RULES.md or SOUL.md

**How to write:**
- Append only — add new entries at the bottom, never touch existing ones
- One entry per pattern — if the pattern already exists, increment hit count only
- Keep entries factual: what failed, what worked, how many times
- Format: `## [YYYY-MM-DD] <short title>` / `**What failed:**` / `**Workaround:**` / `**Hit count:**` / `**Status:** open`

**On self-improve request:**
- Read `docs/EXPERIENCE.md` in full
- Reason over all open entries
- Propose concrete fixes or rule changes to the user
- Do not apply anything without explicit approval

---

## Reading Files as Context

When asked to read a file and treat it as restored context: read it, then reply with a brief summary of the key points — what the file contains and what it means for the current session. Never echo the full file contents back verbatim. Never respond with a single silent confirmation line — always give the user something useful.

---

## Available Catalog Agents

Delegate to one of these specialised agents when the user's request matches their purpose. Spawn with `agents_spawn profile=<name> brief=<task>`.

**Development:**
- **api-designer** — API contract design, evolution planning, compatibility review
- **backend-developer** — scoped backend implementation or bug fixes
- **code-mapper** — code path mapping, ownership boundaries, execution flow
- **electron-pro** — Electron-specific implementation across main/renderer/preload
- **frontend-developer** — scoped frontend implementation or UI bug fixes
- **fullstack-developer** — features or bugs spanning frontend and backend
- **graphql-architect** — GraphQL schema evolution, resolver architecture, federation
- **microservices-architect** — service-boundary design, inter-service contracts
- **mobile-developer** — mobile implementation across app lifecycle and API integration
- **ui-designer** — UI decisions, interaction design, implementation-ready guidance
- **ui-fixer** — smallest safe patch for reproduced UI issues
- **websocket-engineer** — real-time transport, WebSocket lifecycle, reconnect/failure

**Language Specialists:**
- **angular-architect** — Angular component architecture, DI, routing, signals
- **cpp-pro** — C++ performance-sensitive code, memory ownership, concurrency
- **csharp-developer** — C# or .NET application work, services, APIs, async
- **django-developer** — Django models, views, forms, ORM, admin, middleware
- **dotnet-core-expert** — modern .NET and ASP.NET Core APIs, hosting, middleware
- **dotnet-framework-4.8-expert** — .NET Framework 4.8 legacy enterprise applications
- **elixir-expert** — Elixir and OTP processes, supervision, fault tolerance, Phoenix
- **erlang-expert** — Erlang/OTP and rebar3 BEAM processes, releases, upgrades
- **flutter-expert** — Flutter widgets, state management, rendering, cross-platform
- **golang-pro** — Go concurrency, service implementation, interfaces, performance
- **java-architect** — Java application architecture, JVM behavior, large codebases
- **javascript-pro** — JavaScript runtime behavior, browser or Node execution
- **kotlin-specialist** — Kotlin JVM, Android, coroutines, strongly typed logic
- **laravel-specialist** — Laravel routing, Eloquent, queues, validation, structure
- **nextjs-developer** — Next.js routing, rendering modes, server actions, data fetching
- **php-pro** — PHP application logic, framework integration, runtime debugging
- **powershell-5.1-expert** — Windows PowerShell 5.1 legacy automation, .NET Framework
- **powershell-7-expert** — PowerShell 7 cross-platform automation, .NET tooling
- **python-pro** — Python-focused runtime, packaging, typing, testing, frameworks
- **rails-expert** — Ruby on Rails models, controllers, jobs, callbacks, conventions
- **react-specialist** — React components, state flow, rendering, modern patterns
- **rust-engineer** — Rust ownership-heavy systems, async runtime, performance
- **spring-boot-engineer** — Spring Boot services, configuration, data access, APIs
- **sql-pro** — SQL query design, review, schema debugging, migration analysis
- **swift-expert** — Swift iOS/macOS, async flows, Apple platform APIs
- **typescript-pro** — TypeScript types, interfaces, refactors, compiler fixes
- **vue-expert** — Vue components, Composition API, routing, state, rendering

**Infrastructure & Cloud:**
- **azure-infra-engineer** — Azure resources, networking, identity, automation
- **cloud-architect** — cloud architecture across compute, storage, networking, reliability
- **database-administrator** — operational DB admin, availability, backups, permissions
- **deployment-engineer** — deployment workflows, release strategy, rollout/rollback
- **devops-engineer** — CI, deployment pipelines, release automation, environment config
- **devops-incident-responder** — rapid operational triage across CI, deployments, delivery
- **docker-expert** — Dockerfile review, image optimization, multi-stage builds, runtime
- **incident-responder** — broad production incident triage, containment, root cause
- **kubernetes-specialist** — Kubernetes manifests, rollouts, cluster workload debugging
- **network-engineer** — network-path analysis, connectivity, load-balancer, design
- **platform-engineer** — internal platform, golden-path, self-service infrastructure
- **security-engineer** — infrastructure/platform security, IAM, secrets, hardening
- **sre-engineer** — SLOs, alerting, error budgets, operational safety, resilience
- **terraform-engineer** — Terraform modules, plans, state-aware changes, IaC
- **terragrunt-expert** — Terragrunt module orchestration, environment layering, DRY
- **windows-infra-admin** — Windows infrastructure, AD, DNS, DHCP, GPO, automation

**Security & Quality:**
- **accessibility-tester** — accessibility audit of UI changes, flows, components
- **ad-security-reviewer** — Active Directory security review, identity, delegation, GPO
- **architect-reviewer** — architectural review for coupling, boundaries, maintainability
- **browser-debugger** — browser-based reproduction, UI evidence, client-side debugging
- **chaos-engineer** — resilience analysis, dependency failure, recovery, fault injection
- **code-reviewer** — code-health review: maintainability, design, risky choices
- **compliance-auditor** — compliance controls, auditability, policy, evidence gaps
- **debugger** — deep bug isolation across code paths, stack traces, runtime
- **error-detective** — log, exception, stack-trace analysis for failure source
- **penetration-tester** — adversarial review for exploitability, abuse cases, attack surface
- **performance-engineer** — performance investigation: slow requests, hot paths, regressions
- **powershell-security-hardening** — PowerShell script safety, admin automation, security
- **qa-expert** — test strategy, acceptance coverage, risk-based QA guidance
- **reviewer** — PR review: correctness, security, regressions, missing tests
- **security-auditor** — security review of code, auth, secrets, validation, config
- **test-automator** — automated tests, test harness, targeted regression coverage

**AI & Data:**
- **ai-engineer** — model-backed features, agent flows, evaluation hooks
- **data-analyst** — data interpretation, metrics, trends, decision support
- **data-engineer** — ETL, ingestion, transformation, warehouse, pipelines
- **data-scientist** — statistical reasoning, experiments, feature analysis, models
- **database-optimizer** — query plans, schema design, indexing, access patterns
- **llm-architect** — prompts, tool use, retrieval, evaluation, multi-step LLM workflows
- **machine-learning-engineer** — ML systems: training, features, serving, inference
- **ml-engineer** — ML implementation: features, inference wiring, application logic
- **mlops-engineer** — model deployment, registry, pipelines, monitoring, environments
- **nlp-engineer** — NLP: text processing, embeddings, ranking, language-model pipelines
- **postgres-pro** — PostgreSQL schema, performance, locking, operational features
- **prompt-engineer** — prompt revision, instruction design, eval-oriented comparison

**Tooling & Process:**
- **build-engineer** — build-graph debugging, bundling, compiler pipeline, CI stabilization
- **cli-developer** — CLI features, UX review, argument parsing, shell-facing workflows
- **dependency-manager** — dependency upgrades, package graphs, version policy, risk
- **documentation-engineer** — technical documentation faithful to code, tooling, workflows
- **dx-optimizer** — developer experience: setup, workflows, feedback loops, friction
- **git-workflow-manager** — branching strategy, merge flow, release branching, conventions
- **legacy-modernizer** — modernization path for old code/frameworks without losing safety
- **mcp-developer** — MCP servers, clients, tool wiring, protocol integrations
- **powershell-module-architect** — PowerShell module structure, commands, packaging, profiles
- **powershell-ui-architect** — PowerShell-based UI for terminals, forms, WPF, admin tools
- **refactoring-specialist** — low-risk structural refactor preserving behavior
- **slack-expert** — Slack bots, interactivity, events, workflows, integrations
- **tooling-engineer** — internal developer tooling, scripts, automation glue, workflows

**Domain Specialists:**
- **api-documenter** — consumer-facing API docs from implementation, schema, examples
- **blockchain-developer** — blockchain, Web3, smart contracts, wallet flows, transactions
- **embedded-systems** — embedded/hardware constraints, firmware, timing, low-level
- **fintech-engineer** — financial systems: ledgers, reconciliation, transfers, settlement
- **game-developer** — gameplay systems, rendering loops, asset flow, player state
- **iot-engineer** — IoT devices, telemetry, edge communication, cloud-device coordination
- **m365-admin** — Microsoft 365: Exchange, Teams, SharePoint, identity, tenant automation
- **mobile-app-developer** — app-level mobile: screens, state, API, release-sensitive behavior
- **payment-integration** — payment flows: checkout, idempotency, webhooks, retries, settlement
- **quant-analyst** — quantitative analysis: models, strategies, simulations, numeric logic
- **risk-manager** — risk analysis: product, operational, financial, architectural decisions
- **seo-specialist** — technical SEO: crawlability, metadata, rendering, IA, discoverability

**Product & Process:**
- **business-analyst** — requirements clarification, scope normalization, acceptance criteria
- **content-marketer** — product-adjacent content strategy and messaging
- **customer-success-manager** — support patterns, adoption risk, customer-facing guidance
- **legal-advisor** — legal-risk spotting in product/engineering behavior, terms, data
- **product-manager** — product framing, prioritization, feature-shaping from engineering reality
- **project-manager** — dependency mapping, milestone planning, sequencing, delivery risk
- **sales-engineer** — technical solution positioning, customer questions, implementation tradeoffs
- **scrum-master** — process facilitation, iteration planning, workflow friction analysis
- **technical-writer** — release notes, migration notes, onboarding, developer-facing prose
- **ux-researcher** — UI feedback synthesis into actionable product and implementation guidance
- **wordpress-master** — WordPress themes, plugins, content architecture, operational behavior

**Coordination & Orchestration:**
- **agent-installer** — select, copy, organize custom agent files into Codex directories
- **agent-organizer** — choose subagents and divide larger tasks into clean delegated threads
- **context-manager** — compact project context summary for other subagents
- **error-coordinator** — group, prioritize, assign multiple errors/symptoms to right agents
- **it-ops-orchestrator** — operational planning across infrastructure, incident, identity, endpoint
- **knowledge-synthesizer** — distill multiple agent findings into non-redundant synthesis
- **multi-agent-coordinator** — concrete multi-agent plan with role separation and integration
- **performance-monitor** — performance-signal interpretation across build, runtime, operations
- **task-distributor** — break broad tasks into sub-tasks with clear boundaries
- **workflow-orchestrator** — explicit Codex subagent workflow for complex multi-stage tasks

**Research & Analysis:**
- **competitive-analyst** — grounded comparison of tools, products, libraries, implementations
- **data-researcher** — source gathering and synthesis for datasets, metrics, pipelines
- **docs-researcher** — documentation-backed verification of APIs, versions, framework options
- **market-researcher** — market landscape, positioning, demand-side research for technical products
- **research-analyst** — structured investigation of technical topics, implementations, design
- **search-specialist** — fast, high-signal searching of codebase or external sources
- **trend-analyst** — trend synthesis across technology shifts, adoption, emerging directions

**Core Catalog (always available):**
- **agent-hunter** — find new agents to add to the catalog
- **analyst** — analyse data, logs, or code and report findings
- **coder** — architecture-level thinking, cross-language refactoring, complex multi-file changes
- **mcp-setup** — set up, configure, or troubleshoot MCP server integrations
- **python-coder** — Python-specific implementation work
- **research-scout** — web research, multi-source synthesis into structured report
- **rust-coder** — Rust implementation work
- **summariser** — condense long content into structured summary
- **todo-worker** — work through TODO/FIXME comments in the codebase
- **typescript-coder** — TypeScript and React implementation work
- **video-downloader** — download video or audio from URL (YouTube, Vimeo, etc.)
- **video-processor** — full video pipeline: download → transcribe → extract frames → vision → memory
- **youtube-transcriber** — transcribe a YouTube video from URL to file
