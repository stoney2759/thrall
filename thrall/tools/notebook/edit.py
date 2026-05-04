from __future__ import annotations
import json
import time
from uuid import UUID
from schemas.tool import ToolCall, ToolResult
from thrall.tools.filesystem._resolve import resolve, is_protected


def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    path = resolve(call.args.get("path", ""))

    if is_protected(path) or not path.exists():
        return _result(call.id, error=f"path not found: {path}", start=start)
    if not path.is_file() or path.suffix != ".ipynb":
        return _result(call.id, error=f"not a .ipynb file: {path}", start=start)

    cell_index = call.args.get("cell_index")
    new_source = call.args.get("source")
    mode = call.args.get("mode", "replace")

    if cell_index is None:
        return _result(call.id, error="cell_index is required", start=start)
    if new_source is None:
        return _result(call.id, error="source is required", start=start)

    try:
        nb = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return _result(call.id, error=f"failed to parse notebook: {e}", start=start)

    cells = nb.get("cells", [])
    idx = int(cell_index)

    if mode == "insert":
        cell_type = call.args.get("cell_type", "code")
        new_cell: dict = {
            "cell_type": cell_type,
            "metadata": {},
            "source": new_source.splitlines(keepends=True),
        }
        if cell_type == "code":
            new_cell["outputs"] = []
            new_cell["execution_count"] = None
        cells.insert(idx, new_cell)
        nb["cells"] = cells
        path.write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
        return _result(call.id, output=f"Inserted new {cell_type} cell at index {idx}", start=start)

    if idx < 0 or idx >= len(cells):
        return _result(call.id, error=f"cell_index {idx} out of range (notebook has {len(cells)} cells)", start=start)

    if mode == "delete":
        cells.pop(idx)
        nb["cells"] = cells
        path.write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
        return _result(call.id, output=f"Deleted cell {idx}", start=start)

    # replace (default)
    cells[idx]["source"] = new_source.splitlines(keepends=True)
    # clear outputs on edit so stale results don't mislead
    if cells[idx].get("cell_type") == "code":
        cells[idx]["outputs"] = []
        cells[idx]["execution_count"] = None
    nb["cells"] = cells
    path.write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
    return _result(call.id, output=f"Updated cell {idx} source ({len(new_source)} chars, outputs cleared)", start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "notebook_edit"
DESCRIPTION = (
    "Edit a cell in a Jupyter notebook (.ipynb). "
    "Supports replace (overwrite cell source), insert (add a new cell at index), and delete. "
    "Code cell outputs are cleared on replace so stale results don't remain."
)
PARAMETERS = {
    "path": {
        "type": "string",
        "required": True,
        "description": "Path to the .ipynb file",
    },
    "cell_index": {
        "type": "integer",
        "required": True,
        "description": "Zero-based cell index. For insert, the new cell is placed at this position.",
    },
    "source": {
        "type": "string",
        "required": True,
        "description": "New source content for the cell",
    },
    "mode": {
        "type": "string",
        "required": False,
        "default": "replace",
        "description": "replace | insert | delete. Default is replace.",
    },
    "cell_type": {
        "type": "string",
        "required": False,
        "default": "code",
        "description": "Cell type for insert mode: code | markdown. Default code.",
    },
}
