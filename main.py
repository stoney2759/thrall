import tomllib
from pathlib import Path
import uvicorn


def _server_cfg() -> tuple[str, int]:
    try:
        config_path = Path(__file__).parent / "config" / "config.toml"
        with open(config_path, "rb") as f:
            cfg = tomllib.load(f)
        server = cfg.get("server", {})
        return server.get("host", "0.0.0.0"), int(server.get("port", 8000))
    except Exception:
        return "0.0.0.0", 8000


if __name__ == "__main__":
    host, port = _server_cfg()
    uvicorn.run("server.app:app", host=host, port=port, reload=False)
