"""Hybrid retrieval: structured candidates + semantic candidates, merged,
deduplicated, reranked, trimmed to the evidence set. No raw DB dumps to LLM.
"""
from .qdrant import QdrantFacade
from .reranker import rerank
from .supabase import SupabaseRetriever


def _norm_is(n):
    return (n or "").strip().upper().replace("IS ", "").replace("IS", "").strip()


class HybridRetriever:
    def __init__(self, supabase=None, qdrant=None):
        self.pg = supabase or SupabaseRetriever()
        self.qd = qdrant or QdrantFacade()

    def retrieve(self, query, canonical_is_number=None, document_type="",
                 top_k=None, evidence_top=None):
        """One hybrid pull.

        Returns {'standards': [std rows], 'semantic': [evidence dicts],
        'evidence': reranked evidence list}. Structured first for authority,
        semantic dedupes against the structured IS number for focus.
        """
        import config as cfg
        # structured side
        bundles = self.pg.structured_lookup(
            query, context_is_number=canonical_is_number)["bundles"]
        standards = [b["standard"] for b in bundles]

        # semantic side - general pass + focused pass per resolved standard
        semantic = self.qd.search(query, document_type=document_type,
                                  top_k=top_k)
        focused = []
        seen_ids = {e.get("chunk_id") for e in semantic}
        for std in standards[:2]:
            num = std.get("canonical_is_number")
            if not num:
                continue
            for h in self.qd.search(query, canonical_is_number=num,
                                    top_k=3):
                if h["chunk_id"] not in seen_ids:
                    seen_ids.add(h["chunk_id"])
                    focused.append(h)

        candidates = focused + semantic
        for c in candidates:
            c.setdefault("relevance_score", c.get("score", 0.0))
            c["relevance_score"] = float(c["relevance_score"])

        evidence = rerank(candidates, query,
                          resolved_is=[_norm_is(s.get("canonical_is_number"))
                                       for s in standards if s],
                          top=evidence_top or cfg.RERANK_TOP)

        return {"standards": standards, "bundles": bundles,
                "semantic": semantic, "focused": focused, "evidence": evidence}
