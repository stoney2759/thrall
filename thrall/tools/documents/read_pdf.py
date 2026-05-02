from __future__ import annotations
import time
from uuid import UUID
from schemas.tool import ToolCall, ToolResult
from thrall.tools.filesystem._resolve import resolve, is_protected

_MAX_CHARS = 50_000


def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    path = resolve(call.args.get("path", ""))

    if is_protected(path) or not path.exists():
        return _result(call.id, error=f"path not found: {path}", start=start)
    if not path.is_file():
        return _result(call.id, error=f"not a file: {path}", start=start)

    try:
        import pdfplumber
    except ImportError:
        return _result(call.id, error="pdfplumber is not installed — run: pip install pdfplumber", start=start)

    page_start = int(call.args.get("page_start", 1))
    page_end = call.args.get("page_end")
    max_chars = int(call.args.get("max_chars", _MAX_CHARS))

    try:
        with pdfplumber.open(str(path)) as pdf:
            total = len(pdf.pages)
            end = int(page_end) if page_end is not None else total
            end = min(end, total)
            start_idx = max(0, page_start - 1)

            parts = []
            for i, page in enumerate(pdf.pages[start_idx:end], start=page_start):
                text = page.extract_text() or ""
                parts.append(f"[Page {i}]\n{text}")

            output = "\n\n".join(parts)
            if len(output) > max_chars:
                output = output[:max_chars] + f"\n\n[truncated at {max_chars} chars — use page_start/page_end to narrow range]"

        header = f"[PDF: {path.name} | pages {page_start}-{end} of {total}]\n\n"
        return _result(call.id, output=header + output, start=start)

    except PermissionError:
        return _result(call.id, error=f"permission denied: {path}", start=start)
    except Exception as e:
        return _result(call.id, error=str(e), start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "documents_read_pdf"
DESCRIPTION = "Extract text from a PDF file. Supports page range selection. Returns page-numbered text."
PARAMETERS = {
    "path":       {"type": "string",  "required": True},
    "page_start": {"type": "integer", "required": False, "default": 1},
    "page_end":   {"type": "integer", "required": False, "default": None},
    "max_chars":  {"type": "integer", "required": False, "default": 50000},
}
