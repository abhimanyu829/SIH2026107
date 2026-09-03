"""Semantic evidence tool - the Qdrant side of hybrid retrieval."""
from ._shared import qdrant
from .registry import ToolResult, tool


@tool("search_evidence",
      "Semantic search over BIS evidence chunks (manuals, standards, QCOs, "
      "schemes, tests, FAQs, legal text). Filters: canonical_is_number, "
      "document_type, is_id. Returns scored evidence with citations.",
      "Qdrant Cloud bis_knowledge")
def search_evidence(query: str, canonical_is_number: str = "",
                    document_type: str = "", is_id: str = "",
                    top_k: int = 5) -> ToolResult:
    q = (query or "").strip()
    if not q:
        return ToolResult(ok=False, tool="search_evidence", data=None,
                          error="empty query", provenance="Qdrant bis_knowledge")
    try:
        hits = qdrant().search(q, document_type=document_type,
                               canonical_is_number=canonical_is_number,
                               is_id=is_id, top_k=top_k)
    except SystemExit:
        raise
    except Exception as e:
        return ToolResult(ok=False, tool="search_evidence", data=None,
                          error="%s: %s" % (type(e).__name__, str(e)[:150]),
                          provenance="Qdrant bis_knowledge")
    return ToolResult(ok=True, tool="search_evidence", data=hits, error="",
                      provenance="Qdrant Cloud bis_knowledge (BGE-M3 cosine)")
