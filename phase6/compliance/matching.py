"""Requirement <-> evidence matching (spec sections 12-17).

Match order (deterministic first, LLM last):
  1. document category vs requirement type
  2. keyword / field overlap
  3. structured value checks (dates, results)
  4. semantic fallback (Qdrant BIS chunks are NOT used for user evidence -
     matching stays local so user documents never enter BIS knowledge)
  5. LLM interpretation only for ambiguous cases
"""
import re

# requirement type -> document categories that can evidence it
TYPE_TO_CATEGORIES = {
    "CALIBRATION": ["CALIBRATION_CERTIFICATE"],
    "TESTING": ["TEST_REPORT", "QC_DOCUMENT"],
    "LAB": ["TEST_REPORT"],
    "FACTORY": ["FACTORY_DOCUMENT", "MACHINERY_DOCUMENT", "PROCESS_DOCUMENT"],
    "SCHEME": ["FACTORY_DOCUMENT", "QC_DOCUMENT", "OTHER", "TEST_REPORT"],
    "QCO": ["FACTORY_DOCUMENT", "TEST_REPORT", "OTHER"],
    "MANUAL": ["PROCESS_DOCUMENT", "QC_DOCUMENT", "FACTORY_DOCUMENT", "OTHER"],
}

STOP = {"must", "shall", "be", "the", "a", "an", "and", "or", "of", "for",
        "to", "with", "in", "on", "at", "as", "per", "is", "are", "records",
        "record", "document", "documents", "performed", "hold", "valid"}


def _tokens(text):
    return {t for t in re.findall(r"[a-z]{3,}", (text or "").lower())
            if t not in STOP}


def match_requirement(requirement, evidence):
    """(candidates, matched) for one requirement against all evidence.

    candidates: evidence items plausible for this requirement (stage 1+2),
    matched: items that actually support it (stage 3 checks).
    """
    rtype = requirement.get("type", "MANUAL")
    allowed = TYPE_TO_CATEGORIES.get(rtype, list(TYPE_TO_CATEGORIES.values())[0])
    rtext = requirement.get("requirement", "")
    rtokens = _tokens(rtext)
    expected = (requirement.get("evidence_expected") or "").lower()

    candidates, matched = [], []
    for e in evidence:
        if e.get("type") not in allowed and e.get("type") != "OTHER":
            # category mismatch, but keyword fields can still bridge
            if not (rtokens & _tokens(e.get("field", ""))):
                continue
        candidates.append(e)
        score = _support_score(requirement, e, rtokens, expected)
        if score >= 0.5:
            matched.append((e, score))
    matched.sort(key=lambda x: -x[1])
    return candidates, matched


def _support_score(requirement, e, rtokens, expected):
    """Stage 2+3: how strongly one evidence item supports the requirement."""
    score = 0.0
    field = e.get("field", "")
    value = (e.get("value") or "").strip()
    text = (e.get("text") or "").lower()

    # field-level hints
    rtype = requirement.get("type")
    if rtype == "CALIBRATION" and field in ("instrument_id", "certificate_number",
                                            "calibration_date", "validity_date",
                                            "laboratory_name"):
        score += 0.4
    if rtype == "TESTING" and field in ("test_name", "test_date", "result",
                                        "product_model", "laboratory_name"):
        score += 0.4
    if rtype == "FACTORY" and field in ("factory_name", "address", "capacity",
                                        "machinery", "gst_number"):
        score += 0.4

    # expected-evidence overlap
    etok = _tokens(expected) | rtokens
    if etok & _tokens(text):
        score += 0.25
    if etok & _tokens(field):
        score += 0.2

    # structured value present and non-trivial
    if value and len(value) >= 2:
        score += 0.15

    # test result actually says pass/conform
    if field == "result" and value.lower() in ("pass", "passed", "conforms",
                                               "conforming", "conform", "ok"):
        score += 0.25
    return min(score, 1.0)


def check_conflicts(matched, field):
    """Two matched values for the same field that clearly disagree.

    Spec section 17: never pick randomly - conflict => UNKNOWN.
    """
    values = []
    for e, _ in matched:
        if e.get("field") == field:
            values.append((e.get("value", "").strip().lower(), e))
    if len(values) < 2:
        return None
    a, b = values[0], values[1]
    da, db = _digits(a[0]), _digits(b[0])
    if da and db and da != db:
        return {"field": field, "value_a": a[0], "value_b": b[0],
                "evidence_a": a[1].get("evidence_id"),
                "evidence_b": b[1].get("evidence_id"),
                "note": "Conflicting evidence detected."}
    if a[0] and b[0] and a[0] != b[0] and field in ("result",):
        return {"field": field, "value_a": a[0], "value_b": b[0],
                "evidence_a": a[1].get("evidence_id"),
                "evidence_b": b[1].get("evidence_id"),
                "note": "Conflicting evidence detected."}
    return None


def _digits(s):
    return "".join(ch for ch in str(s) if ch.isdigit())


def validity_expired(evidence):
    """Calibration validity date already in the past => requirement NOT met."""
    import datetime
    for e in evidence:
        if e.get("field") == "validity_date":
            v = str(e.get("value") or "")
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
                        "%d/%m/%y", "%m/%d/%Y"):
                try:
                    d = datetime.datetime.strptime(v, fmt)
                    if d.date() < datetime.date.today():
                        return e
                except ValueError:
                    continue
    return None
