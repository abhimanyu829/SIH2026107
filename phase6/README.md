# BIS SIH26107 - Phase 6: AI-assisted Compliance Readiness (Pre-Audit)

Adds a simple manufacturer-readiness feature on top of Phase 5. A manufacturer
identifies a product, uploads factory documents, and gets PASS/GAP/UNKNOWN
per requirement, a Compliance Readiness Score, gap analysis, remediation and
a report - then can recheck after uploading corrected evidence.

**This is a PRE-AUDIT / READINESS prototype. It is NOT official BIS
certification and NOT a legal compliance statement.**

## Reuses Phase 5 (nothing rebuilt)

- Same FastAPI app (mounted, not modified): `phase6/api/app.py` imports
  `phase5/api/main.py` and includes the compliance router.
- Same tool registry: the 13 Phase-6 tools register beside Phase-5 tools
  (`phase6/agent/tools.py` uses `phase5/tools/registry.py`).
- Same Supabase/Qdrant via Phase-5 tools (`find_product`, `get_standard`,
  `get_qco`, `get_scheme`, `get_product_manual`, `get_tests`, `find_labs`).
- Same LLM configuration (tokenrouter, deterministic fallback without a key).
- No new services, no queue, no object storage, no auth framework.

## Layout

```
phase6/
  documents/extraction.py      PDF (PyMuPDF), DOCX (python-docx), XLSX (openpyxl),
                               TXT + OCR fallback only when needed
  documents/classification.py  keyword rules first, LLM only when ambiguous
  documents/evidence.py       regex field extraction with page citations
  compliance/requirements.py  BIS requirements from real Phase-5 lookups
  compliance/matching.py      category -> keyword -> structured -> LLM-last
  compliance/decision.py      PASS / GAP / UNKNOWN engine (spec rules)
  compliance/scoring.py       Compliance Readiness Score (PASS fraction)
  compliance/remediation.py   template-based suggestions
  compliance/report.py        JSON + Markdown report with disclaimer
  agent/store.py              audit contexts, local JSON, uploads per audit_id
  agent/tools.py              13 tools into the phase5 registry
  agent/pipeline.py           the analysis pipeline + LangGraph wrapper
  api/routes.py               /api/compliance/* endpoints
  api/app.py                  mounts the existing phase5 app
  run_phase6.py               check / tests / demo / serve (:8002)
  tests/                      fixtures generator + 18 test cases
```

## API

POST /api/compliance/audit                        create audit
POST /api/compliance/audit/{id}/upload            upload document (multipart)
POST /api/compliance/audit/{id}/process           extract+classify+evidence
POST /api/compliance/audit/{id}/analyze           full analysis
GET  /api/compliance/audit/{id}/result            results + gaps
GET  /api/compliance/audit/{id}/report            report (?fmt=markdown)
POST /api/compliance/audit/{id}/recheck           re-run after new evidence
GET  /api/compliance/audit/{id}                   audit state
GET  /api/compliance/audits                       list audits
(+ all Phase-5 endpoints unchanged)

## Run

```powershell
pip install python-docx pymupdf openpyxl     # document formats
python phase6/tests/make_fixtures.py          # synthetic demo documents
python phase6/run_phase6.py --check           # offline sanity
python phase6/run_phase6.py                  # tests + flagship demo
python phase6/run_phase6.py --serve          # uvicorn :8002
```

## Decision rules (never guess)

- No candidate evidence -> GAP ("No X evidence was found.")
- Vague mention without detail fields -> UNKNOWN ("Insufficient evidence.")
- Conflicting values -> UNKNOWN ("Conflicting evidence detected.")
- Expired calibration validity -> GAP
- Valid detailed evidence -> PASS (cites document, page, BIS source)
- UNKNOWN is never promoted to PASS.
- Missing BIS data -> "Authoritative BIS evidence was not found in the
  current knowledge base."

## Privacy

Uploaded documents are USER EVIDENCE: local files under
`phase6/data/audits/<audit_id>/`, never inserted into the BIS Qdrant
collection, never global knowledge, never training data.
