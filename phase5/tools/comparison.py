"""Comparison tools: structured standard comparison. Never fabricates a
difference - every field shown comes from both records' data.
"""
from ._shared import supabase
from .registry import ToolResult, tool

COMPARE_FIELDS = [
    ("display_is_number", "IS number (display)"),
    ("title", "Title"),
    ("standard_status", "Status"),
    ("publication_date", "Publication date"),
    ("revision_date", "Revision date"),
    ("mandatory_voluntary", "Mandatory/ voluntary"),
    ("certification_type", "Certification type"),
    ("product_category", "Product category"),
    ("technical_committee", "Technical committee"),
    ("standard_scope", "Scope"),
]


def _std_row(is_number):
    return supabase().find_standard(is_number)


@tool("compare_standards",
      "Compare two Indian Standards field by field. Returns comparison_items "
      "with both values and both sources; differences only where data exists.",
      "Supabase bis.is_master")
def compare_standards(is_a: str, is_b: str) -> ToolResult:
    a, b = _std_row(is_a), _std_row(is_b)
    missing = [n for n, r in ((is_a, a), (is_b, b)) if not r]
    if missing:
        return ToolResult(ok=False, tool="compare_standards", data=None,
                          error="standard(s) not found: %s" % ", ".join(missing),
                          provenance="bis.is_master")
    items = []
    for field, label in COMPARE_FIELDS:
        va, vb = a.get(field) or "", b.get(field) or ""
        if not str(va).strip() and not str(vb).strip():
            continue                      # nothing established in the data
        items.append({
            "field": label,
            "value_a": va, "value_b": vb,
            "same": str(va).strip().lower() == str(vb).strip().lower(),
            "source_a": "bis.is_master %s" % a["canonical_is_number"],
            "source_b": "bis.is_master %s" % b["canonical_is_number"],
        })
    data = {"standard_a": a["canonical_is_number"],
            "standard_b": b["canonical_is_number"],
            "comparison_items": items}
    return ToolResult(ok=True, tool="compare_standards", data=data, error="",
                      provenance="Supabase bis.is_master (field comparison)")


@tool("compare_requirements",
      "Compare the requirement/test sets of two IS numbers (manual sections "
      "and tests, union with per-side presence).",
      "Supabase bis.product_manual_* + bis.is_test_mapping")
def compare_requirements(is_a: str, is_b: str) -> ToolResult:
    from .registry import call
    ta = call("get_tests", is_number=is_a)
    tb = call("get_tests", is_number=is_b)
    ma = call("get_product_manual", is_number=is_a)
    mb = call("get_product_manual", is_number=is_b)
    if not (ta["ok"] and tb["ok"]):
        return ToolResult(ok=False, tool="compare_requirements", data=None,
                          error="tests lookup failed for one side",
                          provenance="bis.is_test_mapping")
    key = lambda rows: sorted({(r.get("test_name") or "").strip().lower()
                               for r in rows})
    a_tests, b_tests = key(ta["data"]), key(tb["data"])
    a_secs = {(s["table"], (s["requirement_text"] or "")[:120])
              for s in (ma["data"]["sections"] if ma["ok"] else [])}
    b_secs = {(s["table"], (s["requirement_text"] or "")[:120])
              for s in (mb["data"]["sections"] if mb["ok"] else [])}
    items = []
    for t in set(a_tests) | set(b_tests):
        items.append({"field": "test: %s" % t,
                      "in_a": t in a_tests, "in_b": t in b_tests})
    only_a = [s for s in a_secs - b_secs][:10]
    only_b = [s for s in b_secs - a_secs][:10]
    return ToolResult(ok=True, tool="compare_requirements", data={
        "standard_a": is_a, "standard_b": is_b,
        "tests_only_a": [t for t in a_tests if t not in b_tests],
        "tests_only_b": [t for t in b_tests if t not in a_tests],
        "common_tests": [t for t in a_tests if t in b_tests],
        "manual_sections_only_a": [list(s) for s in only_a],
        "manual_sections_only_b": [list(s) for s in only_b],
    }, error="", provenance="Supabase bis.is_test_mapping + product_manual_*")
