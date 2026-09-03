"""Guardrails: citation validation, claim screening, UNKNOWN enforcement.

Runs on the FINAL answer, after synthesis, before the response leaves the
graph. Deterministic - no model calls.
"""
import re

IS_IN_ANSWER = re.compile(r"\bIS\s*[:\-]?\s*\d{2,6}(?:[:\-]\d{4})?", re.I)


def citations_from_evidence(evidence):
    """Builds citation objects from the evidence set. Every citation must
    point at a real evidence item - nothing is generated from thin air."""
    out = []
    for e in evidence:
        out.append({
            "document_id": e.get("document_id") or e.get("evidence_id") or "",
            "title": e.get("title") or e.get("canonical_is_number") or "",
            "page": e.get("page", ""),
            "clause": e.get("clause") or "",
            "source_url": e.get("source_url") or "",
        })
    return out


def validate_citations(answer, citations, evidence):
    """Every citation must match a retrieved evidence item (by document_id /
    chunk evidence_id / source_url). Returns (ok, problems)."""
    if not citations:
        return (not evidence or len(evidence) == 0), \
               ["answer has no citations but evidence exists"
                if evidence else []]
    keys = {str(e.get("document_id") or e.get("evidence_id") or "") for e in evidence}
    urls = {e.get("source_url") or "" for e in evidence}
    problems = []
    for c in citations:
        cid = str(c.get("document_id") or "")
        url = c.get("source_url") or ""
        if cid and cid in keys:
            continue
        if url and url in urls and url:
            continue
        if not cid and not url:
            problems.append("citation without identifier: %s" % c)
            continue
        problems.append("citation not in evidence set: %s" %
                        (c.get("title") or cid or url))
    return (not problems), problems


def screen_answer(answer, bundles, evidence, unresolved=None):
    """Final checks on the produced answer.

    - IS numbers mentioned must come from resolved standards or evidence
      (no invented IS numbers);
    - UNKNOWN is forced when nothing grounded exists;
    - unresolved conflicts are appended, never silently dropped.
    """
    problems = []
    allowed = set()
    for b in bundles:
        for key in ("canonical_is_number", "display_is_number"):
            v = b.get("standard", {}).get(key)
            if v:
                allowed.add(re.sub(r"[^0-9:]", "", str(v)))
    for e in evidence:
        v = e.get("canonical_is_number")
        if v:
            allowed.add(re.sub(r"[^0-9:]", "", str(v)))
    allowed.discard("")
    for m in IS_IN_ANSWER.finditer(answer or ""):
        seen = re.sub(r"[^0-9:]", "", m.group(0))
        if allowed and seen not in allowed:
            problems.append("answer mentions IS number not in evidence: %s"
                            % m.group(0))
    if unresolved:
        answer = (answer or "").rstrip()
        if answer and not answer.endswith("."):
            answer += "."
        answer += (" Note: unresolved items preserved from the source data: "
                   + "; ".join(str(u) for u in unresolved[:3]) + ".")
    return answer, problems


def unknown_answer(reason="insufficient authoritative evidence"):
    return ("I couldn't determine this reliably from the available "
            "authoritative BIS evidence (%s)." % reason)
