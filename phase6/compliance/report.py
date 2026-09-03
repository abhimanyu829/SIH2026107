"""Final compliance-readiness report (spec section 21): JSON + Markdown.

Pre-audit only. The disclaimer is always present, always the same rule:
this is NOT official BIS certification or legal compliance.
"""
DISCLAIMER = ("This is an AI-assisted PRE-AUDIT READINESS assessment based on "
              "uploaded documents and the BIS data available in this "
              "prototype's knowledge base. It is NOT official BIS "
              "certification, NOT a legal compliance statement, and NOT a "
              "substitute for the actual BIS conformity assessment process.")


def build_report(audit):
    """audit context dict -> report dict (JSON contract)."""
    score = audit.get("score", {})
    results = audit.get("results", [])
    reqs = audit.get("requirements", [])
    docs = audit.get("documents", [])
    bis = audit.get("bis_context", {}) or {}
    std = bis.get("standard") or {}
    return {
        "audit_id": audit.get("audit_id", ""),
        "product": {"product_text": audit.get("product_text", ""),
                    "product": (audit.get("product") or {}),
                    "products_matched": bis.get("products", [])[:3]},
        "bis_standard": {"is_number": std.get("canonical_is_number") or "",
                         "title": std.get("title") or "",
                         "display": std.get("display_is_number") or ""},
        "qco_scheme": {"qcos": (bis.get("qcos") or [])[:4],
                       "schemes": (bis.get("schemes") or [])[:3],
                       "note": ("" if (bis.get("qcos") or bis.get("schemes"))
                                else "Authoritative BIS evidence was not "
                                     "found in the current knowledge base.")},
        "documents": [{"document_id": d.get("document_id"),
                       "filename": d.get("filename"),
                       "category": d.get("category"),
                       "pages": d.get("pages"),
                       "status": d.get("status")} for d in docs],
        "requirements_checked": len(reqs),
        "passed": [r for r in results if r["decision"] == "PASS"],
        "gaps": [r for r in results if r["decision"] == "GAP"],
        "unknown": [r for r in results if r["decision"] == "UNKNOWN"],
        "score": score,
        "critical_missing_evidence": _critical(audit),
        "remediation": audit.get("remediation", []),
        "bis_sources": audit.get("bis_sources", []),
        "disclaimer": DISCLAIMER,
    }


def _critical(audit):
    """GAPs on the highest-impact types first (calibration/testing/factory)."""
    order = {"CALIBRATION": 0, "TESTING": 1, "LAB": 2, "FACTORY": 3,
             "QCO": 4, "SCHEME": 5, "MANUAL": 6}
    crit = [r for r in audit.get("results", []) if r["decision"] == "GAP"]
    crit.sort(key=lambda r: order.get(r.get("type", ""), 9))
    return [{"requirement_id": r["requirement_id"],
             "missing": (r.get("reason") or "")[:160],
             "type": r.get("type", "")} for r in crit[:8]]


def to_markdown(report):
    """Same report as readable Markdown text (no PDF engine needed)."""
    s = report["score"]
    lines = [
        "# BIS Compliance Readiness Report (Pre-Audit)",
        "",
        "**%s**" % report["audit_id"],
        "",
        "## 1. Product",
        "- %s" % (report["product"]["product_text"] or "-"),
        "- Matched BIS product: %s" % (
            (report["product"]["product"] or {}).get("product_name", "-")),
        "",
        "## 2. Applicable BIS standard",
        "- %s %s" % (report["bis_standard"]["is_number"] or "-",
                     report["bis_standard"]["title"]),
        "",
        "## 3. QCO / Scheme",
    ]
    q, sch = report["qco_scheme"]["qcos"], report["qco_scheme"]["schemes"]
    if q:
        lines += ["- QCO: " + "; ".join(str(x.get("qco_number") or x) for x in q[:3])]
    if sch:
        lines += ["- Scheme: " + "; ".join(str(x.get("scheme_code") or x)
                                          for x in sch[:3])]
    if not (q or sch):
        lines += ["- " + report["qco_scheme"]["note"]]

    lines += ["", "## 4. Documents uploaded (%d)" % len(report["documents"])]
    for d in report["documents"]:
        lines.append("- %s [%s, %s pages, %s]"
                     % (d.get("filename"), d.get("category"),
                        d.get("pages"), d.get("status")))

    lines += ["", "## 5-8. Requirement results",
              "- Requirements checked: %d" % report["requirements_checked"],
              "- PASS: %d" % len(report["passed"]),
              "- GAP: %d" % len(report["gaps"]),
              "- UNKNOWN: %d" % len(report["unknown"]),
              "",
              "## 9. Readiness score",
              "- **%s: %s/100** (%d of %d passed)"
              % (s.get("label", "Compliance Readiness Score"), s.get("score"),
                 s.get("passed", 0), s.get("total", 0))]

    lines += ["", "## 10. Critical / missing evidence"]
    if report["critical_missing_evidence"]:
        for c in report["critical_missing_evidence"]:
            lines.append("- [%s] %s" % (c.get("type"), c.get("missing")))
    else:
        lines.append("- None - all checked requirements have supporting "
                     "evidence.")

    lines += ["", "## 11. Recommended remediation"]
    if report["remediation"]:
        for r in report["remediation"]:
            lines.append("- **%s (%s)**: %s"
                         % (r.get("requirement_id"), r.get("decision"),
                            r.get("recommendation")))
    else:
        lines.append("- None - no remediation needed for the checked "
                     "requirements.")

    lines += ["", "## 12. BIS sources"]
    for src in report["bis_sources"]:
        lines.append("- %s: %s" % (src.get("source"), src.get("detail")))
    if not report["bis_sources"]:
        lines.append("- Authoritative BIS evidence was not found in the "
                     "current knowledge base.")

    lines += ["", "## 13. Disclaimer", "", DISCLAIMER, ""]
    return "\n".join(lines)
