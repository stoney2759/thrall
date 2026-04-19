# OpenThrall UI

React + TypeScript frontend for the OpenThrall governed AI system.

## Setup

```bash
npm install
npm run dev        # starts dev server on :5173, proxies API to :8000
```

## Build for production

```bash
npm run build      # outputs to dist/
```

## Environment

| Variable            | Default     | Purpose                            |
|---------------------|-------------|------------------------------------|
| `VITE_API_BASE_URL` | `""`        | API base URL (empty = same origin) |

For a separate dev server, set in `.env.local`:
```
VITE_API_BASE_URL=http://localhost:8000
```

Or use the built-in Vite proxy (configured in `vite.config.ts`) — recommended
for development as it avoids CORS issues.

## Serving from FastAPI

To serve the built UI directly from FastAPI:

```python
from fastapi.staticfiles import StaticFiles
app.mount("/", StaticFiles(directory="dist", html=True), name="ui")
```

Run `npm run build` first. Make sure the `mount` comes after all your API routes.

## Architecture

```
src/
  api/
    types.ts      # TypeScript types generated from OpenAPI schema v0.2.8
    client.ts     # Centralized fetch wrapper — single point of API contact
  state/
    store.ts      # React context store — session state only, no localStorage
  components/
    BootstrapWizard.tsx    # Two-step org initialisation wizard
    OrgTreePanel.tsx       # Read-only org hierarchy tree
    ThrallChatPanel.tsx    # Human → Thrall governed chat
    ApprovalsPanel.tsx     # Pending approvals with approve/deny actions
    EventsPanel.tsx        # Audit event log
    NodeDetailSidebar.tsx  # Read-only node detail view
    StatusBar.tsx          # Kernel + LLM health indicators
  pages/
    Dashboard.tsx          # Main shell (tabs + panels layout)
  App.tsx                  # Root — checks /org, routes wizard ↔ dashboard
```

## Governance notes

- The UI holds **no authority**. All decisions flow through backend endpoints.
- Approval actions always **re-fetch** from backend after decision — no local caching.
- Bootstrap calls **exactly one endpoint**: `POST /org/bootstrap`.
- Node IDs for chat and approval actions are always sourced from bootstrap response — never hardcoded.
- No credentials are stored anywhere in the UI layer.
