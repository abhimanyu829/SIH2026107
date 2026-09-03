"""compliance_node: full BIS preparation/compliance pathway.

Execution policy: product -> IS -> QCO -> scheme -> Product Manual ->
requirements/tests -> labs -> evidence. Emits structured requirement objects
with PASS/GAP/UNKNOWN status per requirement (document audit connects later).
"""

ALLOWED_TOOLS = {"find_product", "get_standard", "get_qco", "get_scheme",
                 "get_product_manual", "get_tests", "find_labs",
                 "search_evidence", "compare_requirements"}


def node_policy(state):
    from agent.planner import PLAN_TEMPLATES
    return {"allowed_tools": ALLOWED_TOOLS,
            "allowed_steps": PLAN_TEMPLATES["COMPLIANCE_WORKFLOW"],
            "instructions": ("Build the compliance pathway for the product: "
                             "standard, QCO, scheme, Product Manual sections, "
                             "required tests, recognized labs. Every "
                             "requirement object must carry evidence or be "
                             "marked UNKNOWN.")}


def build_requirements(tool_results):
    """Structured requirement objects from the tool results of this node.

    Each: {requirement, evidence_expected, source, status, reason} where
    status is PASS (established by data), GAP (expected but absent),
    UNKNOWN (cannot establish from available data).
    """
    reqs = []

    def add(name, ok, has_rows, source):
        if ok and has_rows:
            status, reason = "PASS", "established in authoritative data"
        elif ok:
            status, reason = "GAP", "no records linked in available data"
        else:
            status, reason = "UNKNOWN", "lookup unavailable or failed"
        reqs.append({"requirement": name, "evidence_expected": source,
                     "source": source, "status": status, "reason": reason})

    by_tool = {r["tool"]: r for r in tool_results if r.get("tool")}
    add("applicable_standard", True,
        bool(by_tool.get("get_standard", {}).get("data")), "bis.is_master")
    add("qco_linkage", "get_qco" in by_tool,
        bool(by_tool.get("get_qco", {}).get("data")), "bis.is_qco_mapping")
    add("certification_scheme", "get_scheme" in by_tool,
        bool(by_tool.get("get_scheme", {}).get("data")), "bis.is_scheme_mapping")
    add("product_manual", "get_product_manual" in by_tool,
        bool(by_tool.get("get_product_manual", {}).get("data", {})
             .get("manuals")), "bis.product_manual_master")
    add("required_tests", "get_tests" in by_tool,
        bool(by_tool.get("get_tests", {}).get("data")), "bis.is_test_mapping")
    add("recognized_labs", "find_labs" in by_tool,
        bool(by_tool.get("find_labs", {}).get("data")), "bis.is_lab_test_mapping")
    return reqs
