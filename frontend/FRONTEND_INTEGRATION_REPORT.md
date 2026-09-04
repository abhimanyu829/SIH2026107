# FRONTEND INTEGRATION REPORT — SIH26107

Date: 2025-12-19 (session)
Stack: Vite 5 + React 18 + TypeScript (strict, `tsc -b` clean) + react-router-dom 6 + lucide-react. No UI framework, no chart lib, no state lib. Single CSS token system (`src/styles/tokens.css`) — institutional light design, navy `#0B3B60` + cyan `#0284C7`, 3px tricolor header ribbon only.

## 1. CONNECTION MODEL (verified live)

- Frontend origin: `http://localhost:5173` (Vite dev; also production-`build` verified → `dist/`, 1597 modules, gzip 86KB JS / 3.5KB CSS).
- All backend access through one path: `/api/*` → Vite proxy → FastAPI single origin `127.0.0.1:8002` (`phase6/compliance_api/app.py` = phase5 app + compliance router + `/api/fe/*` wrappers).
- Frontend contains **only** `API_BASE='/api'`. No DB credentials, no LLM keys, no Qdrant URL. Zero secrets in the bundle (verified by build output review).
- No component ever queries PostgreSQL/Qdrant/LLM directly.

## 2. LIVE TEST RESULTS (backend `pwsh-5` on :8002 + Vite `pwsh-7` on :5173, both live during tests)

| # | Test | Result |
|---|---|---|
| 1 | `/api/health` via proxy | **PASS** — status ok, supabase ✓, qdrant ✓ |
| 2 | Labs browse `state=Delhi` via proxy | **PASS** — 48 labs, 25 state facets |
| 3 | Hallmarking centres `state=DELHI` | **PASS** — real rows from 2,244-centre table |
| 4 | Standards search `work chairs` | **PASS** — IS 17631 "WORK CHAIRS – SPECIFICATION" top hit |
| 5 | Products search `office chairs` | **PASS** — PROD-00064 etc. |
| 6 | Chat EN "What is IS 17631?" | **PASS** — intent simple_lookup, conf 0.98, 5 sources |
| 7 | Agent EN (office chairs task) | **PASS** — status COMPLETED, 9 tools, 6 citations |
| 8 | Compliance journey A (full): create audit → upload 5 real docs (pdf/docx/xlsx/txt) → process (5 evidence) → analyze (33 requirements, 28.6s) → result → markdown report (7.1KB) → audits list (27) | **PASS** |
| 9 | Compliance journey B (recheck): expired-calibration audit → score 76 → upload `fixed_validity.pdf` → reprocess → recheck → PASS 25 / GAP 5 / UNKNOWN 3 | **PASS** (expired+fixed in one audit = conflicting evidence → UNKNOWN; documented correct engine behavior) |
| 10 | `tsc --noEmit` / `tsc -b` | **PASS** — 0 errors |
| 11 | `vite build` production | **PASS** |
| 12 | All 19 source modules transform via Vite dev | **PASS** |

All four demo journeys verified end-to-end through the **frontend proxy** (not just direct API): office-chairs Ask→Agent→Compliance full flow; hallmarking discovery; lab discovery; agent research task.

## 3. STATUS REPORT (mandated vocabulary)

- **IMPLEMENTED** — 15 routes, full design system, i18n EN/हिन्दी, compliance workflow with evidence drawer + remediation + recheck + report, no-dead-buttons audit done.
- **CONNECTED** — every data surface binds a real endpoint (see API_MAPPING.md); OFFICIAL BIS SOURCE vs AI-ASSISTED vs USER EVIDENCE separation enforced.
- **TESTED** — live matrix above, all through the running stack.
- **OFFICIAL-EXTERNAL-LINK** — HUID verification (huid.bis.gov.in), licence verification (bcare.bis.gov.in), BIS offices directory (bis.gov.in/offices), standards store, NITS training, CRS/FMCS pages. These are deliberately external; no internal simulation of government transactions.
- **BACKEND-UNAVAILABLE** — none of the in-scope endpoints; backend ran continuously during all tests.
- **BLOCKED** — none for core scope.

## 4. HONEST LIMITATIONS (no fake data substituted)

1. **BIS offices directory** — not in the knowledge base. Offices page states this plainly and links the official directory + real labs browse. **BNA → official link.**
2. **HUID / licence verification transactions** — government systems, out of scope. External official links only; UI copy says the assistant "provides information only". **OFFICIAL-EXTERNAL-LINK.**
3. **Document deletion** — backend has no delete-document endpoint. The remove button explains this honestly via toast instead of pretending. **Deferred / Minor Non-Blocking Issue.**
4. **Hindi NLU** — UI translation is complete, and `language="hi"` is forwarded to the API; however the backend's intent routing for Devanagari product queries is weak (e.g. "आईएस 17631 क्या है?" routes to product_discovery → UNKNOWN answer instead of the IS lookup that the English equivalent performs). Frontend faithfully surfaces the honest UNKNOWN string rather than fabricating. **Deferred / Minor Non-Blocking Issue** (backend NLU enhancement, not frontend).
5. **Related standards / lab scope sparsity** — several IS numbers have 0 related standards and several labs have empty scope rows in the master data. UI shows "not established in the available data" instead of placeholders. Expected data reality, not a bug.
6. **Audit list page** — audits list endpoint exists and is used by no visible page yet (workbench is direct-URL). **Deferred / Minor Non-Blocking Issue** (candidate small feature: recent audits on `/compliance`).

## 5. HOW TO RUN

```bash
# terminal 1 — backend (must be first)
cd phase6 && python -W ignore -m uvicorn compliance_api.app:app --host 127.0.0.1 --port 8002
# terminal 2 — frontend
cd frontend && npm install && npm run dev   # http://localhost:5173
```

## 6. CONCLUSION

The frontend is implemented, connected to the existing FastAPI backend through a single proxied origin, and live-tested journey-by-journey, button-by-button. The demo is ready: office work chairs → Ask BIS → IS 17631 → AI Agent → Compliance audit with uploads → PASS/GAP/UNKNOWN readiness score → evidence drawer → remediation → recheck → markdown report.
