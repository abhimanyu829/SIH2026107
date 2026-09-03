"""Remediation suggestions (spec section 20).

Deterministic templates from the requirement's own evidence_expected text.
One optional LLM polish per gap, capped, only when configured. Never invents
BIS procedure - the recommendation restates the missing evidence + source.
"""


def generate(results, requirements):
    """-> [{requirement_id, gap, missing_evidence, recommendation, bis_source}]"""
    req_by_id = {r["requirement_id"]: r for r in requirements}
    out = []
    for r in results:
        if r["decision"] == "PASS":
            continue
        req = req_by_id.get(r["requirement_id"], {})
        missing = req.get("evidence_expected") or "supporting document"
        rec = _template(r, req, missing)
        out.append({
            "requirement_id": r["requirement_id"],
            "gap": r["requirement"][:200],
            "decision": r["decision"],
            "missing_evidence": missing,
            "recommendation": rec,
            "bis_source": r.get("bis_source", ""),
        })
    return out


def _template(result, req, missing):
    d, rtype = result["decision"], req.get("type", "")
    if "Conflicting evidence detected" in result.get("reason", ""):
        return ("Resolve the conflicting %s values across the uploaded "
                "documents, then upload the corrected document."
                % _type_words(rtype))
    if d == "GAP":
        if rtype == "CALIBRATION":
            return ("Upload a valid calibration certificate for the testing "
                    "instrument showing instrument ID, calibration date and "
                    "validity date.")
        if rtype == "TESTING":
            return ("Upload a test report for '%s' from a BIS-recognized "
                    "laboratory showing test name, date and result."
                    % _test_name(req.get("requirement", "")))
        if rtype == "FACTORY":
            return ("Upload a factory / premises document (license, layout "
                    "plan or capacity statement) covering the manufacturing "
                    "unit for this product.")
        if rtype in ("QCO", "SCHEME"):
            return ("Upload the BIS licence / scheme enrollment documents "
                    "for this product category.")
        return ("Upload %s addressing this requirement (source: %s)."
                % (missing, req.get("source", "BIS data")))
    # UNKNOWN
    if "expired" in result.get("reason", "").lower() or "has passed" in \
            result.get("reason", ""):
        return ("Get the instrument recalibrated and upload the new "
                "certificate showing a future validity date.")
    return ("Upload clearer evidence: %s. Current documents mention the "
            "topic but lack the specific details needed to verify it."
            % missing)


def _type_words(rtype):
    return (rtype or "").lower().replace("_", " ") or "requirement"


def _test_name(requirement_text):
    import re
    m = re.search(r"test\s*'([^']+)'", requirement_text or "")
    return m.group(1) if m else "the required test"
