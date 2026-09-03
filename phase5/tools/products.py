"""Product tools. Deterministic keyword search over product_master."""
from ._shared import supabase
from .registry import ToolResult, tool


@tool("find_product",
      "Find BIS product records matching free product text "
      "(e.g. 'adjustable office work chairs'). Returns product ids and names.",
      "Supabase bis.product_master + is_product_mapping")
def find_product(query: str) -> ToolResult:
    q = (query or "").strip()
    if not q:
        return ToolResult(ok=False, tool="find_product", data=None,
                          error="empty query", provenance="bis.product_master")
    rows = supabase().search_products(q)
    return ToolResult(ok=True, tool="find_product", data=rows[:10], error="",
                      provenance="Supabase bis.product_master (keyword match)")


@tool("get_product",
      "Get the BIS products linked to an IS number (relationship traversal).",
      "Supabase bis.is_product_mapping")
def get_product(is_number: str) -> ToolResult:
    std = supabase().find_standard(is_number)
    if not std:
        return ToolResult(ok=False, tool="get_product", data=None,
                          error="standard not found: %s" % is_number,
                          provenance="bis.is_product_mapping")
    rows = supabase().products(std["is_id"])
    return ToolResult(ok=True, tool="get_product", data=rows, error="",
                      provenance="Supabase bis.is_product_mapping")
