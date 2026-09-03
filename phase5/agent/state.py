"""LangGraph shared state: one TypedDict, serializable, small on purpose.

langgraph merges state updates by key, so each node returns only what it
changed. Everything here is JSON-serializable plain data (no model objects),
which is what the API layer needs to echo traces back.
"""
from typing import Annotated, Any, TypedDict


def _merge_list(old, new):
    """LangGraph reducer: append-only lists (tool_calls, steps, evidence...)."""
    old = old or []
    new = new or []
    out = list(old)
    out.extend(x for x in new)
    return out


class AgentState(TypedDict, total=False):
    # request
    user_query: str
    conversation_id: str
    language: str
    intent: str                      # task type
    execution_mode: str              # SIMPLE | AGENT
    force_agent: bool
    # understanding
    entities: dict
    memory_context: dict             # resolved entities/topic from memory
    # planning
    plan: list                       # [{step, tool, args, done}]
    current_step: int
    completed_steps: Annotated[list, _merge_list]
    pending_steps: list              # REPLACES each step (remaining steps)
    # execution
    tool_calls: Annotated[list, _merge_list]     # [{step, tool, args}]
    tool_results: Annotated[list, _merge_list]   # [{step, tool, ok, data, error}]
    specialized_node: str
    # evidence
    retrieved_documents: Annotated[list, _merge_list]
    evidence: Annotated[list, _merge_list]
    citations: list
    # synthesis
    bundles: list                    # structured bundles the answer rests on
    # output
    final_answer: str
    confidence: float
    status: str                      # COMPLETED | UNKNOWN | REQUIRES_REVIEW | FAILED
    unresolved_items: Annotated[list, _merge_list]
    error: str
    trace: Annotated[list, _merge_list]           # [{step, node, tool, status}]
    steps_count: int


def new_state(query, conversation_id="", language="en", entities=None,
              intent="", mode="SIMPLE", memory_context=None) -> AgentState:
    """Fresh state for one request (memory injects context, never state)."""
    return AgentState(
        user_query=query,
        conversation_id=conversation_id,
        language=language,
        intent=intent,
        execution_mode=mode,
        force_agent=False,
        entities=entities or {},
        memory_context=memory_context or {},
        bundles=[],
        plan=[], current_step=0, completed_steps=[], pending_steps=[],
        tool_calls=[], tool_results=[], retrieved_documents=[], evidence=[],
        citations=[], final_answer="", confidence=0.0, status="",
        unresolved_items=[], error="", trace=[], steps_count=0,
        specialized_node="",
    )
