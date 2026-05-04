from __future__ import annotations
import time
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, WebSocket
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from bootstrap import startup
import os

_START_TIME = time.time()


class CreateJobBody(BaseModel):
    schedule: str
    task: str
    type: str = "cron"
    agent: Optional[str] = None
    output_mode: str = "verbose"


class SetModelBody(BaseModel):
    model: Optional[str] = None


class StopTaskBody(BaseModel):
    session_id: Optional[str] = None


@asynccontextmanager
async def _lifespan(app: FastAPI):
    startup.start()
    yield


app = FastAPI(title="Thrall", version="2.0.0", lifespan=_lifespan)


@app.get("/health")
async def health():
    from bootstrap import state
    cfg = state.get_config().get("thrall", {})
    llm_cfg = state.get_config().get("llm", {})
    model = state.get_model_override() or llm_cfg.get("model", "unknown")
    return JSONResponse({
        "status": "ok",
        "version": cfg.get("version", "2.0.0"),
        "model": model,
    })


@app.get("/api/status")
async def api_status():
    from bootstrap import state
    cfg = state.get_config().get("thrall", {})
    llm_cfg = state.get_config().get("llm", {})
    model = state.get_model_override() or llm_cfg.get("model", "unknown")
    config_model = llm_cfg.get("model", "unknown")
    return JSONResponse({
        "status": "ok",
        "version": cfg.get("version", "2.0.0"),
        "model": model,
        "config_model": config_model,
        "model_overridden": state.get_model_override() is not None,
        "tasks": state.get_active_task_count(),
        "cost_usd": state.get_total_cost(),
        "uptime_seconds": int(time.time() - _START_TIME),
        "reasoning_effort": state.get_reasoning_effort(),
        "errors": len(state.get_error_log()),
    })


@app.get("/api/memory/episodes")
async def api_memory_episodes(search: str = "", limit: int = 100):
    import json
    from pathlib import Path
    path = Path(__file__).parent.parent / "memory" / "episodes" / "episodes.jsonl"
    if not path.exists():
        return JSONResponse([])
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except Exception:
            pass
    if search:
        q = search.lower()
        entries = [
            e for e in entries
            if q in e.get("content", "").lower()
            or any(q in t.lower() for t in e.get("tags", []))
        ]
    entries.reverse()
    return JSONResponse(entries[:limit])


@app.delete("/api/memory/episodes/{episode_id}")
async def api_delete_episode(episode_id: str):
    import json
    from pathlib import Path
    path = Path(__file__).parent.parent / "memory" / "episodes" / "episodes.jsonl"
    if not path.exists():
        return JSONResponse({"error": "Not found"}, status_code=404)
    lines = path.read_text(encoding="utf-8").splitlines()
    new_lines, deleted = [], False
    for line in lines:
        if not line.strip():
            continue
        try:
            if json.loads(line).get("id") == episode_id:
                deleted = True
                continue
        except Exception:
            pass
        new_lines.append(line)
    if not deleted:
        return JSONResponse({"error": "Not found"}, status_code=404)
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return JSONResponse({"ok": True})


@app.get("/api/memory/knowledge")
async def api_memory_knowledge(search: str = "", limit: int = 100):
    import json
    from pathlib import Path
    path = Path(__file__).parent.parent / "memory" / "knowledge" / "facts.jsonl"
    if not path.exists():
        return JSONResponse([])
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except Exception:
            pass
    if search:
        q = search.lower()
        entries = [
            e for e in entries
            if q in e.get("content", "").lower()
            or any(q in t.lower() for t in e.get("tags", []))
        ]
    entries.reverse()
    return JSONResponse(entries[:limit])


@app.delete("/api/memory/knowledge/{fact_id}")
async def api_delete_knowledge(fact_id: str):
    import json
    from pathlib import Path
    path = Path(__file__).parent.parent / "memory" / "knowledge" / "facts.jsonl"
    if not path.exists():
        return JSONResponse({"error": "Not found"}, status_code=404)
    lines = path.read_text(encoding="utf-8").splitlines()
    new_lines, deleted = [], False
    for line in lines:
        if not line.strip():
            continue
        try:
            if json.loads(line).get("id") == fact_id:
                deleted = True
                continue
        except Exception:
            pass
        new_lines.append(line)
    if not deleted:
        return JSONResponse({"error": "Not found"}, status_code=404)
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return JSONResponse({"ok": True})


@app.get("/api/logs")
async def api_logs(file: str = "main", lines: int = 150, min_level: str = "INFO"):
    import re
    LEVELS = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3, "CRITICAL": 4}
    min_lvl = LEVELS.get(min_level.upper(), 1)

    if file == "memory":
        from bootstrap import state
        return JSONResponse(state.get_error_log()[-lines:])

    _log_dir = os.path.join(os.path.dirname(__file__), "..", "logs")
    _files = {
        "main":   os.path.join(_log_dir, "thrall.log"),
        "errors": os.path.join(_log_dir, "thrall_err.log"),
    }
    path = _files.get(file)
    if not path or not os.path.isfile(path):
        return JSONResponse([])

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            raw = f.readlines()
    except Exception:
        return JSONResponse([])

    raw = raw[-(lines * 4):]  # read extra to survive filter
    pattern = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \[(\w+)\] (.+?): (.+)$")
    entries: list[dict] = []
    current: dict | None = None

    for line in raw:
        line = line.rstrip()
        m = pattern.match(line)
        if m:
            if current and LEVELS.get(current["level"], 0) >= min_lvl:
                entries.append(current)
            ts, level, module, message = m.groups()
            current = {"ts": ts, "level": level, "module": module, "message": message, "trace": ""}
        elif current and line.strip():
            current["trace"] = (current["trace"] + "\n" + line).strip()

    if current and LEVELS.get(current["level"], 0) >= min_lvl:
        entries.append(current)

    return JSONResponse(list(reversed(entries[-lines:])))  # newest first


@app.patch("/api/control/model")
async def api_set_model(body: SetModelBody):
    from bootstrap import state
    state.set_model_override(body.model or None)
    llm_cfg = state.get_config().get("llm", {})
    active = body.model or llm_cfg.get("model", "unknown")
    return JSONResponse({"ok": True, "model": active, "overridden": body.model is not None})


@app.post("/api/control/stop")
async def api_stop_task(body: StopTaskBody):
    from bootstrap import state
    if not body.session_id:
        return JSONResponse({"ok": False, "error": "session_id required"}, status_code=400)
    cancelled = state.cancel_task(body.session_id)
    return JSONResponse({"ok": True, "cancelled": cancelled})


@app.get("/api/agents")
async def api_agents():
    from thrall.tasks.pool import list_active
    tasks = list_active()
    return JSONResponse([
        {
            "id": str(t.id),
            "profile": t.profile.name,
            "status": t.status.value,
            "brief": t.brief,
            "created_at": t.created_at.isoformat(),
        }
        for t in tasks
    ])


@app.delete("/api/agents/{task_id}")
async def api_agents_kill(task_id: str):
    from thrall.tasks.pool import cancel
    from uuid import UUID
    try:
        uid = UUID(task_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid task_id")
    cancelled = await cancel(uid)
    return JSONResponse({"ok": True, "cancelled": cancelled})


@app.get("/api/scheduler")
async def api_scheduler():
    try:
        from scheduler import store
        jobs = store.load_jobs()
        return JSONResponse([
            {
                "id": j.id,
                "type": j.type,
                "schedule": j.schedule,
                "schedule_summary": j.schedule_summary(),
                "task": j.task,
                "enabled": j.enabled,
                "last_run": j.last_run,
                "agent": j.agent,
            }
            for j in jobs
        ])
    except Exception:
        return JSONResponse([])


@app.post("/api/scheduler/jobs")
async def api_create_job(body: CreateJobBody):
    import uuid
    from datetime import datetime, timezone
    from scheduler import store
    from scheduler.job import Job
    from scheduler.parser import parse_schedule
    try:
        result = await parse_schedule(body.schedule)
        job = Job(
            id=str(uuid.uuid4()),
            type=body.type,
            schedule=body.schedule,
            cron_expr=result.cron_expr,
            human_summary=result.human_summary,
            task=body.task,
            agent=body.agent,
            output_mode=body.output_mode,
            enabled=True,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        store.add_job(job)
        return JSONResponse(job.to_dict(), status_code=201)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": f"Internal error: {e}"}, status_code=500)


@app.delete("/api/scheduler/jobs/{job_id}")
async def api_delete_job(job_id: str):
    from scheduler import store
    deleted = store.delete_job(job_id)
    if not deleted:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return JSONResponse({"ok": True})


@app.patch("/api/scheduler/jobs/{job_id}/toggle")
async def api_toggle_job(job_id: str):
    from scheduler import store
    toggled = store.toggle_job(job_id)
    if not toggled:
        return JSONResponse({"error": "Not found"}, status_code=404)
    jobs = store.load_jobs()
    job = next((j for j in jobs if j.id == job_id), None)
    return JSONResponse({"ok": True, "enabled": job.enabled if job else None})


@app.get("/api/commands")
async def api_commands():
    from commands.registry import all_commands
    return JSONResponse([
        {"name": cmd.name(), "description": cmd.description()}
        for cmd in sorted(all_commands(), key=lambda c: c.name())
    ])


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    from transports.desktop.handler import handle
    await handle(ws)


# Serve built React app — only if dist/ exists (production mode)
_dist = os.path.join(os.path.dirname(__file__), "..", "dashboard", "dist")
if os.path.isdir(_dist):
    app.mount("/", StaticFiles(directory=_dist, html=True), name="static")
