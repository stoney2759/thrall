from __future__ import annotations
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket
from fastapi.responses import JSONResponse
from bootstrap import startup


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


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    from transports.desktop.handler import handle
    await handle(ws)
