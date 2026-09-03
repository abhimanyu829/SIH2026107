"""Product Manual tools: manual master + sectioned requirements."""
from ._shared import supabase
from .registry import ToolResult, tool

SECTION_TABLES = ("product_manual_requirements", "product_manual_testing",
                  "product_manual_sampling", "product_manual_marking",
                  "product_manual_infrastructure")


@tool("get_product_manual",
      "Product Manual(s) for an IS number, with sectioned requirement text "
      "(requirements/testing/sampling/marking/infrastructure).",
      "Supabase bis.is_product_manual_mapping + bis.product_manual_*")
def get_product_manual(is_number: str, section: str = "") -> ToolResult:
    std = supabase().find_standard(is_number)
    if not std:
        return ToolResult(ok=False, tool="get_product_manual", data=None,
                          error="standard not found: %s" % is_number,
                          provenance="bis.product_manual_master")
    pg = supabase()
    manuals = pg.manuals(std["is_id"])
    tables = [t for t in SECTION_TABLES
              if not section or t.endswith(section.lower())]
    impl = pg.impl
    detail = []
    if manuals:
        pm_ids = [m["pm_id"] for m in manuals]
        with impl.conn.cursor() as cur:
            for t in tables:
                cur.execute('SELECT section_category, requirement_text, clause, '
                            'source_url FROM bis."%s" WHERE pm_id = ANY(%%s) '
                            'LIMIT 20' % t, (pm_ids,))
                for row in cur.fetchall():
                    detail.append({"table": t,
                                   "section_category": row[0],
                                   "requirement_text": (row[1] or "")[:400],
                                   "clause": row[2], "source_url": row[3]})
    return ToolResult(ok=True, tool="get_product_manual",
                      data={"manuals": manuals, "sections": detail}, error="",
                      provenance="Supabase bis.product_manual_master + "
                                 "bis.product_manual_* sections")


@tool("get_document",
      "Registered document metadata for a document_id, if present.",
      "Supabase bis.document_master")
def get_document(document_id: str) -> ToolResult:
    d = (document_id or "").strip()
    if not d:
        return ToolResult(ok=False, tool="get_document", data=None,
                          error="empty document_id", provenance="bis.document_master")
    pg = supabase().impl
    with pg.conn.cursor() as cur:
        cur.execute("SELECT document_id, document_type, title, "
                    "canonical_is_number, version, source_url, download_url, "
                    "page_count, effective_date FROM bis.document_master "
                    "WHERE document_id = %s", (d,))
        row = cur.fetchone()
        data = (dict(zip([c[0] for c in cur.description], row))
                if row else None)
    return ToolResult(ok=bool(data), tool="get_document", data=data,
                      error="" if data else "document not found",
                      provenance="Supabase bis.document_master")
