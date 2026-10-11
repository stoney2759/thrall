from __future__ import annotations
import json
import time
from uuid import UUID
from schemas.tool import ToolCall, ToolResult

_MAX_CHARS = 20_000


async def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    mode        = call.args.get("mode", "text").strip().lower()  # text | links | tables | all | js
    selector    = call.args.get("selector", "").strip()
    max_chars   = int(call.args.get("max_chars", _MAX_CHARS))
    save_path   = call.args.get("save_path", "").strip()
    js_expr     = call.args.get("js_expression", "").strip()

    try:
        from services.browser.manager import get_or_create
        session = await get_or_create(call.session_id)
        page = session.page

        if mode == "js" or js_expr:
            # Evaluate arbitrary JS — useful for extracting window.__PRELOADED_STATE__ etc.
            expr = js_expr or call.args.get("js_expression", "")
            if not expr:
                return _result(call.id, error="js_expression is required when mode=js", start=start)
            raw = await page.evaluate(expr)
            if isinstance(raw, (dict, list)):
                output = json.dumps(raw, ensure_ascii=False, indent=2)
            else:
                output = str(raw) if raw is not None else ""

        elif mode == "links":
            links = await page.eval_on_selector_all(
                "a[href]",
                "els => els.map(e => ({ text: e.innerText.trim(), href: e.href })).filter(l => l.text && l.href)"
            )
            lines = [f"{l['text']} → {l['href']}" for l in links[:100]]
            output = "\n".join(lines) or "No links found."

        elif mode == "tables":
            tables = await page.eval_on_selector_all(
                "table",
                """tables => tables.map(t => {
                    const rows = Array.from(t.querySelectorAll('tr'));
                    return rows.map(r => Array.from(r.querySelectorAll('th,td')).map(c => c.innerText.trim()).join(' | ')).join('\\n');
                })"""
            )
            output = "\n\n---\n\n".join(tables) if tables else "No tables found."

        else:
            # text or all — get main content
            target = selector or "body"
            try:
                text = await page.eval_on_selector(
                    target,
                    "el => el.innerText"
                )
            except Exception:
                text = await page.evaluate("() => document.body.innerText")

            if mode == "all":
                links = await page.eval_on_selector_all(
                    "a[href]",
                    "els => els.slice(0,50).map(e => e.innerText.trim() + ' → ' + e.href).filter(Boolean)"
                )
                link_section = "\n[Links]\n" + "\n".join(links) if links else ""
                output = text + link_section
            else:
                output = text

        output = output.strip() if isinstance(output, str) else output
        current_url = page.url
        header = f"[{current_url}]\n\n"

        if save_path:
            from thrall.tools.filesystem._resolve import resolve
            out_path = resolve(save_path)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(output, encoding="utf-8")
            summary = f"{len(output):,} chars written to {out_path}"
            return _result(call.id, output=header + summary, start=start)

        if len(output) > max_chars:
            output = output[:max_chars] + f"\n\n[truncated at {max_chars} chars — use save_path to capture full output]"

        return _result(call.id, output=header + output, start=start)

    except Exception as e:
        return _result(call.id, error=str(e), start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "browser_extract"
DESCRIPTION = (
    "Extract content from the current browser page. "
    "mode: text (default), links, tables, all, or js (evaluate a JS expression). "
    "Use selector to narrow to a specific element. "
    "Use save_path to write large output directly to a file (bypasses context cap — use this for window.__PRELOADED_STATE__ and other large data blobs). "
    "Use js_expression with mode=js to evaluate arbitrary JavaScript and capture the result."
)
PARAMETERS = {
    "mode":          {"type": "string",  "required": False, "default": "text",  "description": "text | links | tables | all | js"},
    "selector":      {"type": "string",  "required": False, "default": ""},
    "max_chars":     {"type": "integer", "required": False, "default": 20000},
    "save_path":     {"type": "string",  "required": False, "description": "Workspace-relative path to write full output. Returns only a summary in context — use for large data blobs."},
    "js_expression": {"type": "string",  "required": False, "description": "JavaScript expression to evaluate (e.g. 'window.__PRELOADED_STATE__'). Use with mode=js."},
}
