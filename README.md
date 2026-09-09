# BIS Intelligent Assistant — Frontend

AI-powered frontend for **SIH26107 — AI-powered Intelligent Assistant for Indian Standards and BIS Services for Industries and Consumers**.

React 18 + TypeScript + Vite. Institutional light design (navy + cyan, tricolor accent), English/हिन्दी, lucide-react icons. No UI framework, no chart library, no state library.

## Run

The backend must be running first (single origin, port 8002):

```bash
cd phase6
python -W ignore -m uvicorn compliance_api.app:app --host 127.0.0.1 --port 8002
```

Then:

```bash
cd frontend
npm install
npm run dev        # → http://localhost:5173  (proxies /api → 127.0.0.1:8002)
npm run build      # production build (tsc -b && vite build) → dist/
```

`API_BASE_URL` is the only backend reference — `/api` via the Vite proxy in dev. The frontend never touches PostgreSQL, Qdrant or the LLM directly and holds no secrets.

## Pages

| Route | Purpose |
|---|---|
| `/` | Home — omnibar (ASK/AGENT modes), quick actions |
| `/ask` | Ask BIS — evidence-cited Q&A with sources & related info |
| `/agent` | AI Agent — task templates, live progress, citations |
| `/compliance` → `/compliance/:auditId` | 6-step compliance readiness workflow (create → confirm → upload → process → analyze → results) with score, PASS/GAP/UNKNOWN table, evidence drawer, remediation, recheck, markdown report |
| `/standards`, `/standards/:isNumber` | Standards search + detail (overview, QCO, scheme, tests, labs) |
| `/products`, `/products/:productId` | Product records + linked standards |
| `/labs`, `/labs/:labId` | Recognized laboratory directory (state filter) + scope detail |
| `/hallmarking` | HUID explainer, official verification links, A&H centre directory |
| `/offices` | Honest state: office directory not in knowledge base → official BIS link + labs browse |
| `/services` | Industry / consumer / professional service cards (internal or official-link) |
| `/resources` `/help` `/about` | Official portals, FAQ, project & privacy notes |

## Guarantees

- **No fake data.** Every list comes from a live backend call; empty states say so honestly.
- **No dead buttons.** All buttons navigate, call an API or open an official external link.
- **Source separation.** OFFICIAL BIS SOURCE / AI-ASSISTED / USER EVIDENCE badges are visually distinct everywhere.
- **i18n.** Centralized dictionary (`src/i18n`); language sent to the API as `language="hi"`.
- **Honest AI.** Unknown answers surface the exact backend strings ("Insufficient evidence." etc.) — never invented content.

See `API_MAPPING.md`, `BUTTON_FUNCTIONALITY_MATRIX.md`, `FRONTEND_INTEGRATION_REPORT.md`.
