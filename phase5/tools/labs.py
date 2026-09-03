"""Laboratory tools: labs for an IS number + lab scope detail."""
from ._shared import supabase
from .registry import ToolResult, tool


@tool("find_labs",
      "Laboratories recognized for the tests of an IS number (lab name, city, "
      "state, recognition status, per-test capability).",
      "Supabase bis.is_lab_test_mapping + bis.lab_master")
def find_labs(is_number: str, limit: int = 25) -> ToolResult:
    std = supabase().find_standard(is_number)
    if not std:
        return ToolResult(ok=False, tool="find_labs", data=None,
                          error="standard not found: %s" % is_number,
                          provenance="bis.is_lab_test_mapping")
    rows = supabase().labs(std["is_id"], limit=limit)
    return ToolResult(ok=True, tool="find_labs", data=rows, error="",
                      provenance="Supabase bis.is_lab_test_mapping + bis.lab_master")


@tool("get_lab_scope",
      "Scope rows (tests an IS-wise coverage) for one laboratory id.",
      "Supabase bis.lab_scope")
def get_lab_scope(lab_id: str) -> ToolResult:
    d = (lab_id or "").strip()
    if not d:
        return ToolResult(ok=False, tool="get_lab_scope", data=None,
                          error="empty lab_id", provenance="bis.lab_scope")
    impl = supabase().impl
    with impl.conn.cursor() as cur:
        cur.execute("SELECT is_id, canonical_is_number, test_name, "
                    "test_method_standard, clause_reference, capability, "
                    "scope_status, scope_validity, testing_charge, source_url "
                    "FROM bis.lab_scope WHERE lab_id = %s LIMIT 50", (d,))
        rows = [dict(zip([c[0] for c in cur.description], r))
                for r in cur.fetchall()]
    return ToolResult(ok=bool(rows), tool="get_lab_scope", data=rows,
                      error="" if rows else "no scope rows for lab",
                      provenance="Supabase bis.lab_scope")
