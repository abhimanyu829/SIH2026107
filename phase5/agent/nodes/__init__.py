"""Specialized graph nodes. Execution policies in ONE graph - not agents."""
from . import comparison, compliance, standards, verification  # noqa: F401

POLICIES = {
    "standards_node": standards,
    "verification_node": verification,
    "compliance_node": compliance,
    "comparison_node": comparison,
}


def policy_for(task):
    """Task type -> specialized node module."""
    return {
        "COMPARISON": comparison,
        "VERIFICATION": verification,
        "COMPLIANCE_WORKFLOW": compliance,
        "CERTIFICATION_GUIDANCE": compliance,
        "DOCUMENT_RESEARCH": compliance,
        "STANDARD_DISCOVERY": standards,
        "PRODUCT_DISCOVERY": standards,
    }.get(task, standards)
