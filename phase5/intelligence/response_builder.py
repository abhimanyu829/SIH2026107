"""Response building: deterministic evidence-grounded answers (always) with
optional LLM polish. The deterministic path is the backbone - the prototype
answers correctly with zero LLM cost; a configured LLM only rewords the same
grounded facts, never adds any.
"""
import json


def _fmt_std(std):
    return "%s (%s)" % (std.get("canonical_is_number"),
                        std.get("display_is_number") or std.get("title") or "")


def deterministic_answer(task, entities, bundles, evidence, extra=None):
    """Builds the grounded answer text from structured rows + evidence.

    UNKNOWN path: no bundles AND no evidence -> explicit low-confidence answer.
    """
    extra = extra or {}
    lines = []
    if not bundles and not evidence:
        return ("I couldn't determine this reliably from the available "
                "authoritative BIS evidence.", "UNKNOWN")

    # verification tasks: state the verify tool's own verdict - a nearby
    # bundle never counts as a verification success
    if task == "VERIFICATION":
        v = (extra or {}).get("verdict") or "NOT_VERIFIED"
        if v == "VALIDATED":
            lines.append("Verification result: VALIDATED - the identifier "
                         "matches an authoritative BIS record cited in the "
                         "evidence below.")
        elif v == "CONTEXT_MISMATCH":
            lines.append("Verification result: CONTEXT_MISMATCH / NOT_VERIFIED "
                         "- the identifier resolves but does not match the "
                         "stated product context; it could not be verified.")
        else:
            lines.append("Verification result: NOT_FOUND / NOT_VERIFIED / "
                         "UNKNOWN - the requested identifier is not "
                         "established in the available BIS records; it "
                         "could not be verified.")

    if bundles:
        b = bundles[0]
        std = b["standard"]
        head = "%s: %s" % (std.get("canonical_is_number") or "?",
                           std.get("title") or "title not established in source data")
        if task in ("SIMPLE_LOOKUP", "STANDARD_DISCOVERY", "GENERAL_BIS",
                    "CERTIFICATION_GUIDANCE"):
            lines.append("Applicable Indian Standard: %s." % head)
        else:
            lines.append("Resolving against %s." % head)
        if b["products"]:
            lines.append("Products: %s." % "; ".join(
                p.get("product_name") or "" for p in b["products"][:3]))
        if task in ("QCO_LOOKUP", "COMPLIANCE_WORKFLOW",
                    "CERTIFICATION_GUIDANCE") or b["qcos"]:
            if b["qcos"]:
                lines.append("Quality Control Orders: %s." % "; ".join(
                    "%s %s%s" % (q.get("qco_number") or "?", q.get("qco_name") or "",
                                 (" (effective %s)" % q.get("effective_date"))
                                 if q.get("effective_date") else "")
                    for q in b["qcos"][:3]))
                lines.append("Certification is mandatory under these QCOs as "
                             "recorded; verify current status at the BIS "
                             "portal linked in sources.")
            elif task in ("QCO_LOOKUP", "COMPLIANCE_WORKFLOW"):
                lines.append("No QCO linkage is established for this standard "
                             "in the available data - mandatory status UNKNOWN.")
        if task in ("SCHEME_LOOKUP", "COMPLIANCE_WORKFLOW") or b["schemes"]:
            if b["schemes"]:
                lines.append("Certification schemes: %s." % "; ".join(
                    "%s %s" % (s.get("scheme_code") or "", s.get("scheme_name") or "")
                    for s in b["schemes"][:3]))
        if b["manuals"] or task in ("DOCUMENT_RESEARCH", "COMPLIANCE_WORKFLOW"):
            if b["manuals"]:
                lines.append("Product Manual: %s (version %s)." % (
                    b["manuals"][0].get("manual_title") or "untitled",
                    b["manuals"][0].get("manual_version") or "not stated"))
        if b["tests"] or task == "TEST_LOOKUP":
            if b["tests"]:
                lines.append("Required tests (%d recorded): %s." % (
                    len(b["tests"]), "; ".join(
                        t.get("test_name") or "" for t in b["tests"][:8])))
            elif task == "TEST_LOOKUP":
                lines.append("No test requirements are established for this "
                             "standard in the available data (UNKNOWN).")
        if b["labs"] or task == "LAB_LOOKUP":
            if b["labs"]:
                lines.append("Recognized laboratories (%d found; first %d): %s." % (
                    len(b["labs"]), min(3, len(b["labs"])),
                    "; ".join("%s (%s, %s)" % (l.get("lab_name") or "?",
                                               l.get("city") or "?",
                                               l.get("state") or "?")
                              for l in b["labs"][:3])))
            elif task == "LAB_LOOKUP":
                lines.append("No recognized laboratories are established for "
                             "this standard in the available data (UNKNOWN).")
    else:
        lines.append("Answered from BIS evidence chunks (no structured record "
                     "resolved for this query).")

    for k, v in (extra or {}).items():
        lines.append(v)

    if evidence:
        lines.append("Supporting evidence: %d cited chunk(s), best match "
                     "'%s' (score %.2f)." % (
                         len(evidence), (evidence[0].get("title") or "-")[:60],
                         evidence[0].get("relevance_score", 0)))
    status = "COMPLETED"
    return (" ".join(lines), status)


def evidence_prompt(user_query, bundles, evidence, task):
    """Compact, capped context for the LLM - no raw DB dumps (spec)."""
    parts = ["Task: %s" % task, "Question: %s" % user_query, ""]
    for b in bundles[:2]:
        std = b["standard"]
        parts.append("STANDARD: %s | %s | status=%s"
                     % (std.get("canonical_is_number"), std.get("title"),
                        std.get("status")))
        if b["qcos"]:
            parts.append("QCO: " + "; ".join(
                "%s %s" % (q.get("qco_number"), q.get("qco_name") or "")
                for q in b["qcos"][:3]))
        if b["schemes"]:
            parts.append("SCHEME: " + "; ".join(
                "%s %s" % (s.get("scheme_code"), s.get("scheme_name") or "")
                for s in b["schemes"][:3]))
        if b["tests"]:
            parts.append("TESTS (%d): %s" % (len(b["tests"]), "; ".join(
                t.get("test_name") or "" for t in b["tests"][:10])))
        if b["labs"]:
            parts.append("LABS (%d, first 3): %s" % (len(b["labs"]), "; ".join(
                l.get("lab_name") or "" for l in b["labs"][:3])))
        if b["manuals"]:
            parts.append("MANUAL: %s" % (b["manuals"][0].get("manual_title") or ""))
    for e in evidence[:6]:
        parts.append("EVIDENCE [%s] %s | clause=%s | score=%.2f: %s"
                     % (e.get("document_type") or "-", e.get("title") or "-",
                        e.get("clause") or "-", e.get("relevance_score", 0),
                        (e.get("content") or "")[:220]))
    parts.append("")
    parts.append("Write a short factual answer using ONLY the data above. Do "
                 "not invent IS numbers, dates, statuses, tests or labs. Say "
                 "UNKNOWN for anything not established above.")
    return "\n".join(parts)


def llm_available():
    import config as cfg
    return cfg.llm_configured()


def llm_complete(system, prompt, max_tokens=600):
    """One LLM call through langchain-core (OpenAI-compatible). Any failure
    returns None and the deterministic answer stands.

    max_tokens floors at 512: the configured endpoint (glm-5.3-flash) is a
    reasoning model that spends most of the budget on hidden reasoning tokens
    before any visible text - small caps return EMPTY content with
    finish_reason=length, which callers would treat as 'no answer'."""
    try:
        import config as cfg
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(model=cfg.LLM_MODEL, temperature=cfg.LLM_TEMPERATURE,
                         max_tokens=max(512, int(max_tokens or 512)),
                         api_key=cfg.get("LLM_API_KEY") or
                                 cfg.get("OPENAI_API_KEY"),
                         base_url=cfg.LLM_BASE_URL, timeout=90)
        out = llm.invoke([SystemMessage(content=system), HumanMessage(content=prompt)])
        text = (out.content or "").strip()
        return text or None
    except Exception:
        return None
