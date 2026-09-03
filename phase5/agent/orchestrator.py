"""Orchestrator entry: chat + agent-run facades over the one graph.

Chat = SIMPLE mode, least-cost path. Agent-run = AGENT mode (explicit or
auto-selected). Both share the same graph, memory and tools.
"""
from agent import graph, memory
from agent.guardrails import citations_from_evidence


def _related(bundles):
    b = bundles[0] if bundles else {"products": [], "qcos": [], "schemes": [],
                                    "tests": [], "labs": []}
    return {"products": b.get("products", [])[:5], "qcos": b.get("qcos", [])[:5],
            "schemes": b.get("schemes", [])[:5], "tests": b.get("tests", [])[:8],
            "labs": b.get("labs", [])[:5]}


def chat(message, conversation_id="", language="en"):
    """SIMPLE chat: least expensive workflow that answers the message."""
    state = graph.run(message, conversation_id=conversation_id,
                      language=language, force_agent=False)
    bundles = state.get("bundles") or []
    return {
        "answer": state.get("final_answer", ""),
        "confidence": state.get("confidence", 0.0),
        "language": state.get("language", language),
        "intent": (state.get("intent") or "general_bis").lower(),
        "entities": {k: v for k, v in (state.get("entities") or {}).items()
                     if v not in (None, "", [], False)},
        "sources": [{"title": c.get("title"), "source_url": c.get("source_url"),
                     "document_id": c.get("document_id")}
                    for c in state.get("citations", [])][:5],
        "related": _related(bundles),
        "agent": {"used": state.get("execution_mode") == "AGENT",
                  "steps": state.get("steps_count", 0),
                  "tools_used": [c["tool"] for c in state.get("tool_calls", [])]},
    }


def agent_run(message, conversation_id="", language="en", force_agent=True):
    """AGENT workflow: plan, tools, evidence, citations."""
    state = graph.run(message, conversation_id=conversation_id,
                      language=language, force_agent=force_agent)
    return {
        "answer": state.get("final_answer", ""),
        "status": state.get("status", "COMPLETED"),
        "plan": [{"step": s["step"], "name": s["name"]}
                 for s in state.get("plan", [])],
        "steps": state.get("trace", []),
        "tools_used": [c["tool"] for c in state.get("tool_calls", [])],
        "evidence": state.get("evidence", []),
        "citations": state.get("citations", []),
        "confidence": state.get("confidence", 0.0),
        "entities": {k: v for k, v in (state.get("entities") or {}).items()
                     if v not in (None, "", [], False)},
        "unresolved_items": state.get("unresolved_items", []),
        "conversation_id": conversation_id,
    }
