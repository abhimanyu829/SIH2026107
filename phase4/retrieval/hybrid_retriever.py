"""Hybrid retriever: Supabase structured + Qdrant semantic in one response.

No LLM, no answer generation, no framework - just the combined evidence the
later RAG phase will consume. Architecture stays clean:
  Supabase = structured authority data (masters + relationships)
  Qdrant   = semantic document/evidence chunks (payload-filtered)

Run one query:   python retrieval/hybrid_retriever.py "What standard applies to office work chairs?"
Run all 5 smoke: python retrieval/hybrid_retriever.py --smoke
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config  # noqa: E402

from postgres_retriever import PostgresRetriever  # noqa: E402
from qdrant_retriever import QdrantRetriever  # noqa: E402

# Smoke suite from the Phase-4 spec. Queries 3-5 are follow-ups: the harness
# passes the IS number resolved by query 1 as explicit context (deterministic
# chaining, not a chatbot conversation).
SMOKE_QUERIES = [
    ("What standard applies to office work chairs?", None),
    ("What tests are required for IS 17631?", None),
    ("Which laboratories can perform the required tests?", "IS 17631"),
    ("What certification scheme applies?", "IS 17631"),
    ("What is the relevant Product Manual?", "IS 17631"),
]

class HybridRetriever:
    def __init__(self):
        self.pg = PostgresRetriever()
        self.qr = QdrantRetriever()

    def retrieve(self, query, context_is_number=None):
        """One retrieval response: structured bundle + semantic hits + combined."""
        structured = self.pg.structured_lookup(query, context_is_number)
        bundles = structured["bundles"]

        semantic = self.qr.search(query, limit=config.QDRANT_LIMIT)
        # Focused semantic pass over the standard(s) the structured side resolved.
        focused = []
        for b in bundles:
            num = b["standard"]["canonical_is_number"]
            if num:
                focused += self.qr.search(query, limit=3, canonical_is_number=num)

        # Combined evidence: structured rows first (authority), then semantic
        # hits, deduped by chunk_id, capped for the report.
        combined, seen = [], set()
        for b in bundles:
            std = b["standard"]
            combined.append(("supabase", "standard",
                             "%s %s" % (std.get("canonical_is_number") or "",
                                        std.get("title") or "")))
            for p in b["products"][:3]:
                combined.append(("supabase", "product", p.get("product_name") or ""))
            for q in b["qcos"][:3]:
                combined.append(("supabase", "qco",
                                 "%s %s" % (q.get("qco_number") or "", q.get("qco_name") or "")))
            for sc in b["schemes"][:3]:
                combined.append(("supabase", "scheme",
                                 "%s %s" % (sc.get("scheme_code") or "", sc.get("scheme_name") or "")))
            for t in b["tests"][:5]:
                combined.append(("supabase", "test", t.get("test_name") or ""))
            for l in b["labs"][:5]:
                combined.append(("supabase", "lab", l.get("lab_name") or ""))
            for pm in b["manuals"][:2]:
                combined.append(("supabase", "product_manual", pm.get("manual_title") or ""))
        for hits in (focused, semantic):
            for h in hits:
                if h["chunk_id"] in seen:
                    continue
                seen.add(h["chunk_id"])
                combined.append(("qdrant", h["document_type"] or "-",
                                 "%s | %s" % ((h["title"] or "")[:60],
                                              (h["content"] or "")[:120])))

        return {"query": query,
                "context_is_number": context_is_number,
                "supabase": {"bundles": bundles},
                "qdrant": {"focused": focused, "semantic": semantic},
                "hybrid": {"evidence": combined}}


def _print_result(r):
    print("-" * 60)
    print("QUERY")
    print("-" * 60)
    print("  %s%s" % (r["query"],
                     ("   [context: %s]" % r["context_is_number"])
                     if r["context_is_number"] else ""))
    print("\nSUPABASE RESULTS")
    if not r["supabase"]["bundles"]:
        print("  (no structured match for this query)")
    for b in r["supabase"]["bundles"]:
        print("  IS number : %s (%s)" % (std.get("canonical_is_number"),
                                        std.get("display_is_number")))
        print("  title     : %s" % (std.get("title") or ""))
        print("  product   : %s" % "; ".join(
            p.get("product_name") or "" for p in b["products"][:3]) or "-")
        print("  QCO       : %s" % "; ".join(
            "%s %s" % (q.get("qco_number"), q.get("qco_name") or "")
            for q in b["qcos"][:3]) or "-")
        print("  scheme    : %s" % "; ".join(
            "%s %s" % (s.get("scheme_code"), s.get("scheme_name") or "")
            for s in b["schemes"][:3]) or "-")
        print("  tests     : %s" % "; ".join(
            t.get("test_name") or "" for t in b["tests"][:5]) or "-")
        print("  labs      : %s" % "; ".join(
            l.get("lab_name") or "" for l in b["labs"][:3]) or "-")
    print("\nQDRANT RESULTS")
    sem = r["qdrant"]["focused"] + r["qdrant"]["semantic"]
    if not sem:
        print("  (no semantic hits)")
    for h in sem[:8]:
        print("  %.4f  %-16s  %-38s  clause=%s  %s  %s"
              % (h["score"], h["document_type"] or "-", (h["title"] or "")[:38],
                 h["clause"] or "-", h["page"] or "-", h["source_url"] or "-"))
    print("\nHYBRID RESULTS")
    if not r["hybrid"]["evidence"]:
        print("  (no combined evidence)")
    for src, kind, text in r["hybrid"]["evidence"][:18]:
        print("  [%s] %-15s %s" % (src, kind, text[:110]))


def run_smoke(write_json=True):
    """Runs the 5 spec smoke queries; queries 3-5 chain IS 17631 from query 1."""
    results, ctx = [], None
    hr = HybridRetriever()
    for i, (q, explicit) in enumerate(SMOKE_QUERIES, 1):
        context = explicit or ctx
        r = hr.retrieve(q, context_is_number=context)
        # resolve the follow-up context from the first successful bundle
        if ctx is None and r["supabase"]["bundles"]:
            ctx = r["supabase"]["bundles"][0]["standard"]["canonical_is_number"]
        results.append(r)
        _print_result(r)
        print()
    hr.pg.close()
    if write_json:
        path = config.merge_validation("smoke_tests", {
            "queries": [{"query": r["query"],
                         "context_is_number": r["context_is_number"],
                         "standards_found": [b["standard"]["canonical_is_number"]
                                             for b in r["supabase"]["bundles"]],
                         "semantic_hits": len(r["qdrant"]["focused"]) +
                                          len(r["qdrant"]["semantic"]),
                         "evidence_items": len(r["hybrid"]["evidence"])}
                        for r in results]})
        print("smoke-test report -> %s" % path)
    return results


if __name__ == "__main__":
    if "--smoke" in sys.argv:
        run_smoke()
    else:
        q = " ".join(a for a in sys.argv[1:] if a != "--json")
        hr = HybridRetriever()
        r = hr.retrieve(q)
        _print_result(r)
        if "--json" in sys.argv:
            print(json.dumps(r, indent=2, ensure_ascii=False, default=str)[:8000])
        hr.pg.close()
