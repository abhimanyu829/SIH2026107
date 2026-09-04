# API_MAPPING.md — Frontend ↔ Backend Contract

One backend origin serves everything: the **Phase-6 app** (`phase6/compliance_api/app.py`)
mounts the existing Phase-5 FastAPI app and adds the compliance router + thin
frontend-support wrappers. Run:

```
cd phase6
python -m uvicorn compliance_api.app:app --port 8002
```

Frontend `API_BASE_URL` = `http://127.0.0.1:8002` (dev proxy configured).
No frontend secret exists — only API_BASE_URL. No direct Supabase/Qdrant/LLM access.

## Phase-5 endpoints (existing, unchanged)

| Frontend Feature | Frontend Button/Component | Backend Endpoint | Method | Request | Response | Loading State | Error State | UI Result |
|---|---|---|---|---|---|---|---|---|
| Health | app boot / connection banner | `/api/health` | GET | — | `{status, phase, llm, supabase:{ok}, qdrant:{ok}}` | — | banner "temporarily unavailable" | green dot in header |
| Ask BIS chat | Send (omnibar/chat page) | `/api/chat` | POST | `{message, conversation_id, language}` | `ChatResponse{answer, confidence, language, intent, entities, sources[], related{products,qcos,schemes,tests,labs}, agent{used,steps,tools_used}}` | "Finding BIS information…" | toast + retry | answer card + sources + related + follow-ups |
| AI Agent | Run Agent | `/api/agent/run` | POST | `{message, conversation_id, language}` | `AgentRunResponse{answer, status, plan[], steps[], tools_used[], evidence[], citations[], confidence, entities, unresolved_items[]}` | progress steps animation | inline error card | task summary + sources + next steps |
| Evidence search (global search evidence tab) | search submit | `/api/search` | POST | `{query, top_k, canonical_is_number?, document_type?, is_id?}` | `{query, count, results[], provenance}` | "Searching BIS…" | empty state | evidence list |
| Standard detail | Standards page → card click | `/api/standards/{is_number}?year=` | GET | — | `{data: standardRow, provenance}` | skeleton | 404 → empty state | standard detail page |
| Product detail | Products page → card click | `/api/products/{product_id}` | GET | — | `{data:{product, standards[]}, provenance}` | skeleton | 404 → empty state | product detail |
| QCO for standard | detail sections | `/api/qco/{is_number}` | GET | — | `{data: qcoRows, provenance}` | section spinner | "No QCO linkage established" | QCO panel |
| Scheme for standard | detail sections | `/api/schemes/{is_number}` | GET | — | `{data: schemeRows, provenance}` | section spinner | hidden if empty | scheme panel |
| Tests for standard | detail sections | `/api/tests/{is_number}` | GET | — | `{data: testRows, provenance}` | section spinner | "not established" | tests table |
| Labs for standard | detail sections | `/api/labs/{is_number}?limit=` | GET | — | `{data: labRows, provenance}` | section spinner | empty list state | labs table |
| Evidence document | View Source | `/api/evidence/{document_id}` | GET | — | `{data: documentRow, provenance}` | drawer spinner | drawer error | source in drawer |

## Phase-6 compliance endpoints (existing, unchanged)

| Frontend Feature | Frontend Button | Backend Endpoint | Method | Request | Response | Loading State | Error State | UI Result |
|---|---|---|---|---|---|---|---|---|
| Create audit | Start Compliance Check / wizard step 1 | `/api/compliance/audit` | POST | `{product_text}` | `{audit_id, product_text, product, is_number, status}` | "Creating audit…" | inline | wizard advances, standard shown |
| Upload document | Dropzone / Browse | `/api/compliance/audit/{id}/upload` | POST | multipart `file` | `{document_id, filename, status, ...}` | per-file progress | toast (400 invalid/unsupported/too large) | file chip w/ status |
| Process documents | Process | `/api/compliance/audit/{id}/process` | POST | `{document_ids: []}` | `{extract[], classify[], evidence_added, documents[]}` | "Processing documents…" | inline | files show ✓ + category |
| Analyze | Analyze | `/api/compliance/audit/{id}/analyze?max_requirements=&use_llm=` | POST | — | `{audit_id, score{score,total,passed,gaps,unknown,label}, requirements, results[], steps[], latency_sec}` | "Checking your documents against BIS requirements…" | inline error | score ring + PASS/GAP/UNKNOWN list |
| Results | results view | `/api/compliance/audit/{id}/result` | GET | — | `{audit_id, score, results[], gaps[], remediation[], status}` | spinner | 404 empty | result cards |
| Report | View Report | `/api/compliance/audit/{id}/report?fmt=json\|markdown` | GET | — | `ComplianceReport{...}` or markdown | "Generating report…" | 409 → "run analysis first" | report page |
| Recheck | Recheck Compliance | `/api/compliance/audit/{id}/recheck` | POST | query `max_requirements` | `{audit_id, score, recheck, status}` | "Re-running analysis…" | inline | before→after score |
| Audit state | wizard resume | `/api/compliance/audit/{id}` | GET | — | audit ctx (no page_texts) | spinner | 404 | wizard restores |
| Audit list | Compliance page list | `/api/compliance/audits` | GET | — | `{audits: AuditSummary[]}` | spinner | empty state | audit list |

## Frontend-support wrappers (`/api/fe/*`, thin — added this phase)

| Frontend Feature | Endpoint | Method | Request | Response | Provenance |
|---|---|---|---|---|---|
| Standards search page | `/api/fe/standards/search?q=&limit=` | GET | query params | `{data: [is_id, canonical_is_number, display_is_number, title, standard_status, mandatory_voluntary]}` | wraps `search_standards` tool |
| Products search page | `/api/fe/products/search?q=&limit=` | GET | query | `{data: productRows}` | wraps `find_product` tool |
| Product detail (alt) | `/api/fe/products/{product_id}` | GET | — | `{data:{product, standards}}` | same as /api/products |
| Labs browse (state/city/name) | `/api/fe/labs?state=&city=&q=&lab_type=&limit=` | GET | query | `{data:{labs[], states[]}}` | bis.lab_master |
| Lab detail + scope | `/api/fe/labs/{lab_id}` | GET | — | `{data:{lab, scope[]}}` | bis.lab_master + lab_scope |
| Hallmarking centres | `/api/fe/hallmarking/centres?state=&city=&q=&status=&limit=` | GET | query | `{data:{centres[], states[], statuses[]}}` | bis.hallmarking_master |
| QCO browse | `/api/fe/qcos?q=&limit=` | GET | query | `{data: qcoRows}` | bis.qco_master |
| Schemes browse | `/api/fe/schemes` | GET | — | `{data: schemeRows}` | bis.scheme_master |
| Product manuals browse | `/api/fe/manuals?q=&limit=` | GET | query | `{data: manualRows}` | bis.product_manual_master |

## Backend functions NOT available (honest UI states, never faked)

| Feature | Status | UI treatment |
|---|---|---|
| BIS offices directory | BACKEND FUNCTION NOT AVAILABLE (no office data in DB) | Offices page = official BIS portal link + labs nearby via /api/fe/labs |
| Verify HUID / licence transaction | BACKEND FUNCTION NOT AVAILABLE (verification of gov registry not in scope) | official BIS portal external link (Care/jewel portal) |
| Official BIS transactions (apply, pay, submit) | OFFICIAL-EXTERNAL-LINK | [Continue on Official BIS Portal] buttons → bis.gov.in |
| User accounts / auth | NOT AVAILABLE (out of scope) | none shown |

All external links: https://www.bis.gov.in, https://www.manakonline.in (hallmarking), https://www.bcare.bis.gov.in (licence verification).
