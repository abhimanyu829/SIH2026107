# BUTTON FUNCTIONALITY MATRIX

Every interactive element in the BIS Intelligent Assistant, its action, its backend/external target, and its honest state behavior. **No dead buttons** — verified live against the running backend (127.0.0.1:8002 via Vite proxy).

Legend: — = state not reachable (action always available); **BA** = backend-available; **BNA** = backend function not available → honest fallback or official external link; **EXT** = official external BIS link.

## Shell

| Element | Action | Target | Disabled/Empty state |
|---|---|---|---|
| Header logo + name | Navigate home | `/` | — |
| Header EN / हिन्दी switcher | Switch language (whole UI + API `language` param) | local + `/api/chat`, `/api/agent/run` | — |
| Sidebar items (11) | Navigate | routes below | — |
| Footer links (13) | Navigate or external | routes + bis.gov.in | — |
| Mobile menu button | Open off-canvas sidebar | overlay | ≤768px only |

## Home `/`

| Element | Action | Target |
|---|---|---|
| Omnibar ASK mode submit | Navigate with query | `/ask?q=…` |
| Omnibar AGENT mode submit | Navigate with task | `/agent?q=…` |
| ASK/AGENT mode toggle | Switch omnibar mode | local |
| "Ask BIS" / "Run Agent" hero buttons | Navigate | `/ask`, `/agent` |
| 6 quick-action cards | Navigate | `/standards`, `/products`, `/standards`, `/labs`, `/compliance`, `/services` |

## Ask BIS `/ask`

| Element | Action | Target | Behavior |
|---|---|---|---|
| Example chips (4) | Send that question | POST `/api/chat` | disabled while busy |
| Message input + Send | Send conversation turn | POST `/api/chat` | Enter submits; busy → spinner + disabled |
| "New Conversation" | Reset thread | local | — |
| Per-answer "View Standard" | Navigate | `/standards/:is` | only when an IS was resolved |
| Per-answer "Use in Compliance Check" | Navigate prefilled | `/compliance?product=…` | same |
| Per-answer "Ask Agent" | Hand question to agent | `/agent?q=…` | — |
| Source cards (click) | — | displayed inline with clause/page/url | open external doc link |
| Error state Retry | Resend last question | POST `/api/chat` | — |

## AI Agent `/agent`

| Element | Action | Target | Behavior |
|---|---|---|---|
| Task input + "Run Agent" | Start agent task | POST `/api/agent/run` | progress phases shown live; disabled while running |
| 7 task templates | Fill + run task | POST `/api/agent/run` | — |
| Result "View Standard" | Navigate | `/standards/:is` | when standard resolved |
| Result "Start Compliance Check" | Navigate | `/compliance?product=…` | — |
| Result "Ask Follow-up" | Navigate | `/ask` | — |
| Citations cards | Display | inline | official-source badge |
| Error Retry | Re-run task | POST `/api/agent/run` | — |

## Compliance `/compliance(/:auditId)`

| Element | Action | Target | Behavior |
|---|---|---|---|
| Product input + "Create Audit" | Create audit | POST `/api/compliance/audit` | spinner; then navigate to workbench |
| "Browse" product suggestions | Search products | GET `/api/fe/products/search` | shows real product records to pick |
| FileDropzone (drag/browse) | Upload document | POST `/api/compliance/audit/:id/upload` (multipart) | per-file error toasts; list refreshes |
| "Process" | Extract evidence | POST `/api/compliance/audit/:id/process` | spinner + evidence count toast |
| "Analyze" | Run decision engine | POST `/api/compliance/audit/:id/analyze` | "analyzing" panel up to ~60s |
| Requirement row / "View Evidence" | Open evidence drawer | GET result data | shows requirement, decision, reason, evidence refs, BIS source |
| "Recheck Compliance" | Re-run with updated docs | POST `/api/compliance/audit/:id/recheck` | previous → current score diff |
| "View Report" | Open markdown report | GET `/api/compliance/audit/:id/report?fmt=markdown` | drawer with full report text |
| Remediation upload dropzone | Upload corrected evidence | upload + process + recheck flow | remediation card list |
| "Confirm Standard" → View Standard | Navigate | `/standards/:is` | — |
| Document remove button | Honest notice | **BNA**: no delete endpoint in this version | toast explains, no fake removal |
| Report drawer close | Close | local | — |

## Standards `/standards`, `/standards/:isNumber`

| Element | Action | Target |
|---|---|---|
| Search bar submit | Search standards | GET `/api/fe/standards/search` |
| Result card (click) | Navigate | `/standards/:is` |
| "Ask AI" | Navigate prefilled | `/ask?q=…` |
| "Use for Compliance" | Navigate prefilled | `/compliance?product=…` |
| "Official Source" (when URL) | Open external | EXT document |
| Detail: QCO / Scheme / Testing / Labs sections | Load independently | GET `/api/qco/:is`, `/api/schemes/:is`, `/api/tests/:is`, `/api/labs/:is` — empty text when no linkage |

## Products `/products`, `/products/:productId`

| Element | Action | Target |
|---|---|---|
| Search bar | Search products | GET `/api/fe/products/search` |
| Card (click) | Navigate | `/products/:id` |
| "Start Compliance Check" | Navigate prefilled | `/compliance?product=…` |
| Standard card (click) | Navigate | `/standards/:is` |

## Labs `/labs`, `/labs/:labId`

| Element | Action | Target |
|---|---|---|
| State dropdown | Real state list | GET `/api/fe/labs` → `states[]` |
| Search input + button | Filter labs | GET `/api/fe/labs?state=&q=` |
| Lab row (click) | Navigate | `/labs/:labId` |
| Pagination Previous/Next | Page through real rows | local slice (20/page) |
| Detail "Official Source" | Open scope document | EXT when `scope_url` present |

## Hallmarking `/hallmarking`

| Element | Action | Target |
|---|---|---|
| "Verify HUID — Official BIS" | Open official verifier | EXT https://huid.bis.gov.in |
| "Verify BIS Licence" | Open official portal | EXT https://www.bcare.bis.gov.in |
| Hallmarking guidance links | Open official docs | EXT bis.gov.in |
| Centre search + state filter | Search centres | GET `/api/fe/hallmarking/centres` |
| Pagination | Page through centres | local slice (20/page) |

## Offices `/offices` (BNA — honest state)

| Element | Action | Target |
|---|---|---|
| "Open Official BIS Portal" | Official offices directory | EXT https://www.bis.gov.in/offices/ |
| "Browse Recognized Laboratories" | Navigate | `/labs` (real data) |

## Services `/services`

Every service card has one of: **Open** (navigate to an in-app workspace with real data), **Ask AI** (navigate prefilled to `/ask`), **Open Official BIS Portal** (EXT link). 19 cards across industry / consumer / professional groups; zero cards without a working action.

## Resources / Help / About

| Element | Action | Target |
|---|---|---|
| 6 official portal cards | Open external | EXT (bis.gov.in, standardsbis.in, manakonline.in, bcare, huid) |
| "Inside this assistant" buttons | Navigate | workspaces |
| FAQ accordions | Expand/collapse | local |
| Help "Ask BIS" | Navigate | `/ask` |
| About external links | Open official | EXT |

## Toasts & global states

- Success/warning/error/info toasts top-right, click to dismiss.
- Loading spinners for every async action (LLM calls can take 8–60s — UI stays responsive with progress phases).
- Empty states ("No matching BIS information was found in the current knowledge base.") and Error states with Retry on every data surface.
