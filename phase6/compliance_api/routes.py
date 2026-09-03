"""Phase-6 FastAPI routes: /api/compliance/*.

These are included by phase6/api/app.py which MOUNTS the existing Phase-5
application - Phase 5 code is imported, not modified.
"""
import base64

from fastapi import APIRouter, File, HTTPException, UploadFile

from compliance_agent import store, ensure_registered
from compliance_agent.pipeline import run_analysis
from compliance_schemas import (AuditCreateRequest, ComplianceReport, ProcessRequest)

router = APIRouter(prefix="/api/compliance", tags=["compliance"])


def _ctx_or_404(audit_id):
    ctx = store.load(audit_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="audit not found")
    return ctx


@router.post("/audit")
def create_audit(req: AuditCreateRequest):
    """Create audit: resolve product + BIS context via Phase-5 tools."""
    ensure_registered()
    from compliance.requirements import resolve_product
    ctx = store.new_audit(req.product_text)
    resolved = resolve_product(req.product_text)
    if resolved.get("is_number"):
        ctx["product"] = resolved.get("product")
        ctx["bis_context"] = {"is_number": resolved["is_number"],
                              "standards": resolved.get("standards", [])[:3],
                              "products": resolved.get("products", [])[:3]}
        store.save(ctx)
    return {"audit_id": ctx["audit_id"],
            "product_text": ctx["product_text"],
            "product": ctx["product"],
            "is_number": (ctx.get("bis_context") or {}).get("is_number"),
            "status": ctx["status"]}


@router.post("/audit/{audit_id}/upload")
async def upload(audit_id: str, file: UploadFile = File(...)):
    """Upload one document into the audit (validated, stored locally)."""
    ensure_registered()
    _ctx_or_404(audit_id)
    raw = await file.read()
    err = store.validate_upload(file.filename or "upload", len(raw))
    if err:
        raise HTTPException(status_code=400, detail=err)
    b64 = base64.b64encode(raw).decode("ascii")
    from tools import call as p5_call
    r = p5_call("upload_document", audit_id=audit_id,
                filename=file.filename, content_b64=b64)
    if not r["ok"]:
        raise HTTPException(status_code=400, detail=r.get("error"))
    return r["data"]


@router.post("/audit/{audit_id}/process")
def process(audit_id: str, req: ProcessRequest = None):
    """Extract + classify + evidence for uploaded documents."""
    ensure_registered()
    _ctx_or_404(audit_id)
    from tools import call as p5_call
    e = p5_call("extract_document", audit_id=audit_id)
    c = p5_call("classify_document", audit_id=audit_id)
    v = p5_call("extract_evidence", audit_id=audit_id)
    ctx = _ctx_or_404(audit_id)
    return {"extract": e.get("data"), "classify": c.get("data"),
            "evidence_added": (v.get("data") or {}).get("added"),
            "documents": [{"document_id": d["document_id"],
                           "filename": d["filename"],
                           "category": d.get("category"),
                           "status": d.get("status"),
                           "pages": d.get("pages")} for d in ctx["documents"]]}


@router.post("/audit/{audit_id}/analyze")
def analyze(audit_id: str, max_requirements: int = 40, use_llm: bool = True):
    """Full compliance analysis: requirements, matching, decisions, score."""
    ensure_registered()
    _ctx_or_404(audit_id)
    out = run_analysis(audit_id, max_requirements=max_requirements,
                       use_llm=use_llm)
    if not out.get("ok"):
        raise HTTPException(status_code=502, detail=out.get("error", "failed"))
    ctx = _ctx_or_404(audit_id)
    return {"audit_id": audit_id, "score": ctx.get("score"),
            "requirements": len(ctx.get("requirements", [])),
            "results": ctx.get("results", []),
            "steps": out.get("steps", []),
            "latency_sec": out.get("latency_sec")}


@router.get("/audit/{audit_id}/result")
def result(audit_id: str):
    ctx = _ctx_or_404(audit_id)
    return {"audit_id": audit_id, "score": ctx.get("score"),
            "results": ctx.get("results", []),
            "gaps": ctx.get("gaps", []),
            "remediation": ctx.get("remediation", []),
            "status": ctx.get("status")}


@router.get("/audit/{audit_id}/report")
def report(audit_id: str, fmt: str = "json"):
    ctx = _ctx_or_404(audit_id)
    if not ctx.get("report_md"):
        raise HTTPException(status_code=409,
                            detail="analysis not run yet - POST "
                                   "/api/compliance/audit/%s/analyze first"
                            % audit_id)
    rep = ComplianceReport(**build_report_dict(ctx))
    if fmt == "markdown":
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(ctx["report_md"], media_type="text/markdown")
    return rep


def build_report_dict(ctx):
    from compliance.report import build_report
    return build_report(ctx)


@router.post("/audit/{audit_id}/recheck")
def recheck(audit_id: str, max_requirements: int = 40):
    """Re-run after corrected/new documents: same pipeline, fresh evidence."""
    ensure_registered()
    _ctx_or_404(audit_id)
    from tools import call as p5_call
    r = p5_call("recheck_compliance", audit_id=audit_id,
                max_requirements=max_requirements)
    if not r["ok"]:
        raise HTTPException(status_code=502, detail=r.get("error", "failed"))
    ctx = _ctx_or_404(audit_id)
    return {"audit_id": audit_id, "score": ctx.get("score"),
            "recheck": r["data"].get("score"), "status": ctx.get("status")}


@router.get("/audit/{audit_id}")
def audit_state(audit_id: str):
    ctx = _ctx_or_404(audit_id)
    safe = {k: v for k, v in ctx.items() if k not in ("report_md",)}
    for d in safe.get("documents", []):
        d.pop("page_texts", None)
        d.pop("path", None)
    return safe


@router.get("/audits")
def audits():
    return {"audits": store.list_audits()}


