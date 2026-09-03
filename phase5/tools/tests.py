"""Tests tool: required tests for an IS number with method standards."""
from ._shared import supabase
from .registry import ToolResult, tool


@tool("get_tests",
      "Tests required for an IS number, with method standards, clauses and "
      "acceptance criteria as recorded in Phase 3.",
      "Supabase bis.is_test_mapping + bis.test_master")
def get_tests(is_number: str) -> ToolResult:
    std = supabase().find_standard(is_number)
    if not std:
        return ToolResult(ok=False, tool="get_tests", data=None,
                          error="standard not found: %s" % is_number,
                          provenance="bis.is_test_mapping")
    rows = supabase().tests(std["is_id"])
    return ToolResult(ok=True, tool="get_tests", data=rows, error="",
                      provenance="Supabase bis.is_test_mapping + bis.test_master")
