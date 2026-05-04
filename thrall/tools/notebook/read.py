from __future__ import annotations
import json
import time
from uuid import UUID
from schemas.tool import ToolCall, ToolResult
from thrall.tools.filesystem._resolve import resolve, is_protected

_MAX_CHARS = 60_000


def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    path = resolve(call.args.get("path", ""))

    if is_protected(path) or not path.exists():
        return _result(call.id, error=f"path not found: {path}", start=start)
    if not path.is_file() or path.suffix != ".ipynb":
        return _result(call.id, error=f"not a .ipynb file: {path}", start=start)

    try:
        nb = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return _result(call.id, error=f"failed to parse notebook: {e}", start=start)

    cells = nb.get("cells", [])
    kernel = nb.get("metadata", {}).get("kernelspec", {}).get("display_name", "unknown")
    parts = [f"[Notebook: {path.name} | kernel: {kernel} | {len(cells)} cells]"]

    for idx, cell in enumerate(cells):
        cell_type = cell.get("cell_type", "unknown")
        source = "".join(cell.get("source", []))
        header = f"\n--- Cell {idx} [{cell_type}] ---"
        parts.append(header)
        parts.append(source if source.strip() else "(empty)")

        if cell_type == "code":
            outputs = cell.get("outputs", [])
            if outputs:
                out_lines = []
                for o in outputs:
                    otype = o.get("output_type", "")
                    if otype in ("stream",):
                        out_lines.append("".join(o.get("text", [])))
                    elif otype in ("execute_result", "display_data"):
                        text = o.get("data", {}).get("text/plain", [])
                        out_lines.append("".join(text))
                    elif otype == "error":
                        out_lines.append(f"ERROR: {o.get('ename')}: {o.get('evalue')}")
                if out_lines:
                    parts.append("[output]\n" + "\n".join(out_lines))

    output = "\n".join(parts)
    if len(output) > _MAX_CHARS:
        output = output[:_MAX_CHARS] + f"\n\n[truncated at {_MAX_CHARS} chars]"

    return _result(call.id, output=output, start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "notebook_read"
DESCRIPTION = (
    "Read a Jupyter notebook (.ipynb) and return all cells with their source and outputs. "
    "Cell indices in the output match the indices used by notebook_edit."
)
PARAMETERS = {
    "path": {"type": "string", "required": True, "description": "Path to the .ipynb file"},
}
