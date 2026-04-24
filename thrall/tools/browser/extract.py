from __future__ import annotations
import time
from uuid import UUID
from schemas.tool import ToolCall, ToolResult

_MAX_CHARS = 20_000


async def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    mode = call.args.get("mode", "text").strip().lower()  # text | links | tables | all
    selector = call.args.get("selector", "").strip()
    max_chars = int(call.args.get("max_chars", _MAX_CHARS))

    try:
        from services.browser.manager import get_or_create
        session = await get_or_create(call.session_id)
        page = session.page

        if mode == "links":
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

        output = output.strip()
        if len(output) > max_chars:
            output = output[:max_chars] + f"\n\n[truncated at {max_chars} chars]"

        header = f"[{page.url}]\n\n"
        return _result(call.id, output=header + output, start=start)

    except Exception as e:
        return _result(call.id, error=str(e), start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "browser.extract"
DESCRIPTION = "Extract content from the current browser page. mode: text (default), links, tables, or all. Use selector to narrow to a specific element."
PARAMETERS = {
    "mode":      {"type": "string",  "required": False, "default": "text"},
    "selector":  {"type": "string",  "required": False, "default": ""},
    "max_chars": {"type": "integer", "required": False, "default": 20000},
}
