"""Audit context store: one JSON file per audit, simple index (spec 27/29).

Local storage only. No Postgres tables, no cloud. User documents live under
phase6/data/audits/<audit_id>/ and NEVER enter the BIS Qdrant collection.
"""
import json
import os
import re
import time
import uuid

import config as cfg


def _audit_dir(audit_id):
    d = os.path.join(cfg.UPLOADS_DIR, audit_id)
    os.makedirs(d, exist_ok=True)
    return d


def _path(audit_id):
    return os.path.join(_audit_dir(audit_id), "audit_context.json")


def _safe_id(audit_id):
    """audit ids are uuid4 hex we generate; sanitize anyway (defense in depth)."""
    return re.sub(r"[^a-zA-Z0-9\-]", "", str(audit_id))[:40]


def new_audit(product_text):
    """Creates the audit context (spec section 29 shape)."""
    audit_id = "AUD-%s" % uuid.uuid4().hex[:12]
    ctx = {"audit_id": audit_id,
           "product_text": product_text[:400],
           "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "status": "CREATED",
           "product": None, "bis_context": {},
           "documents": [], "evidence": [],
           "requirements": [], "results": [],
           "score": {}, "gaps": [], "remediation": [],
           "bis_sources": [], "report_md": ""}
    save(ctx)
    return ctx


def load(audit_id):
    p = _path(_safe_id(audit_id))
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save(ctx):
    audit_id = _safe_id(ctx.get("audit_id"))
    ctx["audit_id"] = audit_id
    with open(_path(audit_id), "w", encoding="utf-8") as f:
        json.dump(ctx, f, indent=1, ensure_ascii=False)
    return audit_id


def list_audits():
    out = []
    if not os.path.isdir(cfg.UPLOADS_DIR):
        return out
    for name in sorted(os.listdir(cfg.UPLOADS_DIR)):
        p = os.path.join(cfg.UPLOADS_DIR, name, "audit_context.json")
        if os.path.exists(p):
            try:
                with open(p, encoding="utf-8") as f:
                    ctx = json.load(f)
                out.append({"audit_id": ctx.get("audit_id"),
                            "product_text": ctx.get("product_text"),
                            "status": ctx.get("status"),
                            "documents": len(ctx.get("documents", [])),
                            "score": ctx.get("score", {}).get("score")})
            except Exception:
                continue
    return out


def uploads_dir(audit_id):
    return _audit_dir(_safe_id(audit_id))


def sanitize_filename(name):
    """Strip path/dangerous chars, keep extension, cap length."""
    name = os.path.basename(str(name or "upload"))
    name = re.sub(r"[^A-Za-z0-9._ ()\-]", "_", name)
    return name[:80] or "upload"


def validate_upload(filename, size_bytes):
    """Basic upload safety (spec 35): extension allowlist + size limit."""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in cfg.ALLOWED_EXTENSIONS:
        return "unsupported file type: %s (allowed: %s)" % (
            ext, ", ".join(sorted(cfg.ALLOWED_EXTENSIONS)))
    if size_bytes > cfg.MAX_FILE_MB * 1024 * 1024:
        return "file too large (limit %d MB)" % cfg.MAX_FILE_MB
    return ""
