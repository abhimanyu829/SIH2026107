"""test_tools.py - registry contract: every tool callable, typed, provenance."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _base import db_available, evaluate


def runner(case):
    from tools import registry, tool_specs
    fails, results = [], []
    regs = registry()
    if len(regs) < 15:
        fails.append("registry too small: %d tools" % len(regs))
    specs = tool_specs()
    if len(specs) != len(regs):
        fails.append("specs/registry mismatch")
    for name, fn in regs.items():
        if not getattr(fn, "_tool_description", ""):
            fails.append("tool %s has no description" % name)
    # empty-arg guard on a representative tool per family
    from tools import call
    r = call("get_standard", is_number="")
    if r["ok"]:
        fails.append("get_standard accepted empty is_number")
    r = call("search_evidence", query="")
    if r["ok"]:
        fails.append("search_evidence accepted empty query")
    r = call("nonexistent_tool")
    if r["ok"]:
        fails.append("unknown tool call succeeded")
    results.append({"answer": "registry=%d" % len(regs)})
    return results, fails


if __name__ == "__main__":
    evaluate("tool_tests", runner)
