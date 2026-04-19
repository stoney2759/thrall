    Thrall/
        main.py                        ← uvicorn entry point
        telegram_server.py             ← telegram bot entry point
        CLAUDE.md                      ← governance (pending approval)

    bootstrap/
        state.py                     ← Loads in all thralls files, configs works like a loader.

    cli/                           ← Handles command line interface

    commands/                      ← Build in / commands

    components/
        agents/
        diff/ 
        sandbox/
        setting
        shell

    constants/

    
    thrall/                        ← core Thrall package
        __init__.py
    core.py                      ← main reasoning loop
    memory.py                    ← memory read/write/search
    router.py                    ← thin FastAPI bridge
    tools/
        __init__.py
        filesystem.py              ← read/write/edit/glob/grep
        web.py                     ← search/fetch/browse/scrape
        code.py                    ← sandboxed execution
        spawner.py                 ← worker spawn/cancel/track
        org.py                     ← state/org.json mutations
    workers/
        __init__.py
        base.py                    ← Worker dataclass + lifecycle
        registry.py                ← capability profiles/templates
        pool.py                    ← active worker management

    memory/
        identity/                    ← SOUL.md, IDENTITY.md
        episodes/                    ← message history (searchable)
        knowledge/                   ← semantic facts (structured JSONL)

    config/
        config.toml

    state/
        org.json                     ← Human + Thrall only

    frontend/
        server.py                    ← FastAPI app
        frontend_adapter.py          ← domain → HTTP DTOs

    dashboard/                     ← React UI (copied, untouched)

    docs/                          ← protocol docs

    tests/