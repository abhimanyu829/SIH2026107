"""standards_node: find applicable IS + supporting regulatory info.

Execution policy: product -> candidate IS -> selected IS -> QCO -> scheme ->
evidence. Never invents an IS number; keeps multiple candidates when the data
does not single one out; prefers current/effective info (reranker handles it).
"""

ALLOWED_TOOLS = {"find_product", "search_standards", "get_standard",
                 "get_related_standards", "get_qco", "get_scheme",
                 "search_evidence"}


def node_policy(state):
    """Step filter for the executor when the graph routes to this node."""
    from agent.planner import PLAN_TEMPLATES
    order = PLAN_TEMPLATES["STANDARD_DISCOVERY"] + \
        ["check_qco", "determine_scheme", "get_related_standards"]
    allowed_names = [n for n in order if n not in ("get_standard",)]
    return {"allowed_tools": ALLOWED_TOOLS,
            "allowed_steps": allowed_names,
            "instructions": ("Find the applicable Indian Standard for the "
                             "product. Keep multiple candidates if the data "
                             "does not single one out. Then fetch QCO and "
                             "scheme linkages. Never guess an IS number.")}
