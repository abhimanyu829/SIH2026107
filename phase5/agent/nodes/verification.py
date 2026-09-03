"""verification_node: verify BIS identifiers against authoritative data.

Verdicts: VALIDATED / NOT_FOUND / NOT_VERIFIED / CONTEXT_MISMATCH.
Format alone is never proof; results come from exact matches in Supabase only.
"""

ALLOWED_TOOLS = {"verify_identifier", "search_evidence"}


def node_policy(state):
    return {"allowed_tools": ALLOWED_TOOLS,
            "allowed_steps": ["verify", "collect_evidence"],
            "instructions": ("Verify the identifier against authoritative "
                             "data only. Report the verdict verbatim with "
                             "preserved evidence; never fabricate a result.")}
