"""comparison_node: compare standards/requirements/schemes. Structured
differences only - every value shown exists in both records' data.
"""

ALLOWED_TOOLS = {"get_standard", "get_product_manual", "get_tests",
                 "search_evidence", "compare_standards", "compare_requirements"}


def node_policy(state):
    return {"allowed_tools": ALLOWED_TOOLS,
            "allowed_steps": ["compare_standards", "compare_requirements",
                              "collect_evidence"],
            "instructions": ("Compare the two standards field by field. "
                             "Report only differences the data establishes; "
                             "never fabricate a difference.")}
