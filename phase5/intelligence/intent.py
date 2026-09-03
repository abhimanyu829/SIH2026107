"""Intent layer: thin aliases over query_understanding (kept as separate file
because the spec structure names it; no duplicated logic).
"""
from .query_understanding import (AGENT_TASKS, classify_task,  # noqa: F401
                                  execution_mode)


def intent_label(task):
    """Map task type to the API's lowercase intent field."""
    return (task or "general_bis").lower()
