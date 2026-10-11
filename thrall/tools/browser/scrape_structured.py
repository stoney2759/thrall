from __future__ import annotations
import csv
import io
import json
import time
from uuid import UUID
from schemas.tool import ToolCall, ToolResult

_MAX_ROWS = 1000

# ── JavaScript injected into the page ─────────────────────────────────────────

_DETECT_JS = """
() => {
    function textOf(el) { return (el.innerText || el.textContent || '').trim(); }

    function extractTable(table) {
        const rows = [...table.querySelectorAll('tr')];
        if (rows.length === 0) return null;

        const headers = [];
        let dataRows = rows;

        const headRow = table.querySelector('thead tr')
            || (rows[0].querySelector('th') ? rows[0] : null);

        if (headRow) {
            [...headRow.querySelectorAll('th, td')].forEach((c, i) => {
                headers.push(textOf(c) || ('col_' + i));
            });
            dataRows = rows.filter(r => r !== headRow && !r.closest('thead'));
        }

        const result = [];
        dataRows.forEach(row => {
            const cells = [...row.querySelectorAll('td, th')];
            if (cells.length === 0) return;
            const rowData = {};
            cells.forEach((cell, i) => {
                const key = headers[i] || ('col_' + i);
                rowData[key] = textOf(cell);
                const link = cell.querySelector('a[href]');
                if (link) rowData[key + '_url'] = link.href;
            });
            result.push(rowData);
        });

        return { headers: headers.length ? headers : Object.keys(result[0] || {}), rows: result, detected: 'table' };
    }

    function getLeaves(el) {
        const leaves = [];
        function walk(node, depth) {
            if (depth > 8) return;
            const tag = node.tagName;
            const children = [...node.children];
            const isLink = (tag === 'A' && node.href);
            const isImg  = (tag === 'IMG' && node.src);
            const isLeaf = children.length === 0 || isLink || isImg;
            if (isLeaf) {
                const text = textOf(node);
                if (text.length > 0 || isImg) {
                    leaves.push({
                        cls: (node.classList[0] || '').replace(/[^a-zA-Z0-9_-]/g, '_').slice(0, 40),
                        tag: tag.toLowerCase(),
                        text: isImg ? '' : text,
                        href: node.href || null,
                        src:  isImg ? node.src : null,
                    });
                }
                return;
            }
            children.forEach(c => walk(c, depth + 1));
        }
        walk(el, 0);
        return leaves;
    }

    function extractRepeating(elements) {
        if (elements.length === 0) return null;
        const sample = getLeaves(elements[0]);
        if (sample.length === 0) return null;

        const headers = sample.map((leaf, i) => {
            if (leaf.src)  return leaf.cls || ('image_' + i);
            if (leaf.href) return leaf.cls || ('url_' + i);
            return leaf.cls && leaf.cls.length > 1 ? leaf.cls : ('col_' + i);
        });

        // Deduplicate headers
        const seen = {};
        const dedupedHeaders = headers.map(h => {
            seen[h] = (seen[h] || 0) + 1;
            return seen[h] > 1 ? h + '_' + seen[h] : h;
        });

        const rows = elements.map(el => {
            const leaves = getLeaves(el);
            const rowData = {};
            dedupedHeaders.forEach((h, i) => {
                const leaf = leaves[i];
                if (!leaf) { rowData[h] = ''; return; }
                rowData[h] = leaf.href || leaf.src || leaf.text;
            });
            return rowData;
        });

        return { headers: dedupedHeaders, rows, detected: 'repeated' };
    }

    // ── Selector-override path ────────────────────────────────────────────────
    const overrideSelector = window.__thrall_scrape_selector__ || '';
    if (overrideSelector) {
        const overrideEls = [...document.querySelectorAll(overrideSelector)];
        if (overrideEls.length > 0) {
            // If single table element, use table extractor
            if (overrideEls.length === 1 && overrideEls[0].tagName === 'TABLE') {
                return extractTable(overrideEls[0]);
            }
            return extractRepeating(overrideEls);
        }
    }

    // ── Auto-detect ───────────────────────────────────────────────────────────

    // Priority 1: HTML tables
    const SKIP_TAGS = new Set(['HTML','BODY','HEAD','SCRIPT','STYLE','NOSCRIPT','NAV','HEADER','FOOTER','ASIDE']);
    const tables = [...document.querySelectorAll('table')]
        .filter(t => !SKIP_TAGS.has(t.closest('nav,header,footer,aside')?.tagName || ''))
        .map(t => ({ t, count: t.querySelectorAll('tr').length }))
        .filter(x => x.count > 2)
        .sort((a, b) => b.count - a.count);

    if (tables.length > 0) {
        const result = extractTable(tables[0].t);
        if (result && result.rows.length > 0) return result;
    }

    // Priority 2: Most repeated sibling group
    const groups = new Map();

    document.querySelectorAll('li, article, tr, [class]').forEach(el => {
        if (SKIP_TAGS.has(el.tagName)) return;
        const parent = el.parentElement;
        if (!parent || SKIP_TAGS.has(parent.tagName)) return;
        // Skip tiny or invisible elements
        const rect = el.getBoundingClientRect();
        if (rect.width === 0 && rect.height === 0) return;

        const firstClass = el.classList[0] || '';
        const key = el.tagName + '::' + firstClass;
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key).push(el);
    });

    let bestGroup = null, bestScore = 2;
    groups.forEach((els) => {
        if (els.length <= bestScore) return;
        const avgLen = els.reduce((s, e) => s + textOf(e).length, 0) / els.length;
        if (avgLen < 15) return;
        bestScore = els.length;
        bestGroup = els;
    });

    if (bestGroup) {
        const result = extractRepeating(bestGroup);
        if (result && result.rows.length > 0) return result;
    }

    return null;
}
"""

_NEXT_BUTTON_JS = """
() => {
    const NEXT_TEXTS = ['next', '>', '»', '→', 'next page', 'load more', 'show more', 'see more'];
    const NEXT_CLASSES = ['next', 'pagination-next', 'page-next', 'nextpage', 'btn-next', 'arrow-next', 'arrow-right'];

    const candidates = [...document.querySelectorAll('a, button, [role="button"]')];
    for (const el of candidates) {
        if (el.disabled || el.getAttribute('aria-disabled') === 'true') continue;
        const text  = (el.innerText || el.textContent || '').trim().toLowerCase();
        const cls   = (el.className || '').toLowerCase();
        const aria  = (el.getAttribute('aria-label') || '').toLowerCase();
        const rel   = (el.getAttribute('rel') || '').toLowerCase();

        if (rel === 'next') return el;
        if (NEXT_TEXTS.includes(text) || NEXT_TEXTS.some(t => aria.includes(t))) return el;
        if (NEXT_CLASSES.some(c => cls.includes(c))) return el;
    }
    return null;
}
"""


# ── Tool implementation ────────────────────────────────────────────────────────

async def execute(call: ToolCall) -> ToolResult:
    start = time.monotonic()
    url          = call.args.get("url", "").strip()
    selector     = call.args.get("selector", "").strip()
    max_pages    = int(call.args.get("max_pages", 1))
    next_sel     = call.args.get("next_selector", "").strip()
    max_rows     = int(call.args.get("max_rows", _MAX_ROWS))
    output_fmt   = call.args.get("output", "csv").strip().lower()
    save_path    = call.args.get("save_path", "").strip()

    try:
        from services.browser.manager import get_or_create
        session = await get_or_create(call.session_id)
        page = session.page

        if url:
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            await page.wait_for_load_state("domcontentloaded")

        current_url = page.url
        all_rows: list[dict] = []
        headers: list[str] = []

        for page_num in range(max_pages):
            # Inject selector override so JS can pick it up
            if selector:
                await page.evaluate(f"() => {{ window.__thrall_scrape_selector__ = {json.dumps(selector)}; }}")

            data = await page.evaluate(_DETECT_JS)

            if not data or not data.get("rows"):
                if page_num == 0:
                    return _result(call.id, error="No repeating data structure detected. Try providing a CSS selector.", start=start)
                break

            if not headers:
                headers = data.get("headers") or list(data["rows"][0].keys())

            new_rows = data["rows"]
            all_rows.extend(new_rows)

            if len(all_rows) >= max_rows:
                all_rows = all_rows[:max_rows]
                break

            if page_num < max_pages - 1:
                # Find and click next button
                next_btn = None
                if next_sel:
                    try:
                        next_btn = await page.query_selector(next_sel)
                    except Exception:
                        pass
                if not next_btn:
                    next_btn = await page.evaluate_handle(_NEXT_BUTTON_JS)
                    is_null = await page.evaluate("el => el === null", next_btn)
                    if is_null:
                        next_btn = None

                if not next_btn:
                    break

                prev_url = page.url
                await next_btn.click()
                try:
                    await page.wait_for_load_state("domcontentloaded", timeout=10_000)
                except Exception:
                    pass

                # If URL didn't change and no new content, stop
                if page.url == prev_url:
                    await page.wait_for_timeout(1000)

        if not all_rows:
            return _result(call.id, error="No rows extracted.", start=start)

        # ── Format output ──────────────────────────────────────────────────────
        detected_type = data.get("detected", "?") if data else "?"

        if output_fmt == "json":
            content = json.dumps(all_rows, ensure_ascii=False, indent=2)
        else:
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=headers, extrasaction="ignore", lineterminator="\n")
            writer.writeheader()
            writer.writerows(all_rows)
            content = buf.getvalue()

        summary = (
            f"[Scraped: {current_url}]\n"
            f"Detected: {detected_type} | Pages: {page_num + 1} | "
            f"Rows: {len(all_rows)} | Columns: {len(headers)}\n"
            f"Headers: {', '.join(headers)}\n\n"
        )

        if save_path:
            from thrall.tools.filesystem._resolve import resolve
            out_path = resolve(save_path)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(content, encoding="utf-8")
            return _result(call.id, output=summary + f"Saved to: {out_path}", start=start)

        # Inline return — cap at 50k chars
        MAX_INLINE = 50_000
        inline = summary + content
        if len(inline) > MAX_INLINE:
            inline = inline[:MAX_INLINE] + f"\n\n[truncated — {len(all_rows)} rows total. Use save_path to write full output.]"

        return _result(call.id, output=inline, start=start)

    except Exception as e:
        return _result(call.id, error=str(e), start=start)


def _result(call_id: UUID, start: float, output: str | None = None, error: str | None = None) -> ToolResult:
    return ToolResult(call_id=call_id, output=output, error=error, duration_ms=int((time.monotonic() - start) * 1000))


NAME = "browser_scrape_structured"
DESCRIPTION = (
    "Auto-detect and extract structured tabular data from the current browser page or a URL. "
    "Detects HTML tables, repeated card/list elements, and paginated data automatically. "
    "Returns CSV (default) or JSON. Optionally saves to a file via save_path."
)
PARAMETERS = {
    "url":           {"type": "string",  "required": False, "description": "Navigate to this URL first. Omit to use the current page."},
    "selector":      {"type": "string",  "required": False, "description": "CSS selector to target specific repeating elements. Auto-detected if omitted."},
    "max_pages":     {"type": "integer", "required": False, "default": 1,    "description": "How many pagination steps to follow."},
    "next_selector": {"type": "string",  "required": False, "description": "CSS selector for the 'next page' button. Auto-detected if omitted."},
    "max_rows":      {"type": "integer", "required": False, "default": 1000, "description": "Maximum total rows to collect across all pages."},
    "output":        {"type": "string",  "required": False, "default": "csv", "description": "Output format: csv or json."},
    "save_path":     {"type": "string",  "required": False, "description": "Workspace-relative path to save the output file. Returns inline if omitted."},
}
