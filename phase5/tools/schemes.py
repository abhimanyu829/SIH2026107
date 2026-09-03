"""Scheme tool: certification scheme applicability for an IS number."""
from ._shared import supabase
from .registry import ToolResult, tool


@tool("get_scheme",
      "Certification schemes linked to an IS number (Scheme I/II/FMCS etc.), "
      "with relationship type as recorded in Phase 3.",
      "Supabase bis.is_scheme_mapping + bis.scheme_master")
def get_scheme(is_number: str) -> ToolResult:
    std = supabase().find_standard(is_number)
    if not std:
        return ToolResult(ok=False, tool="get_scheme", data=None,
                          error="standard not found: %s" % is_number,
                          provenance="bis.is_scheme_mapping")
    rows = supabase().schemes(std["is_id"])
    return ToolResult(ok=True, tool="get_scheme", data=rows, error="",
                      provenance="Supabase bis.is_scheme_mapping + bis.scheme_master")
