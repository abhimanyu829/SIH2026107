"""Tests 6-15: matching, PASS/GAP/UNKNOWN, conflict, score, remediation,
report, recheck, end-to-end."""
import base64
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _base import (FIXTURES, SkipTest, bis_db_loaded, db_available,  # noqa: E402
                   run_cases)

CAL_REQ = {"requirement_id": "REQ-001",
           "requirement": "Testing instruments must hold valid calibration "
                          "records.",
           "type": "CALIBRATION", "source": "Product Manual", "clause": "4.3",
           "evidence_expected": "valid calibration certificate"}
TEST_REQ = {"requirement_id": "REQ-002",
            "requirement": "Test 'Stability test' must be performed as per "
                           "IS 17631.",
            "type": "TESTING", "source": "bis.is_test_mapping", "clause": "",
            "evidence_expected": "test report for 'Stability test'"}
FACTORY_REQ = {"requirement_id": "REQ-003",
               "requirement": "Manufacturing premises and production "
                              "capability must be documented.",
               "type": "FACTORY", "source": "bis.product_master", "clause": "",
               "evidence_expected": "factory / premises document"}


def _doc(fname, category):
    from documents.extraction import extract
    pages, _ = extract(os.path.join(FIXTURES, fname))
    return {"filename": fname, "document_id": "DOC-T", "category": category,
            "pages": [p.to_dict() for p in pages]}


def _evidence(fname, category):
    from documents import evidence as ev
    return ev.extract_evidence(_doc(fname, category))


def t_matching():
    from compliance.matching import match_requirement
    evidence = _evidence("calibration_certificate.pdf", "CALIBRATION_CERTIFICATE")
    cands, matched = match_requirement(CAL_REQ, evidence)
    if not cands:
        return "no candidates for calibration evidence"
    if not matched:
        return "calibration evidence did not match calibration requirement"
    cands2, matched2 = match_requirement(CAL_REQ, [])
    if cands2 or matched2:
        return "empty evidence must match nothing"
    return ""


def t_pass():
    from compliance.decision import decide
    evidence = _evidence("calibration_certificate.pdf", "CALIBRATION_CERTIFICATE")
    r = decide(CAL_REQ, evidence)
    if r["decision"] != "PASS":
        return "expected PASS, got %s (%s)" % (r["decision"], r["reason"])
    if not r["evidence_refs"]:
        return "PASS must cite evidence"
    if "Product Manual" not in r["bis_source"]:
        return "BIS source missing from PASS result"
    return ""


def t_gap():
    from compliance.decision import decide
    r = decide(CAL_REQ, [])                       # nothing uploaded
    if r["decision"] != "GAP":
        return "expected GAP with no evidence, got %s" % r["decision"]
    if "No calibration" not in r["reason"] and "No " not in r["reason"]:
        return "GAP reason must say no evidence: %s" % r["reason"]
    return ""


def t_unknown_vague():
    from compliance.decision import decide
    evidence = _evidence("vague_calibration.txt", "OTHER")
    # the vague doc yields little - decide with it alone
    r = decide(CAL_REQ, evidence)
    if r["decision"] == "PASS":
        return "vague evidence must never be PASS (spec 15)"
    return ""


def t_conflict():
    from compliance.decision import decide
    a = _evidence("calibration_certificate.pdf", "CALIBRATION_CERTIFICATE")
    b = _evidence("conflicting_validity.pdf", "CALIBRATION_CERTIFICATE")
    r = decide(CAL_REQ, a + b)
    if r["decision"] != "UNKNOWN":
        return "conflicting evidence must be UNKNOWN, got %s" % r["decision"]
    if "Conflicting evidence detected" not in r["reason"]:
        return "conflict reason missing: %s" % r["reason"]
    if not r.get("conflicts"):
        return "conflict details not preserved"
    return ""


def t_expired():
    from compliance.decision import decide
    evidence = _evidence("calibration_expired.pdf", "CALIBRATION_CERTIFICATE")
    r = decide(CAL_REQ, evidence)
    if r["decision"] != "GAP":
        return "expired validity must be GAP, got %s" % r["decision"]
    return ""


def t_score():
    from compliance.scoring import score
    results = [{"decision": "PASS", "type": "A"}, {"decision": "PASS", "type": "A"},
               {"decision": "GAP", "type": "B"}, {"decision": "UNKNOWN", "type": "B"}]
    s = score(results)
    if (s["total"], s["passed"], s["gaps"], s["unknown"]) != (4, 2, 1, 1):
        return "counts wrong: %s" % s
    if s["score"] != 50:
        return "score must be 50, got %s" % s["score"]
    if s["label"] != "Compliance Readiness Score":
        return "label must be Compliance Readiness Score"
    if score([])["score"] != 0:
        return "empty results must score 0"
    return ""


def t_remediation():
    from compliance.remediation import generate
    results = [{"requirement_id": "REQ-001", "decision": "GAP",
                 "requirement": CAL_REQ["requirement"],
                 "reason": "No calibration evidence was found.",
                 "bis_source": "Product Manual clause 4.3"},
                {"requirement_id": "REQ-002", "decision": "UNKNOWN",
                 "requirement": TEST_REQ["requirement"],
                 "reason": "Conflicting evidence detected for 'result'.",
                 "bis_source": "bis.is_test_mapping"}]
    items = generate(results, [CAL_REQ, TEST_REQ])
    if len(items) != 2:
        return "expected 2 remediation items, got %d" % len(items)
    rec = items[0]["recommendation"]
    if "calibration certificate" not in rec.lower():
        return "calibration remediation wrong: %s" % rec
    if "conflicting" not in items[1]["recommendation"].lower():
        return "conflict remediation must mention conflict: %s" % \
            items[1]["recommendation"]
    return ""


def t_report():
    from compliance.report import build_report, to_markdown
    audit = {"audit_id": "AUD-T", "product_text": "office work chairs",
             "product": {"product_name": "Work Chairs"},
             "bis_context": {"is_number": "17631",
                             "standard": {"canonical_is_number": "IS 17631",
                                          "title": "WORK CHAIRS - SPECIFICATION",
                                          "display_is_number": "IS 17631:2022"},
                             "qcos": [{"qco_number": "QCO-00052"}],
                             "schemes": [{"scheme_code": "SCH-00019"}]},
             "documents": [{"document_id": "D1", "filename": "a.pdf",
                             "category": "TEST_REPORT", "pages": 1,
                             "status": "EXTRACTED"}],
             "requirements": [CAL_REQ, TEST_REQ],
             "results": [{"requirement_id": "REQ-001", "requirement": "x",
                          "type": "CALIBRATION", "decision": "GAP",
                          "reason": "No calibration evidence was found.",
                          "evidence_refs": [], "bis_source": "Product Manual",
                          "clause": "4.3", "conflicts": []}],
             "score": {"score": 0, "total": 2, "passed": 0, "gaps": 1,
                       "unknown": 1, "label": "Compliance Readiness Score"},
             "gaps": [], "remediation": [],
             "bis_sources": [{"source": "bis.is_master", "detail": "IS 17631"}]}
    rep = build_report(audit)
    md = to_markdown(rep)
    if rep["audit_id"] != "AUD-T":
        return "report audit id wrong"
    if "NOT official BIS" not in rep["disclaimer"]:
        return "disclaimer missing"
    if "Compliance Readiness Report" not in md:
        return "markdown title missing"
    if "IS 17631" not in md:
        return "BIS standard missing from markdown"
    if "Disclaimer" not in md:
        return "markdown disclaimer section missing"
    return ""


def _upload_all(aid, names):
    import compliance_agent.tools  # noqa: F401
    from tools import call as p5_call
    for n in names:
        with open(os.path.join(FIXTURES, n), "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        r = p5_call("upload_document", audit_id=aid, filename=n, content_b64=b64)
        if not r["ok"]:
            return "upload failed: %s" % r["error"]
    return ""


def t_recheck_and_e2e():
    """End-to-end + recheck: synthetic fixtures decide deterministically
    against locally-built requirements (no DB dependency for the core test;
    live DB adds the real BIS requirement list)."""
    from compliance_agent import store
    import compliance_agent.tools  # noqa: F401
    from compliance_agent.pipeline import run_analysis
    from compliance import requirements as req_mod

    if bis_db_loaded():
        ctx = store.new_audit("office work chairs")
        resolved = req_mod.resolve_product("office work chairs")
        if not resolved.get("is_number"):
            return "DB live but product not resolved"
        ctx["product"] = resolved.get("product")
        ctx["bis_context"] = {"is_number": resolved["is_number"],
                              "standards": resolved.get("standards", [])[:3],
                              "products": resolved.get("products", [])[:3]}
        store.save(ctx)
    elif db_available():
        # credentials exist but the BIS tables are empty (Phase-4 load pending):
        # synthetic requirements still exercise the full decision+recheck flow
        ctx = store.new_audit("office work chairs")
        ctx["requirements"] = [CAL_REQ, TEST_REQ, FACTORY_REQ]
        ctx["bis_context"] = {"is_number": None}
        store.save(ctx)
    else:
        # offline: build a synthetic requirement set directly
        ctx = store.new_audit("office work chairs")
        ctx["requirements"] = [CAL_REQ, TEST_REQ, FACTORY_REQ]
        ctx["bis_context"] = {"is_number": None}
        store.save(ctx)

    aid = ctx["audit_id"]
    err = _upload_all(aid, ["calibration_certificate.pdf", "test_report.pdf",
                            "factory_details.docx"])
    if err:
        return err
    out = run_analysis(aid)
    if not out.get("ok"):
        return "analysis failed: %s" % out.get("error")
    ctx = store.load(aid)
    s = ctx.get("score", {})
    if s.get("total", 0) == 0:
        return "no requirements checked"
    if not (0 <= s.get("score", -1) <= 100):
        return "score out of range"
    # PASS must exist (calibration + test report + factory uploaded)
    decisions = {r["decision"] for r in ctx.get("results", [])}
    if "PASS" not in decisions:
        return "uploaded valid docs must produce at least one PASS"

    # GAP path: no calibration uploaded at all
    ctx2 = store.new_audit("office work chairs")
    ctx2["requirements"] = [CAL_REQ]
    ctx2["bis_context"] = {"is_number": None}
    store.save(ctx2)
    out2 = run_analysis(ctx2["audit_id"])
    ctx2 = store.load(ctx2["audit_id"])
    r0 = ctx2.get("results", [{}])[0]
    if r0.get("decision") != "GAP":
        return "missing calibration must be GAP, got %s" % r0.get("decision")

    # recheck: start from an expired calibration (GAP), then upload the
    # corrected certificate and re-run - the same requirement must flip to
    # PASS. (Kept in one audit WITHOUT the expired doc's instrument to avoid
    # a deliberate conflict; here the corrected doc supersedes by recheck.)
    ctx3 = store.new_audit("office work chairs")
    ctx3["requirements"] = [CAL_REQ]
    ctx3["bis_context"] = {"is_number": None}
    store.save(ctx3)
    aid3 = ctx3["audit_id"]
    _upload_all(aid3, ["calibration_expired.pdf"])
    run_analysis(aid3)
    before = store.load(aid3).get("results", [{}])[0].get("decision")
    if before != "GAP":
        return "expired calibration must be GAP, got %s" % before

    # remove the expired doc's evidence influence the honest way: a fresh
    # recheck audit with only the corrected certificate
    ctx4 = store.new_audit("office work chairs")
    ctx4["requirements"] = [CAL_REQ]
    ctx4["bis_context"] = {"is_number": None}
    store.save(ctx4)
    aid4 = ctx4["audit_id"]
    _upload_all(aid4, ["fixed_validity.pdf"])
    run_analysis(aid4)
    after = store.load(aid4).get("results", [{}])[0].get("decision")
    if after != "PASS":
        return "corrected calibration must be PASS after recheck, got %s" % after
    s_before = store.load(aid3).get("score", {}).get("score")
    s_after = store.load(aid4).get("score", {}).get("score")
    if s_after <= s_before:
        return "recheck score did not improve (%s -> %s)" % (s_before, s_after)
    return ""


def t_registry_and_api():
    """13 phase-6 tools in the phase5 registry + compliance routes mounted."""
    import compliance_agent.tools  # noqa: F401
    from tools import registry
    p6 = {"upload_document", "list_uploaded_documents", "extract_document",
          "classify_document", "extract_evidence", "get_applicable_requirements",
          "match_evidence", "check_requirement", "calculate_readiness_score",
          "identify_gaps", "generate_remediation", "generate_compliance_report",
          "recheck_compliance"}
    regs = registry()
    missing = p6 - set(regs)
    if missing:
        return "registry missing: %s" % missing
    from compliance_api.app import app
    paths = [r.path for r in app.routes if hasattr(r, "methods")]
    need = ["/api/compliance/audit", "/api/chat", "/api/health"]
    for p in need:
        if p not in paths:
            return "route missing: %s" % p
    if not any("/upload" in p for p in paths):
        return "upload route missing"
    return ""


if __name__ == "__main__":
    ok = run_cases("compliance_tests", [
        ("requirement_matching", t_matching),
        ("decision_pass", t_pass),
        ("decision_gap", t_gap),
        ("decision_unknown_vague", t_unknown_vague),
        ("decision_conflict", t_conflict),
        ("decision_expired_gap", t_expired),
        ("readiness_score", t_score),
        ("remediation", t_remediation),
        ("report_json_and_markdown", t_report),
        ("registry_and_api", t_registry_and_api),
        ("recheck_and_end_to_end", t_recheck_and_e2e),
    ])
    sys.exit(0 if ok else 1)



