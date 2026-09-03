"""Decision engine: every requirement -> PASS / GAP / UNKNOWN (spec 13-17).

Deterministic order, LLM only for ambiguous interpretation:
  - no candidate evidence at all              -> GAP
  - candidates exist but no real support     -> UNKNOWN (thin/ambiguous)
  - matched support with sufficient detail   -> PASS
  - conflicting values                       -> UNKNOWN
  - calibration validity expired             -> GAP
  - vague mention without detail fields      -> UNKNOWN (never promoted)
"""
from . import matching


def decide(requirement, evidence):
    """One requirement -> decision dict with reason + evidence refs."""
    rtype = requirement.get("type", "")
    candidates, matched = matching.match_requirement(requirement, evidence)

    # stage 1: nothing uploaded that could evidence this requirement
    if not candidates:
        return _result(requirement, "GAP",
                       "No %s evidence was found. Required evidence: %s."
                       % (rtype.lower().replace("_", " "),
                          requirement.get("evidence_expected") or
                          "supporting document"),
                       [], conflicts=[])

    # conflict scan on the matched set (spec 17)
    conflict = None
    for field in ("validity_date", "calibration_date", "result", "test_date"):
        conflict = matching.check_conflicts(matched, field)
        if conflict:
            break
    if conflict:
        return _result(requirement, "UNKNOWN",
                       "Conflicting evidence detected for '%s' (%s vs %s)."
                       % (conflict["field"], conflict["value_a"],
                          conflict["value_b"]),
                       [e for e, _ in matched][:4], conflicts=[conflict])

    # calibration expiry is a hard GAP (spec: evidence exists but not valid)
    if rtype == "CALIBRATION":
        expired = matching.validity_expired([e for e, _ in matched])
        if expired:
            return _result(requirement, "GAP",
                           "Calibration evidence found but validity date "
                           "(%s) has passed." % expired.get("value"),
                           [expired])

    # stage 2/3: matched support with enough detail -> PASS
    if matched:
        best = matched[0]
        detail_ok = _sufficient_detail(best[0], rtype)
        if detail_ok and best[1] >= 0.5:
            refs = [e for e, _ in matched[:4]]
            return _result(requirement, "PASS",
                           "Sufficient %s evidence was found (%s)."
                           % (rtype.lower().replace("_", " "),
                              ", ".join(sorted({e["field"] for e in refs})[:3])),
                           refs)
        if not detail_ok:
            # present but thin -> UNKNOWN (spec 15 example, never PASS)
            return _result(requirement, "UNKNOWN",
                           "Evidence mentions the topic but does not provide "
                           "enough detail to verify the requirement "
                           "(%s)."
                           % (requirement.get("evidence_expected") or "insufficient detail"),
                           [e for e, _ in matched[:3]])

    # candidates exist, nothing matched: ambiguous -> one LLM interpretation
    llm = _llm_interpret(requirement, candidates)
    if llm == "PASS":
        return _result(requirement, "PASS",
                       "Evidence supports the requirement after interpretation "
                       "(%s)." % ", ".join(c["document"] for c in candidates[:2]),
                       [c for c in candidates[:3]])
    if llm == "GAP":
        return _result(requirement, "GAP",
                       "Available evidence does not satisfy the requirement: %s."
                       % (requirement.get("evidence_expected") or ""),
                       [c for c in candidates[:2]])
    return _result(requirement, "UNKNOWN",
                   "Insufficient evidence. Documents exist but do not clearly "
                   "address the requirement.",
                   [c for c in candidates[:3]])


def _sufficient_detail(e, rtype):
    """Vague mentions are never PASS (spec 15)."""
    value = (e.get("value") or "").strip()
    if not value:
        return False
    if rtype == "CALIBRATION" and e.get("field") in ("instrument_id",
                                                     "certificate_number",
                                                     "calibration_date",
                                                     "validity_date"):
        return True
    if rtype in ("TESTING", "LAB") and e.get("field") in ("test_name", "result",
                                                          "test_date",
                                                          "laboratory_name",
                                                          "product_model"):
        return True
    if rtype in ("FACTORY", "QCO", "SCHEME", "MANUAL", "PROCESS_DOCUMENT"):
        return len(value) >= 3
    return len(value) >= 2


def _llm_interpret(requirement, candidates):
    """One bounded LLM call for a genuinely ambiguous case. Returns
    PASS/GAP/UNKNOWN or '' when unavailable. The LLM only judges whether the
    quoted evidence addresses the requirement - it never sees or creates BIS
    data."""
    import config as cfg
    if not cfg.llm_configured():
        return ""
    lines = [("%s [%s] = %s (page %s)"
              % (c.get("field"), c.get("type"), (c.get("value") or "")[:80],
                 c.get("page"))) for c in candidates[:6]]
    prompt = ("Requirement: %s\n\nAvailable evidence:\n%s\n\n"
              "Does the evidence satisfy the requirement? Reply with exactly "
              "one word: PASS, GAP, or UNKNOWN. PASS only if evidence clearly "
              "shows the requirement is satisfied; GAP only if evidence "
              "clearly shows it is not; else UNKNOWN."
              % (requirement.get("requirement", ""), "\n".join(lines)))
    out = cfg.llm_complete_cached("You are a strict compliance pre-auditor. "
                                  "Never guess. Never invent data.",
                                  prompt, max_tokens=6)
    if not out:
        return ""
    word = out.strip().upper().split()[0] if out.strip() else ""
    return word if word in ("PASS", "GAP", "UNKNOWN") else ""


def _result(requirement, decision, reason, evidence_refs, conflicts=None):
    refs = [{"evidence_id": e.get("evidence_id"),
             "document": e.get("document"),
             "field": e.get("field"),
             "value": (e.get("value") or "")[:120],
             "page": e.get("page")} for e in evidence_refs[:4]]
    return {
        "requirement_id": requirement["requirement_id"],
        "requirement": requirement.get("requirement", ""),
        "type": requirement.get("type", ""),
        "decision": decision,
        "reason": reason,
        "evidence_refs": refs,
        "bis_source": "%s%s" % (requirement.get("source", ""),
                                (" clause " + requirement["clause"])
                                if requirement.get("clause") else ""),
        "clause": requirement.get("clause", ""),
        "conflicts": conflicts or [],
    }
