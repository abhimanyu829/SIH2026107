"""Standards tools: keyword search, exact lookup, related standards."""
from ._shared import supabase
from .registry import ToolResult, tool

_RELATED_TYPES = ("COVERS", "COVERED_BY", "RELATED_TO", "SUPERSEDES",
                 "SUPERSEDED_BY", "AMENDS")


@tool("search_standards",
      "Search Indian Standards by keyword (title/scope/category). Use for "
      "discovery when the IS number is unknown.",
      "Supabase bis.is_master")
def search_standards(query: str, limit: int = 5) -> ToolResult:
    q = (query or "").strip()
    if not q:
        return ToolResult(ok=False, tool="search_standards", data=None,
                          error="empty query", provenance="bis.is_master")
    rows = supabase().search_standards(q, limit=limit)
    return ToolResult(ok=True, tool="search_standards", data=rows, error="",
                      provenance="Supabase bis.is_master (keyword match)")


@tool("get_standard",
      "Exact IS lookup by number, with or without year "
      "(e.g. 'IS 17631', '17631', 'IS 2347:2023').",
      "Supabase bis.is_master")
def get_standard(is_number: str, year: str = "") -> ToolResult:
    n = (is_number or "").strip()
    if not n:
        return ToolResult(ok=False, tool="get_standard", data=None,
                          error="empty is_number", provenance="bis.is_master")
    std = supabase().find_standard(n, year=year or None)
    if not std:
        return ToolResult(ok=False, tool="get_standard", data=None,
                          error="standard not found: %s%s"
                                % (n, ("/" + year) if year else ""),
                          provenance="bis.is_master")
    keep = {k: std.get(k) for k in (
        "is_id", "canonical_is_number", "display_is_number", "title",
        "standard_status", "publication_date", "revision_date",
        "mandatory_voluntary", "certification_type", "official_url",
        "document_url", "standard_scope", "product_category")}
    return ToolResult(ok=True, tool="get_standard", data=keep, error="",
                      provenance="Supabase bis.is_master (exact)")


@tool("get_related_standards",
      "Standards related to an IS number (covers/covered-by/supersession "
      "relationships preserved from Phase 3).",
      "Supabase bis.is_related_is + bis.is_master")
def get_related_standards(is_number: str) -> ToolResult:
    std = supabase().find_standard(is_number)
    if not std:
        return ToolResult(ok=False, tool="get_related_standards", data=None,
                          error="standard not found: %s" % is_number,
                          provenance="bis.is_related_is")
    pg = supabase()
    impl = pg.impl
    with impl.conn.cursor() as cur:
        cur.execute("""
            SELECT r.related_is_id, r.related_canonical_is_number,
                   r.relationship_type, s.title
              FROM bis.is_related_is r
              LEFT JOIN bis.is_master s ON s.is_id = r.related_is_id
             WHERE r.is_id = %s""", (std["is_id"],))
        rows = [dict(zip([d[0] for d in cur.description], row))
                for row in cur.fetchall()]
    return ToolResult(ok=True, tool="get_related_standards", data=rows,
                      error="", provenance="Supabase bis.is_related_is")
