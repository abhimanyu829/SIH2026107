"""QCO tool: regulatory control order lookup for an IS number."""
from ._shared import supabase
from .registry import ToolResult, tool


@tool("get_qco",
      "Quality Control Orders linked to an IS number, with mandatory status "
      "and effective dates as recorded in the source data.",
      "Supabase bis.is_qco_mapping + bis.qco_master")
def get_qco(is_number: str) -> ToolResult:
    std = supabase().find_standard(is_number)
    if not std:
        return ToolResult(ok=False, tool="get_qco", data=None,
                          error="standard not found: %s" % is_number,
                          provenance="bis.is_qco_mapping")
    rows = supabase().qcos(std["is_id"])
    return ToolResult(ok=True, tool="get_qco", data=rows, error="",
                      provenance="Supabase bis.is_qco_mapping + bis.qco_master")


@tool("get_notifications",
      "BIS notifications linked to an IS number (gazette/press references).",
      "Supabase bis.is_entity_mapping + bis.notification_master")
def get_notifications(is_number: str) -> ToolResult:
    std = supabase().find_standard(is_number)
    if not std:
        return ToolResult(ok=False, tool="get_notifications", data=None,
                          error="standard not found: %s" % is_number,
                          provenance="bis.is_entity_mapping")
    pg = supabase().impl
    with pg.conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT n.notification_id, n.notification_number, n.title,
                   n.notification_date, n.effective_date, n.document_url
              FROM bis.is_entity_mapping m
              JOIN bis.notification_master n ON n.notification_id = m.entity_id
             WHERE m.is_id = %s AND m.entity_type ILIKE '%notification%'
             LIMIT 10""", (std["is_id"],))
        rows = [dict(zip([d[0] for d in cur.description], row))
                for row in cur.fetchall()]
    return ToolResult(ok=True, tool="get_notifications", data=rows, error="",
                      provenance="Supabase bis.is_entity_mapping")
