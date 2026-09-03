"""Lightweight deterministic reranking. Spec priority:

1. exact IS/product match      3. semantic relevance (Qdrant score)
2. document relevance (type)   4. clause relevance
5. current/effective info      6. source authority (official URLs)

Rules + weights, no ML reranker, no extra model calls. Scores stay comparable
because every signal is a small bounded bonus over the semantic base score.
"""

# Document types the compliance path treats as primary evidence.
TYPE_WEIGHT = {
    "IS_STANDARD": 0.30, "PRODUCT_MANUAL": 0.25, "QCO": 0.22,
    "SCHEME": 0.18, "TEST_METHOD": 0.18, "LABORATORY": 0.10,
    "FAQ": 0.08, "LEGAL": 0.15, "NOTIFICATION": 0.15, "DOCUMENT": 0.12,
    "OFFICIAL_DOCUMENT": 0.12, "OFFICIAL_WEBPAGE": 0.05,
    "OFFICIAL_DATABASE": 0.03, "PRODUCT": 0.08, "HALLMARKING_CENTRE": 0.05,
    "FMCS_LICENCE": 0.05,
}
OFFICIAL_URL_BONUS = 0.05          # bis.gov.in / bis-certified hosts
CLAUSE_BONUS = 0.03                # clause reference present
PAGE_BONUS = 0.01                  # page reference present
EFFECTIVE_BONUS = 0.02             # version/effective_date present
EXACT_IS_BONUS = 0.35              # chunk IS == resolved IS
CONTENT_LEN_PENALTY = 0.02         # ultra-short chunks carry less signal


def _isnum(n):
    digits = "".join(ch for ch in str(n or "") if ch.isdigit())
    return digits


def rerank(candidates, query, resolved_is=None, top=6):
    """Deterministic rerank. Returns a new list, best first, capped at top."""
    resolved_is = [_isnum(x) for x in (resolved_is or []) if x]
    q_terms = [t for t in (query or "").lower().split() if len(t) >= 3]

    scored = []
    for c in candidates:
        s = float(c.get("relevance_score", c.get("score", 0.0)))
        c = dict(c)
        # 1. exact IS match on the resolved standard(s)
        cnum = _isnum(c.get("canonical_is_number"))
        if resolved_is and cnum and cnum in resolved_is:
            s += EXACT_IS_BONUS
        # 2. document type relevance
        s += TYPE_WEIGHT.get((c.get("document_type") or "").upper(), 0.0)
        # 3. semantic already in base; small boost when title overlaps query
        title = (c.get("title") or "").lower()
        if any(t in title for t in q_terms):
            s += 0.04
        # 4. clause / page precision
        if (c.get("clause") or "").strip():
            s += CLAUSE_BONUS
        if (c.get("page") or c.get("page_start")) not in (None, "",):
            s += PAGE_BONUS
        # 5. current/effective information
        if (c.get("effective_date") or "").strip() or (c.get("version") or "").strip():
            s += EFFECTIVE_BONUS
        # 6. source authority
        url = (c.get("source_url") or "").lower()
        if "bis.gov" in url or "indiacode" in url or "egazette" in url:
            s += OFFICIAL_URL_BONUS
        # mild penalty for stub content
        if len(c.get("content") or "") < 60:
            s -= CONTENT_LEN_PENALTY

        c["relevance_score"] = round(min(s, 1.0), 4)
        scored.append(c)

    scored.sort(key=lambda c: (-c["relevance_score"],
                               -(len(c.get("content") or "")),
                               str(c.get("chunk_id") or "")))
    return scored[:top]
