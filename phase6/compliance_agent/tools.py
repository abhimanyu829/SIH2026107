"""Phase-6 compliance tools, registered into the EXISTING Phase-5 registry.

The 14 tools from spec section 23 live beside the Phase-5 tools with the same
ToolResult contract. Nothing else in Phase 5 changes.
"""
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "phase5"))

import config as cfg  # noqa: E402  (phase6 config)
from compliance_agent import store  # noqa: E402
from tools.registry import ToolResult, tool  # noqa: E402  (phase5 registry)


# ---- audit lifecycle --------------------------------------------------------
@tool("upload_document",
      "Upload one manufacturer document (PDF/DOCX/XLSX/TXT/PNG/JPG) into an "
      "audit. Validates type + size, stores locally under the audit dir.",
      "phase6 local audit storage")
def upload_document(audit_id: str, filename: str, content_b64: str) -> ToolResult:
    import base64
    aid = store._safe_id(audit_id)
    if not store.load(aid):
        return ToolResult(ok=False, tool="upload_document", data=None,
                          error="audit not found: %s" % aid, provenance="")
    fname = store.sanitize_filename(filename)
    err = store.validate_upload(fname, len(content_b64 or "") * 3 // 4)
    if err:
        return ToolResult(ok=False, tool="upload_document", data=None,
                          error=err, provenance="")
    dest = os.path.join(store.uploads_dir(aid), fname)
    with open(dest, "wb") as f:
        f.write(base64.b64decode(content_b64))
    doc_id = "DOC-%s" % uuid.uuid4().hex[:8]
    ctx = store.load(aid)
    ctx["documents"].append({"document_id": doc_id, "filename": fname,
                             "path": dest, "status": "UPLOADED",
                             "category": "", "pages": 0})
    ctx["status"] = "CREATED"
    store.save(ctx)
    return ToolResult(ok=True, tool="upload_document",
                      data={"document_id": doc_id, "filename": fname,
                            "stored": dest, "size_bytes": os.path.getsize(dest)},
                      error="", provenance="phase6 local storage (never BIS "
                                           "knowledge)")


@tool("list_uploaded_documents",
      "List documents uploaded to an audit with their processing status.",
      "phase6 local audit storage")
def list_uploaded_documents(audit_id: str) -> ToolResult:
    ctx = store.load(audit_id)
    if not ctx:
        return ToolResult(ok=False, tool="list_uploaded_documents", data=None,
                          error="audit not found", provenance="")
    docs = [{"document_id": d.get("document_id"), "filename": d.get("filename"),
             "category": d.get("category"), "status": d.get("status"),
             "pages": d.get("pages")} for d in ctx.get("documents", [])]
    return ToolResult(ok=True, tool="list_uploaded_documents", data=docs,
                      error="", provenance="phase6 local audit storage")


# ---- processing -------------------------------------------------------------
@tool("extract_document",
      "Extract text from one or all audit documents (PDF/DOCX/XLSX/TXT; OCR "
      "fallback only when text extraction is empty and OCR is available).",
      "phase6 documents/extraction")
def extract_document(audit_id: str, document_id: str = "") -> ToolResult:
    from documents import extraction
    ctx = store.load(audit_id)
    if not ctx:
        return ToolResult(ok=False, tool="extract_document", data=None,
                          error="audit not found", provenance="")
    targets = [d for d in ctx.get("documents", [])
               if d.get("status") == "UPLOADED"
              and (not document_id or d.get("document_id") == document_id)]
    if not targets:
        return ToolResult(ok=False, tool="extract_document", data=None,
                          error="no unprocessed documents", provenance="")
    done = []
    for d in targets:
        pages, meta = extraction.extract(d["path"])
        d["pages"] = meta.get("pages", 0)
        d["chars"] = meta.get("chars", 0)
        d["ocr_used"] = meta.get("ocr_used", False)
        d["page_texts"] = [p.to_dict() for p in pages]
        d["status"] = "EXTRACTED" if pages and not meta.get("error") else \
            "EXTRACTION_FAILED: %s" % (meta.get("error") or "no text")
        done.append({"document_id": d["document_id"],
                     "filename": d["filename"], "pages": d["pages"],
                     "status": d["status"]})
    store.save(ctx)
    return ToolResult(ok=True, tool="extract_document", data=done, error="",
                      provenance="phase6 documents/extraction (PyMuPDF, "
                                 "python-docx, openpyxl)")


@tool("classify_document",
      "Classify extracted audit documents into CALIBRATION_CERTIFICATE, "
      "TEST_REPORT, FACTORY_DOCUMENT, QC_DOCUMENT, RAW_MATERIAL_DOCUMENT, "
      "PROCESS_DOCUMENT, MACHINERY_DOCUMENT or OTHER. Rules first, LLM only "
      "when ambiguous.",
      "phase6 documents/classification")
def classify_document(audit_id: str, document_id: str = "") -> ToolResult:
    from documents import classification
    ctx = store.load(audit_id)
    if not ctx:
        return ToolResult(ok=False, tool="classify_document", data=None,
                          error="audit not found", provenance="")
    out = []
    for i, d in enumerate(list(ctx.get("documents", []))):
        if document_id and d.get("document_id") != document_id:
            continue
        if d.get("status") == "UPLOADED":
            r = extract_document(audit_id, d["document_id"])
            if not r["ok"]:
                continue
            ctx = store.load(audit_id)     # fresh dict: extraction saved it
            d = ctx["documents"][i]         # re-bind to the saved document
        if not str(d.get("status", "")).startswith("EXTRACTED"):
            continue
        # classify() reads page dicts; the stored document keeps them in
        # 'page_texts' ('pages' holds the page COUNT)
        cls_doc = dict(d, pages=d.get("page_texts", []))
        result = classification.classify(cls_doc)
        d["category"] = result["category"]
        d["category_confidence"] = result["confidence"]
        d["category_method"] = result["method"]
        out.append({"document_id": d["document_id"],
                    "filename": d["filename"],
                    "category": result["category"],
                    "confidence": result["confidence"],
                    "method": result["method"]})
    store.save(ctx)
    return ToolResult(ok=True, tool="classify_document", data=out, error="",
                      provenance="phase6 documents/classification "
                                 "(rules + optional LLM)")


@tool("extract_evidence",
      "Extract compliance-useful evidence fields from extracted documents "
      "(instrument IDs, dates, results, factory details) with page citations.",
      "phase6 documents/evidence")
def extract_evidence(audit_id: str) -> ToolResult:
    from documents import evidence as ev
    ctx = store.load(audit_id)
    if not ctx:
        return ToolResult(ok=False, tool="extract_evidence", data=None,
                          error="audit not found", provenance="")
    # keep only pre-existing evidence from docs NOT being reprocessed
    keep_ids = {d["document_id"] for d in ctx.get("documents", [])}
    ctx["evidence"] = [e for e in ctx.get("evidence", [])
                       if e.get("document_id") not in keep_ids]
    added = 0
    for d in ctx.get("documents", []):
        if not str(d.get("status", "")).startswith("EXTRACTED"):
            continue
        if d.get("category") in ("", None):
            continue
        ev_doc = dict(d, pages=d.get("page_texts", []))
        items = ev.extract_evidence(ev_doc)
        ctx["evidence"].extend(items)
        added += len(items)
        d["evidence_count"] = len(items)
    store.save(ctx)
    return ToolResult(ok=True, tool="extract_evidence",
                      data={"added": added, "total": len(ctx["evidence"]),
                            "items": ctx["evidence"][:20]}, error="",
                      provenance="phase6 documents/evidence (regex fields)")


# ---- BIS side ----------------------------------------------------------------
@tool("get_applicable_requirements",
      "Normalized BIS requirement list for the audit's product: standard, "
      "QCO, scheme, Product Manual sections, tests. Sources are real BIS "
      "rows via Phase-5 lookups; nothing invented.",
      "Phase-5 Supabase lookups (is_master, is_qco_mapping, "
      "is_scheme_mapping, product_manual_*, is_test_mapping)")
def get_applicable_requirements(audit_id: str, max_requirements: int = 40) -> ToolResult:
    from compliance import requirements as R
    ctx = store.load(audit_id)
    if not ctx:
        return ToolResult(ok=False, tool="get_applicable_requirements",
                          data=None, error="audit not found", provenance="")
    if not ctx.get("bis_context") or not ctx["bis_context"].get("is_number"):
        resolved = R.resolve_product(ctx.get("product_text", ""))
        if resolved.get("error") and not resolved.get("is_number"):
            return ToolResult(ok=False, tool="get_applicable_requirements",
                              data=None, error=resolved["error"],
                              provenance="phase5 find_product/search_standards")
        ctx["product"] = resolved.get("product")
        ctx["bis_context"] = {"is_number": resolved.get("is_number"),
                              "standards": resolved.get("standards", [])[:3],
                              "products": resolved.get("products", [])[:3]}
        store.save(ctx)
    is_num = ctx["bis_context"].get("is_number")
    if not is_num:
        return ToolResult(ok=False, tool="get_applicable_requirements",
                          data=None,
                          error="Authoritative BIS evidence was not found in "
                                "the current knowledge base for this product.",
                          provenance="phase5 Supabase/Qdrant")
    reqs, std_row = R.build_requirements(is_num, max_requirements)
    ctx["requirements"] = reqs
    if std_row:
        ctx["bis_context"]["standard"] = std_row
    ctx["bis_sources"] = R.requirement_sources(is_num)
    store.save(ctx)
    return ToolResult(ok=True, tool="get_applicable_requirements",
                      data={"is_number": is_num, "count": len(reqs),
                            "requirements": reqs},
                      error="",
                      provenance="Supabase bis.* via phase5 tools; no "
                                "invented requirements")


# ---- matching + decision ------------------------------------------------------
@tool("match_evidence",
      "Match audit evidence against the BIS requirement list "
      "(category -> keywords -> structured values; LLM only for ambiguity).",
      "phase6 compliance/matching")
def match_evidence(audit_id: str) -> ToolResult:
    from compliance import matching
    ctx = store.load(audit_id)
    if not ctx:
        return ToolResult(ok=False, tool="match_evidence", data=None,
                          error="audit not found", provenance="")
    out = []
    for req in ctx.get("requirements", []):
        cands, matched = matching.match_requirement(req, ctx.get("evidence", []))
        out.append({"requirement_id": req["requirement_id"],
                    "candidates": len(cands), "matched": len(matched)})
    ctx["matches"] = out
    store.save(ctx)
    return ToolResult(ok=True, tool="match_evidence", data=out, error="",
                      provenance="phase6 compliance/matching")


@tool("check_requirement",
      "Decide one requirement: PASS, GAP or UNKNOWN, with reason, evidence "
      "refs, conflicts and BIS source. Never promotes UNKNOWN to PASS.",
      "phase6 compliance/decision")
def check_requirement(audit_id: str, requirement_id: str) -> ToolResult:
    from compliance import decision
    ctx = store.load(audit_id)
    if not ctx:
        return ToolResult(ok=False, tool="check_requirement", data=None,
                          error="audit not found", provenance="")
    req = next((r for r in ctx.get("requirements", [])
                if r["requirement_id"] == requirement_id), None)
    if not req:
        return ToolResult(ok=False, tool="check_requirement", data=None,
                          error="requirement not found: %s" % requirement_id,
                          provenance="")
    result = decision.decide(req, ctx.get("evidence", []))
    return ToolResult(ok=True, tool="check_requirement", data=result, error="",
                      provenance="phase6 compliance/decision + BIS source: "
                                 + result.get("bis_source", ""))


# ---- score / gaps / remediation / report -------------------------------------
@tool("calculate_readiness_score",
      "Compliance Readiness Score: PASS fraction of all checked requirements. "
      "Pre-audit indicator, not official BIS compliance.",
      "phase6 compliance/scoring")
def calculate_readiness_score(audit_id: str) -> ToolResult:
    from compliance import scoring
    ctx = store.load(audit_id)
    if not ctx:
        return ToolResult(ok=False, tool="calculate_readiness_score", data=None,
                          error="audit not found", provenance="")
    s = scoring.score(ctx.get("results", []))
    ctx["score"] = s
    ctx["gaps"] = scoring.gaps(ctx.get("results", []))
    store.save(ctx)
    return ToolResult(ok=True, tool="calculate_readiness_score", data=s,
                      error="", provenance="phase6 compliance/scoring "
                                          "('Compliance Readiness Score')")


@tool("identify_gaps",
      "Gap analysis: every GAP/UNKNOWN requirement with reason, missing "
      "evidence and BIS source.",
      "phase6 compliance/scoring")
def identify_gaps(audit_id: str) -> ToolResult:
    ctx = store.load(audit_id)
    if not ctx:
        return ToolResult(ok=False, tool="identify_gaps", data=None,
                          error="audit not found", provenance="")
    items = [{"requirement_id": g["requirement_id"],
              "decision": g["decision"],
              "gap": g["requirement"][:200],
              "reason": g["reason"],
              "missing_evidence": next(
                  (r.get("evidence_expected") for r in ctx.get("requirements", [])
                   if r["requirement_id"] == g["requirement_id"]), ""),
              "bis_source": g.get("bis_source", "")}
             for g in ctx.get("gaps", [])]
    return ToolResult(ok=True, tool="identify_gaps", data=items, error="",
                      provenance="phase6 compliance/scoring")


@tool("generate_remediation",
      "Simple actionable remediation suggestions for each GAP/UNKNOWN, based "
      "on the actual requirement's expected evidence.",
      "phase6 compliance/remediation")
def generate_remediation(audit_id: str) -> ToolResult:
    from compliance import remediation as rem
    ctx = store.load(audit_id)
    if not ctx:
        return ToolResult(ok=False, tool="generate_remediation", data=None,
                          error="audit not found", provenance="")
    items = rem.generate(ctx.get("results", []), ctx.get("requirements", []))
    ctx["remediation"] = items
    store.save(ctx)
    return ToolResult(ok=True, tool="generate_remediation", data=items,
                      error="", provenance="phase6 compliance/remediation")


@tool("generate_compliance_report",
      "Final compliance-readiness report: JSON + Markdown, with disclaimer. "
      "Pre-audit readiness, not official BIS certification.",
      "phase6 compliance/report")
def generate_compliance_report(audit_id: str) -> ToolResult:
    from compliance import report as rep
    ctx = store.load(audit_id)
    if not ctx:
        return ToolResult(ok=False, tool="generate_compliance_report",
                          data=None, error="audit not found", provenance="")
    r = rep.build_report(ctx)
    md = rep.to_markdown(r)
    ctx["report_md"] = md
    store.save(ctx)
    return ToolResult(ok=True, tool="generate_compliance_report",
                      data={"report": r, "markdown": md}, error="",
                      provenance="phase6 compliance/report (pre-audit "
                                 "readiness only)")


@tool("recheck_compliance",
      "Re-run the full analysis after new/corrected documents were uploaded: "
      "re-extract, re-classify, re-extract evidence, re-match, re-score.",
      "phase6 full pipeline")
def recheck_compliance(audit_id: str, max_requirements: int = 40) -> ToolResult:
    ctx = store.load(audit_id)
    if not ctx:
        return ToolResult(ok=False, tool="recheck_compliance", data=None,
                          error="audit not found", provenance="")
    from compliance_agent.pipeline import run_analysis
    out = run_analysis(audit_id, max_requirements=max_requirements)
    return ToolResult(ok=out.get("ok", False), tool="recheck_compliance",
                      data=out, error=out.get("error", ""),
                      provenance="phase6 agent/pipeline (recheck)")

