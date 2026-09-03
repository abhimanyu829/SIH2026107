"""Qdrant retrieval facade for Phase 5 - same QdrantRetriever as Phase 4,
same one collection (bis_knowledge), same shared BGE-M3 embedder. Phase 5 only
normalizes the output into EvidenceItem-shaped dicts with full content kept.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, _ROOT)

from ._phase4_loader import (load_phase4_connect,  # noqa: E402
                             load_phase4_module)

_qr = None


def _impl():
    """phase4's QdrantRetriever by path (same shared BGE-M3 loader).

    qdrant.connect is preloaded with phase4's config bound: the retriever
    imports it lazily (first client use), which would otherwise resolve
    'config' to phase5's config module.
    """
    global _qr
    if _qr is None:
        load_phase4_connect("qdrant", "qdrant.connect")
        _qr = load_phase4_module("retrieval/qdrant_retriever.py",
                                 "phase4_qdrant_retriever")
    return _qr


class QdrantFacade:
    """search(query, filters, top_k) -> list of evidence dicts (spec contract)."""

    def __init__(self, collection=None):
        import config as cfg
        self.impl = _impl().QdrantRetriever(collection or cfg.QDRANT_COLLECTION)

    def search(self, query, document_type="", canonical_is_number="",
               is_id="", top_k=None):
        import config as cfg
        limit = top_k or cfg.QDRANT_LIMIT
        types = [t for t in (document_type or "").split(",") if t] or None
        hits = self.impl.search(query, limit=limit, document_types=types,
                                canonical_is_number=canonical_is_number or None,
                                is_id=is_id or None)
        # normalize to the Phase-5 evidence shape; keep full payload content
        out = []
        for h in hits:
            h = dict(h)
            pl = h.pop("payload", {})
            out.append({**pl, **h})
        return out
