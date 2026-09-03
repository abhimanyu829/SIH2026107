"""Evidence engine: builds the evidence_set the answer must be grounded in.

Selects from reranked candidates, assigns stable evidence ids (chunk_id when
present), and enforces the contract that every evidence item carries its source
metadata. No content is invented, trimmed, or rewritten here.
"""


def build_evidence_set(reranked, limit=None):
    """Reranked candidates -> serializable evidence list, dedup by chunk."""
    import config as cfg
    limit = limit or cfg.RERANK_TOP
    seen, out = set(), []
    for c in reranked[:limit]:
        cid = c.get("chunk_id") or c.get("document_id") or ""
        key = cid or str(c)[:80]
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "evidence_id": cid,
            "document_id": c.get("document_id") or "",
            "canonical_is_number": c.get("canonical_is_number") or "",
            "document_type": c.get("document_type") or "",
            "title": c.get("title") or "",
            "section": c.get("section") or "",
            "clause": c.get("clause") or "",
            "page": c.get("page", c.get("page_start", "")),
            "content": c.get("content") or "",
            "source_url": c.get("source_url") or "",
            "version": c.get("version") or "",
            "effective_date": c.get("effective_date") or "",
            "relevance_score": float(c.get("relevance_score", 0.0)),
        })
    return out


def evidence_confidence(evidence, need=1):
    """Simple grounding confidence: 0 with no evidence, saturating with hits."""
    if not evidence:
        return 0.0
    top = max(e["relevance_score"] for e in evidence)
    return round(min(0.35 + 0.5 * top + 0.05 * max(0, len(evidence) - need), 0.98), 2)
