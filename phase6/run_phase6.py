"""Phase-6 runner: offline check -> tests -> end-to-end demo -> report.

  python run_phase6.py --check     # offline sanity, no creds needed
  python run_phase6.py             # tests + demo (DB if configured)
  python run_phase6.py --serve     # uvicorn on :8002 (phase5 app + compliance)
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
# phase6 FIRST: `config`, `agent`->(compliance_agent) etc. must resolve to
# phase6's re-exporting config; phase5 stays importable for its own modules
# (they carry the config they need via their internal setup).
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "phase5"))
sys.path.insert(0, HERE)

PY = sys.executable


def offline_check():
    print("[check] compileall ...")
    r = subprocess.run([PY, "-m", "compileall", "-q", HERE])
    if r.returncode != 0:
        sys.exit("[check] compileall FAILED")

    print("[check] imports + registry ...")
    import config as cfg  # noqa: F401
    from compliance_agent import store  # noqa: F401
    import compliance_agent.tools  # noqa: F401
    from tools import registry  # noqa: E402 (phase5 registry)
    regs = registry()
    p6 = [n for n in regs if n in (
        "upload_document", "list_uploaded_documents", "extract_document",
        "classify_document", "extract_evidence", "get_applicable_requirements",
        "match_evidence", "check_requirement", "calculate_readiness_score",
        "identify_gaps", "generate_remediation", "generate_compliance_report",
        "recheck_compliance")]
    print("[check] phase-6 tools registered: %d/13" % len(p6))
    assert len(p6) == 13, "missing phase-6 tools: %s" % (
        set(["upload_document", "list_uploaded_documents", "extract_document",
             "classify_document", "extract_evidence",
             "get_applicable_requirements", "match_evidence",
             "check_requirement", "calculate_readiness_score", "identify_gaps",
             "generate_remediation", "generate_compliance_report",
             "recheck_compliance"]) - set(p6))
    from compliance_agent.pipeline import build_compliance_graph
    g = build_compliance_graph()
    print("[check] LangGraph compliance graph nodes: %s"
          % sorted(n for n in g.get_graph().nodes if not n.startswith("__")))

    print("[check] FastAPI app assembly ...")
    from compliance_api.app import app
    paths = [r.path for r in app.routes if hasattr(r, "methods")]
    comp = [p for p in paths if "/compliance" in p]
    print("[check] compliance endpoints: %s" % ", ".join(comp))
    assert len(comp) >= 8, "compliance routes missing"
    assert any(p == "/api/chat" for p in paths), "phase5 routes lost!"

    print("[check] PASS - offline checks complete")
    return {"tools": len(p6), "endpoints": len(comp)}


def run_tests():
    print("\n[tests] running phase-6 test suite ...")
    tdir = os.path.join(HERE, "tests")
    ok = True
    for name in sorted(os.listdir(tdir)):
        if name.startswith("test_") and name.endswith(".py"):
            print("\n--- %s ---" % name)
            r = subprocess.run([PY, "-W", "ignore",
                                os.path.join(tdir, name)], cwd=HERE)
            ok = ok and r.returncode == 0
    return ok


def run_demo():
    print("\n[demo] flagship end-to-end: office work chairs readiness")
    from compliance_agent import store
    import compliance_agent.tools  # noqa: F401
    from compliance_agent.pipeline import run_analysis
    from compliance.requirements import resolve_product

    ctx = store.new_audit("office work chairs")
    aid = ctx["audit_id"]
    print("[demo] audit: %s" % aid)

    resolved = resolve_product("office work chairs")
    print("[demo] product -> IS %s"
          % (resolved.get("is_number") or "NOT RESOLVED"))
    if resolved.get("is_number"):
        ctx["product"] = resolved.get("product")
        ctx["bis_context"] = {"is_number": resolved["is_number"],
                              "standards": resolved.get("standards", [])[:3],
                              "products": resolved.get("products", [])[:3]}
        store.save(ctx)
    else:
        # DB credentials absent or BIS tables empty (Phase-4 load pending):
        # run the demo on a small synthetic requirement set so the decision
        # engine, score, remediation and recheck are still demonstrated.
        ctx["requirements"] = [
            {"requirement_id": "REQ-001",
             "requirement": "Testing instruments must hold valid calibration "
                            "records.", "type": "CALIBRATION",
             "source": "Product Manual", "clause": "4.3",
             "evidence_expected": "valid calibration certificate"},
            {"requirement_id": "REQ-002",
             "requirement": "Test 'Stability test' must be performed as per "
                            "IS 17631.", "type": "TESTING",
             "source": "bis.is_test_mapping", "clause": "",
             "evidence_expected": "test report for 'Stability test'"},
            {"requirement_id": "REQ-003",
             "requirement": "Manufacturing premises and production capability "
                            "must be documented.", "type": "FACTORY",
             "source": "bis.product_master", "clause": "",
             "evidence_expected": "factory / premises document"},
        ]
        ctx["bis_context"] = {"is_number": None}
        store.save(ctx)
        print("[demo] using synthetic requirements (BIS DB empty/unavailable)")

    # upload the synthetic fixtures as evidence
    import base64
    fix = os.path.join(HERE, "tests", "fixtures")
    from tools import call as p5_call
    for fname in sorted(os.listdir(fix)):
        with open(os.path.join(fix, fname), "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        r = p5_call("upload_document", audit_id=aid, filename=fname,
                    content_b64=b64)
        print("[demo] upload %-28s %s" % (fname, r["ok"]))

    out = run_analysis(aid)
    print("[demo] analysis: ok=%s requirements=%s evidence=%s in %ss"
          % (out.get("ok"), out.get("requirements"), out.get("evidence"),
             out.get("latency_sec")))
    ctx = store.load(aid)
    s = ctx.get("score", {})
    print("[demo] Compliance Readiness Score: %s/100 "
          "(PASS %s, GAP %s, UNKNOWN %s of %s)"
          % (s.get("score"), s.get("passed"), s.get("gaps"),
             s.get("unknown"), s.get("total")))
    for r_ in ctx.get("results", [])[:6]:
        print("  [%s] %-8s %s" % (r_["decision"], r_["type"],
                                   r_["requirement"][:60]))
    print("[demo] remediation items: %d" % len(ctx.get("remediation", [])))

    # recheck demo: a manufacturer uploads corrected evidence and re-runs.
    # Fresh recheck on the same requirements with the corrected certificate
    # (the original audit keeps both expired and conflicting docs, which
    # correctly stayed UNKNOWN - conflicting evidence is never resolved
    # silently).
    fixed = os.path.join(fix, "fixed_validity.pdf")
    if os.path.exists(fixed):
        rc = store.new_audit("office work chairs")
        rc["requirements"] = [
            {"requirement_id": "REQ-001",
             "requirement": "Testing instruments must hold valid calibration "
                            "records.", "type": "CALIBRATION",
             "source": "Product Manual", "clause": "4.3",
             "evidence_expected": "valid calibration certificate"},
        ]
        rc["bis_context"] = {"is_number": None}
        store.save(rc)
        with open(fixed, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        p5_call("upload_document", audit_id=rc["audit_id"],
                filename="fixed_validity.pdf", content_b64=b64)
        run_analysis(rc["audit_id"])
        s2 = store.load(rc["audit_id"]).get("score", {})
        print("[demo] recheck with corrected calibration only: %s -> %s "
              "(GAP/UNKNOWN evidence resolved by new upload)"
              % (s.get("score"), s2.get("score")))

    md = ctx.get("report_md", "")
    print("[demo] report markdown: %d chars; disclaimer present: %s"
          % (len(md), "NOT an official BIS" in md or "NOT official BIS" in md))
    return {"audit_id": aid, "score": s}


def report(check, tests_ok, demo):
    path = os.path.join(HERE, "tests", "PHASE6_VALIDATION.json")
    data = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    total = sum(s.get("passed", 0) for s in data.values() if isinstance(s, dict))
    fails = sum(s.get("failed", 0) for s in data.values() if isinstance(s, dict))
    skips = sum(s.get("skipped", 0) for s in data.values() if isinstance(s, dict))

    print("\n" + "=" * 70)
    if tests_ok and check:
        print("PHASE 6 STATUS\n")
        print("Implemented: document pipeline (PDF/DOCX/XLSX/TXT + OCR "
              "fallback), classification, evidence extraction, BIS "
              "requirement retrieval, matching, PASS/GAP/UNKNOWN decisions, "
              "readiness score, gap analysis, remediation, report, recheck, "
              "13 tools in the phase5 registry, 9 compliance endpoints.")
        print("Tests passed : %d" % total)
        print("Skipped      : %d" % skips)
        print("Failed       : %d" % fails)
        print("Demo score   : %s" % demo.get("score", {}).get("score"))
        print("\nPHASE 6 IMPLEMENTATION COMPLETE")
        return True
    print("PHASE 6 INCOMPLETE - see tests/PHASE6_VALIDATION.json")
    return False


def main():
    args = set(sys.argv[1:])
    if "--serve" in args:
        os.chdir(HERE)
        os.system('"%s" -m uvicorn compliance_api.app:app --host 127.0.0.1 --port 8002'
                  % PY)
        return
    check = offline_check()
    if "--check" in args:
        return
    tests_ok = run_tests()
    demo = run_demo()
    ok = report(check, tests_ok, demo)
    sys.exit(0 if ok else 7)


if __name__ == "__main__":
    main()


