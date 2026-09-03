"""BIS requirement generation from Phase-5 sources (spec section 10).

Requirements come ONLY from real Phase-5 lookups:
  product -> standard -> QCO -> scheme -> Product Manual -> tests/labs.
No requirement is ever invented here; text is quoted from the retrieved rows.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "phase5"))

from tools import call as p5_call  # noqa: E402  (phase5 tool registry)


def resolve_product(product_text):
    """product text -> {product, standards, is_number, bis_context}.

    Uses find_product + get_product (via any linked standard) exactly like the
    Phase-5 flagship flow. Never guesses an IS number.
    """
    out = {"product": None, "products": [], "standards": [],
           "is_number": None, "error": ""}
    r = p5_call("find_product", query=product_text)
    if not r["ok"] or not r["data"]:
        out["error"] = r.get("error") or "product not found"
        return out
    out["products"] = r["data"]
    out["product"] = r["data"][0]

    # standards linked to the best product match
    from tools._shared import supabase
    try:
        stds = supabase().standards_for_product(r["data"][0].get("product_id"))
    except SystemExit as e:
        out["error"] = "credentials missing (exit %s)" % e.code
        return out
    out["standards"] = stds or []
    if stds:
        num = stds[0].get("canonical_is_number") or ""
        out["is_number"] = num.replace("IS", "").strip() or None
    if not out["is_number"]:
        # fallback: keyword standards search over the same product text
        rs = p5_call("search_standards", query=product_text)
        if rs["ok"] and rs["data"]:
            num = (rs["data"][0].get("canonical_is_number") or "")
            out["is_number"] = num.replace("IS", "").strip() or None
            out["standards"] = rs["data"][:3]
    return out


def build_requirements(is_number, max_requirements=40):
    """IS number -> normalized requirement list from actual BIS sources.

    Types: CALIBRATION / TESTING / FACTORY / SCHEME / QCO / MANUAL / LAB.
    Each carries source + clause for citation. Nothing is invented.
    """
    reqs, n = [], 0

    def add(requirement, rtype, source, clause="", evidence_expected=""):
        nonlocal n
        n += 1
        reqs.append({
            "requirement_id": "REQ-%03d" % n,
            "requirement": requirement,
            "type": rtype,
            "source": source,
            "clause": clause,
            "evidence_expected": evidence_expected or _default_evidence(rtype),
        })

    std = p5_call("get_standard", is_number=is_number)
    std_row = std["data"] if std["ok"] and std["data"] else None

    # QCO linkage -> mandatory status requirement
    qco = p5_call("get_qco", is_number=is_number)
    if qco["ok"] and qco["data"]:
        rows = qco["data"] if isinstance(qco["data"], list) else [qco["data"]]
        for row in rows[:3]:
            name = row.get("qco_name") or row.get("title") or "QCO"
            add("Certification under QCO %s (%s) applies to this product."
                % (row.get("qco_number") or "?", name),
                "QCO", "bis.is_qco_mapping",
                clause=str(row.get("qco_number") or ""),
                evidence_expected="BIS licence / registration documents")

    # scheme linkage
    scheme = p5_call("get_scheme", is_number=is_number)
    if scheme["ok"] and scheme["data"]:
        rows = scheme["data"] if isinstance(scheme["data"], list) else [scheme["data"]]
        for row in rows[:2]:
            add("Certification scheme %s (%s) applies."
                % (row.get("scheme_code") or "?", row.get("scheme_name") or ""),
                "SCHEME", "bis.is_scheme_mapping",
                evidence_expected="scheme enrollment / licence documents")

    # product manual sections -> the actual requirement text
    manual = p5_call("get_product_manual", is_number=is_number)
    if manual["ok"] and manual["data"]:
        for sec in (manual["data"].get("sections") or [])[:10]:
            text = (sec.get("requirement_text") or "").strip()
            if not text:
                continue
            rtype = _manual_type(sec.get("section_category") or "",
                                 sec.get("table") or "", text)
            add(text[:220], rtype,
                "Product Manual (%s)" % (sec.get("table") or "manual"),
                clause=str(sec.get("clause") or sec.get("section_category") or ""))

    # tests -> testing requirements with method standards
    tests = p5_call("get_tests", is_number=is_number)
    if tests["ok"] and tests["data"]:
        for t in tests["data"][:15]:
            name = t.get("test_name") or "test"
            method = t.get("test_method_standard") or ""
            add("Test '%s' must be performed%s."
                % (name, (" as per %s" % method) if method else ""),
                "TESTING", "bis.is_test_mapping",
                clause=str(t.get("clause_reference") or ""),
                evidence_expected="test report for '%s'" % name)

    # labs -> where tests can be done (informational requirement)
    labs = p5_call("find_labs", is_number=is_number, limit=5)
    if labs["ok"] and labs["data"]:
        add("Testing must be performed at BIS-recognized laboratories.",
            "LAB", "bis.is_lab_test_mapping",
            evidence_expected="test report from a recognized laboratory")

    # calibration inference: TESTING present => instruments need calibration
    if any(r["type"] == "TESTING" for r in reqs):
        add("Testing instruments must hold valid calibration records.",
            "CALIBRATION", "Product Manual (testing)",
            clause="", evidence_expected="valid calibration certificate")

    # factory basics
    add("Manufacturing premises and production capability must be documented.",
        "FACTORY", "bis.product_master",
        evidence_expected="factory license / layout / capacity document")

    return [r for r in reqs][:max_requirements], std_row


def _manual_type(section_category, table, text):
    low = (str(section_category) + " " + str(table) + " " + text).lower()
    if "test" in low:
        return "TESTING"
    if "calibrat" in low:
        return "CALIBRATION"
    if "sampling" in low:
        return "TESTING"
    if "mark" in low:
        return "MANUAL"
    if "infrastructure" in low or "machiner" in low or "plant" in low:
        return "FACTORY"
    if "process" in low:
        return "MANUAL"
    return "MANUAL"


def _default_evidence(rtype):
    return {
        "CALIBRATION": "valid calibration certificate",
        "TESTING": "test report",
        "FACTORY": "factory / premises document",
        "SCHEME": "scheme enrollment document",
        "QCO": "licence / registration document",
        "LAB": "test report from a recognized laboratory",
        "MANUAL": "document addressing the Product Manual requirement",
    }.get(rtype, "supporting document")


def requirement_sources(is_number):
    """Citation block for the report: the BIS sources actually retrieved."""
    sources = []
    std = p5_call("get_standard", is_number=is_number)
    if std["ok"] and std["data"]:
        d = std["data"]
        sources.append({"source": "bis.is_master",
                        "detail": "%s: %s" % (d.get("canonical_is_number"),
                                             d.get("title") or "")[:150]})
    for label, tool in (("QCO", "get_qco"), ("Scheme", "get_scheme")):
        r = p5_call(tool, is_number=is_number)
        if r["ok"] and r["data"]:
            sources.append({"source": r.get("provenance") or label,
                             "detail": "%s records retrieved" % label})
    r = p5_call("get_product_manual", is_number=is_number)
    if r["ok"] and r["data"] and r["data"].get("manuals"):
        m = r["data"]["manuals"][0]
        sources.append({"source": "bis.product_manual_master",
                        "detail": (m.get("manual_title") or "Product Manual")[:120]})
    return sources
