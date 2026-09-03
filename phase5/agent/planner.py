"""Planner: short machine-readable plans, deterministic by task type.

The LLM is allowed to propose a different step order when configured, but the
plan vocabulary is fixed - a step is a (name, tool, args) the executor knows.
No multi-agent planning, no plan trees, max MAX_AGENT_STEPS steps.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as cfg  # noqa: E402

from intelligence.query_understanding import extract_entities  # noqa: E402

# Fixed step vocabulary: name -> (tool, arg-builder)
STEPS = {
    "identify_product": ("find_product",
                         lambda e, ctx: {"query": e.get("product_text") or ""}),
    "identify_standard": ("search_standards",
                          lambda e, ctx: {"query": e.get("product_text") or ""}),
    "get_standard": ("get_standard",
                     lambda e, ctx: {"is_number": e["is_number"]}),
    "check_qco": ("get_qco", lambda e, ctx: {"is_number": ctx["is"]}),
    "determine_scheme": ("get_scheme", lambda e, ctx: {"is_number": ctx["is"]}),
    "retrieve_manual": ("get_product_manual",
                        lambda e, ctx: {"is_number": ctx["is"]}),
    "retrieve_tests": ("get_tests", lambda e, ctx: {"is_number": ctx["is"]}),
    "find_labs": ("find_labs", lambda e, ctx: {"is_number": ctx["is"]}),
    "collect_evidence": ("search_evidence",
                         lambda e, ctx: {"query": ctx["query"],
                                         "canonical_is_number": ctx["is"]}),
    "compare_standards": ("compare_standards",
                          lambda e, ctx: {"is_a": e["is_numbers"][0],
                                          "is_b": e["is_numbers"][1]}),
    "compare_requirements": ("compare_requirements",
                             lambda e, ctx: {"is_a": e["is_numbers"][0],
                                             "is_b": e["is_numbers"][1]}),
    "verify": ("verify_identifier",
               lambda e, ctx: {"identifier": e.get("identifier") or "",
                                "context": ctx["query"]}),
}

PLAN_TEMPLATES = {
    "COMPLIANCE_WORKFLOW": ["identify_product", "identify_standard",
                            "get_standard", "check_qco", "determine_scheme",
                            "retrieve_manual", "retrieve_tests", "find_labs",
                            "collect_evidence"],
    "COMPARISON": ["compare_standards", "compare_requirements",
                   "collect_evidence"],
    "VERIFICATION": ["verify", "collect_evidence"],
    "CERTIFICATION_GUIDANCE": ["identify_product", "identify_standard",
                               "check_qco", "determine_scheme",
                               "collect_evidence"],
    "DOCUMENT_RESEARCH": ["get_standard", "retrieve_manual", "collect_evidence"],
    "STANDARD_DISCOVERY": ["identify_product", "identify_standard",
                           "get_standard", "collect_evidence"],
    "TEST_LOOKUP": ["get_standard", "retrieve_tests", "collect_evidence"],
    "LAB_LOOKUP": ["retrieve_tests", "find_labs", "collect_evidence"],
    "QCO_LOOKUP": ["check_qco", "collect_evidence"],
    "SCHEME_LOOKUP": ["determine_scheme", "collect_evidence"],
    "SIMPLE_LOOKUP": ["get_standard", "collect_evidence"],
    "PRODUCT_DISCOVERY": ["identify_product", "collect_evidence"],
    "GENERAL_BIS": ["collect_evidence"],
}


def build_plan(task, query, entities=None, memory_resolved=None):
    """Plan for a task. Resolves an IS number from entities or memory; steps
    needing an IS when none is known are skipped (not guessed)."""
    entities = dict(entities or extract_entities(query))
    resolved = dict(memory_resolved or {})
    for k, v in resolved.items():
        entities.setdefault(k, v)
    if not entities.get("is_number") and resolved.get("is_number"):
        entities["is_number"] = resolved["is_number"]

    names = [n for n in PLAN_TEMPLATES.get(task, ["collect_evidence"])
             if _usable(n, entities, query)]
    # hard bound (spec): plans never exceed MAX_AGENT_STEPS
    names = names[:cfg.MAX_AGENT_STEPS]
    plan = [{"step": i + 1, "name": n, "tool": STEPS[n][0],
             "args": STEPS[n][1](entities, {"is": entities.get("is_number"),
                                             "query": query})}
            for i, n in enumerate(names)]
    return plan


def _usable(name, entities, query):
    """Skip steps whose required input the plan does not have yet."""
    if name == "get_standard":
        return bool(entities.get("is_number"))
    if name in ("check_qco", "determine_scheme", "retrieve_manual",
                "retrieve_tests", "find_labs"):
        return bool(entities.get("is_number"))       # fills at runtime from ctx
    if name in ("compare_standards", "compare_requirements"):
        return len(entities.get("is_numbers") or []) >= 2
    if name == "identify_product":
        return bool(entities.get("product_text"))
    if name == "verify":
        return bool(entities.get("identifier"))
    return True
