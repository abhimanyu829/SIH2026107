"""THE one LangGraph orchestrator.

Single graph, single shared state, single tool registry. The four specialized
nodes are routing policies inside this graph - never independent agents,
never agent-to-agent chatter.

Flow (spec):
START -> understand -> [simple path | agent path]
simple: quick_lookup -> collect_evidence -> synthesize -> cite -> finalize
agent : plan -> route -> execute_tool (bounded loop) -> collect_evidence ->
        synthesize -> cite -> finalize
Hard bound: MAX_AGENT_STEPS tool executions per request, always.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as cfg  # noqa: E402

from agent import executor, memory, planner  # noqa: E402
from agent.guardrails import (citations_from_evidence,  # noqa: E402
                              screen_answer, unknown_answer)
from agent.guardrails import validate_citations as check_citations  # noqa: E402
from agent.state import AgentState, new_state  # noqa: E402
from intelligence.response_builder import (deterministic_answer,  # noqa: E402
                                           evidence_prompt, llm_available,
                                           llm_complete)
from intelligence.query_understanding import (classify_task,  # noqa: E402
                                              detect_language,
                                              execution_mode,
                                              extract_entities)
from retrieval.evidence import build_evidence_set, evidence_confidence  # noqa: E402
from tools import call  # noqa: E402
from tools._shared import hybrid, supabase  # noqa: E402

_TRACE_N = [0]


def _t(node, tool, status):
    """One trace entry (spec agent-trace contract), auto-numbered."""
    _TRACE_N[0] += 1
    return [{"step": _TRACE_N[0], "node": node, "tool": tool or "",
             "status": str(status)[:80]}]


def _reset_trace():
    _TRACE_N[0] = 0


def _safe_hybrid(query, canonical_is_number=None):
    """Hybrid pull that degrades to empty results when credentials are absent
    (SystemExit from Phase-4 connectors becomes an UNKNOWN answer, not a
    crashed request)."""
    empty = {"standards": [], "bundles": [], "semantic": [], "focused": [],
             "evidence": []}
    try:
        return hybrid().retrieve(query, canonical_is_number=canonical_is_number)
    except SystemExit as e:
        return dict(empty, reason="credentials missing (exit %s)" % e.code)
    except Exception as e:
        return dict(empty, reason="%s: %s" % (type(e).__name__, str(e)[:120]))


# --------------------------------------------------------------------------
def understand_query(state: AgentState):
    """detect_language + extract_entities + classify_task + mode selection,
    one cheap deterministic pass. Memory resolves follow-up entities."""
    q = state["user_query"]
    language = state.get("language") or detect_language(q)
    entities = extract_entities(q)
    entities = memory.resolve_entities(state.get("conversation_id"), entities)
    task = classify_task(q, entities)
    mode = execution_mode(task, force_agent=bool(state.get("force_agent")))
    return {"language": language, "entities": entities, "intent": task,
            "execution_mode": mode,
            "trace": _t("understand_query", "-", "%s/%s" % (task, mode))}


def route_after_understanding(state: AgentState):
    return state["execution_mode"]


# ---- simple chat path -----------------------------------------------------
def quick_lookup(state: AgentState):
    """One hybrid pull answers simple questions; agent machinery skipped."""
    q = state["user_query"]
    ctx_is = state["entities"].get("is_number") or \
        memory.select_standard(state.get("conversation_id"))
    r = _safe_hybrid(q, canonical_is_number="IS %s" % ctx_is if ctx_is else None)
    evidence = build_evidence_set(r["evidence"])
    bundles = r["bundles"][:1]
    return {"retrieved_documents": r["semantic"][:10], "evidence": evidence,
            "bundles": bundles, "specialized_node": "simple_chat",
            "steps_count": 1,
            "trace": _t("quick_lookup", "hybrid_retrieve",
                        "%d std, %d evidence" % (len(r["standards"]),
                                                len(evidence))),
            "tool_calls": [{"step": 1, "tool": "hybrid_retrieve", "args": {}}],
            "tool_results": [{"step": 1, "tool": "hybrid_retrieve",
                              "ok": True, "data":
                              {"standards": len(r["standards"])}, "error": ""}]}


# ---- agent path -----------------------------------------------------------
def create_plan(state: AgentState):
    ctx = memory.context_for(state.get("conversation_id"))
    plan = planner.build_plan(state["intent"], state["user_query"],
                              entities=state["entities"],
                              memory_resolved=ctx.get("resolved"))
    if not plan:
        plan = [{"step": 1, "name": "collect_evidence",
                 "tool": "search_evidence",
                 "args": {"query": state["user_query"]}}]
    return {"plan": plan, "pending_steps": [s["name"] for s in plan],
            "current_step": 0,
            "trace": _t("create_plan", "-",
                         "%d steps: %s" % (len(plan),
                                           ", ".join(s["name"] for s in plan)))}


def route_specialized_node(state: AgentState):
    """Task type -> specialized node policy (same graph, same state)."""
    from agent.nodes import policy_for
    mod = policy_for(state["intent"])
    pol = mod.node_policy(state)
    keep = {s["name"] for s in state["plan"]}
    allowed = {n for n in pol["allowed_steps"]}
    allowed |= {"identify_product", "identify_standard", "get_standard",
               "collect_evidence"}
    plan = [s for s in state["plan"] if s["name"] in allowed or s["name"] in keep]
    node = mod.__name__.split(".")[-1] + "_node"
    return {"specialized_node": node, "plan": plan,
            "trace": _t("route_specialized_node", "-", node)}


def execute_tool(state: AgentState):
    """One bounded loop iteration: next step -> tool -> harvest -> extend."""
    entities = dict(state["entities"])
    ctx = {"is": entities.get("is_number"), "query": state["user_query"]}
    done = {r["step"] for r in state.get("tool_results", [])}
    done_names = {c["name"] for c in state.get("completed_steps", [])}
    executed = len(done)

    step_obj = None
    for s in state["plan"]:
        if s["step"] in done or s["name"] in done_names:
            continue
        step_obj = s
        break

    if step_obj is None:
        return {"pending_steps": [],
                "trace": _t("execute_tool", "-", "no step left")}
    if executed >= cfg.MAX_AGENT_STEPS:
        return {"pending_steps": [],
                "trace": _t("execute_tool", step_obj["tool"],
                            "MAX_AGENT_STEPS reached")}

    result = executor.run_step(step_obj, entities, ctx, state)
    executor.harvest(result, entities, ctx)
    if ctx.get("is"):
        entities.setdefault("is_number", executor._digits(ctx["is"]))
        entities["resolved_is"] = ctx["is"]

    tool_calls = [{"step": step_obj["step"], "tool": step_obj["tool"],
                   "args": step_obj.get("args") or {}}]
    tool_results = [{"step": step_obj["step"], "tool": step_obj["tool"],
                     "ok": result["ok"], "data": _slim(result["data"]),
                     "error": result.get("error", ""),
                     "provenance": result.get("provenance", "")}]
    completed = [{"name": step_obj["name"], "step": step_obj["step"],
                  "ok": result["ok"]}]

    # plan extension once an IS number resolved mid-flight
    plan = list(state["plan"])
    if ctx.get("is") and state["intent"] in (
            "COMPLIANCE_WORKFLOW", "CERTIFICATION_GUIDANCE",
            "STANDARD_DISCOVERY"):
        names = {s["name"] for s in plan} | done_names | \
            {c["name"] for c in completed}
        for n in ("check_qco", "determine_scheme", "retrieve_manual",
                  "retrieve_tests", "find_labs"):
            if n not in names and len(plan) < cfg.MAX_AGENT_STEPS:
                plan.append({"step": len(plan) + 1, "name": n,
                             "tool": planner.STEPS[n][0],
                             "args": planner.STEPS[n][1](
                                 entities, {"is": ctx["is"],
                                            "query": state["user_query"]})})
    pending = [s["name"] for s in plan
               if s["step"] not in done and s["name"] not in done_names]

    return {"entities": entities, "plan": plan,
            "tool_calls": tool_calls, "tool_results": tool_results,
            "completed_steps": completed, "pending_steps": pending,
            "current_step": step_obj["step"], "steps_count": executed + 1,
            "trace": _t(state.get("specialized_node") or "execute_tool",
                        step_obj["tool"],
                        "ok" if result["ok"] else
                        "fail: %s" % (result.get("error") or "")[:60])}


def decide_after_tool(state: AgentState):
    if state.get("pending_steps") and state["steps_count"] < cfg.MAX_AGENT_STEPS:
        return "loop"
    return "collect"


def collect_evidence(state: AgentState):
    """Evidence pass over everything resolved + tool-result evidence merge."""
    ents = state["entities"]
    ctx_is = ents.get("is_number") or ents.get("resolved_is")
    r = _safe_hybrid(state["user_query"],
                     canonical_is_number="IS %s" % ctx_is if ctx_is else None)
    evidence = list(build_evidence_set(r["evidence"]))
    for tr in state.get("tool_results", []):
        if tr.get("tool") == "search_evidence" and tr.get("ok") and tr.get("data"):
            evidence.extend(build_evidence_set(
                [{**h, "relevance_score": h.get("score", 0)} for h in tr["data"]]))
    seen = {}
    for e in evidence:
        k = e.get("evidence_id") or e.get("document_id") or str(e)[:60]
        if k not in seen or e["relevance_score"] > seen[k]["relevance_score"]:
            seen[k] = e
    evidence = sorted(seen.values(), key=lambda e: -e["relevance_score"])
    evidence = evidence[:cfg.RERANK_TOP]

    # structured bundle for the answer synthesis
    bundles = r["bundles"][:1] if r["bundles"] else []
    if not bundles and ctx_is:
        try:
            std = supabase().find_standard(ctx_is)
            if std:
                pg = supabase()
                bundles = [{"standard": std, "products": pg.products(std["is_id"]),
                            "qcos": pg.qcos(std["is_id"]),
                            "schemes": pg.schemes(std["is_id"]),
                            "tests": pg.tests(std["is_id"]),
                            "labs": pg.labs(std["is_id"], 10),
                            "manuals": pg.manuals(std["is_id"])}]
        except SystemExit:
            bundles = []
    # record the evidence pass as a tool call (it is one: hybrid retrieve)
    n = len(state.get("tool_results", []))
    return {"evidence": evidence, "bundles": bundles,
            "retrieved_documents": r["semantic"][:10],
            "tool_calls": [{"step": n + 1, "tool": "hybrid_retrieve",
                            "args": {"query": state["user_query"]}}],
            "tool_results": [{"step": n + 1, "tool": "hybrid_retrieve",
                              "ok": not r.get("reason"), "data":
                              {"evidence": len(evidence)},
                              "error": r.get("reason", "")}],
            "trace": _t("collect_evidence", "hybrid_retrieve",
                        "%d evidence" % len(evidence))}


def synthesize_answer(state: AgentState):
    """Deterministic grounded answer always; LLM rewording only if configured."""
    bundles = state.get("bundles") or []
    evidence = state.get("evidence", [])
    # verification tasks: pass the verify tool's own outcome through so the
    # deterministic answer states FOUND / NOT_FOUND from the record, not guess
    extra = {}
    if state["intent"] == "VERIFICATION":
        for tr in state.get("tool_results", []):
            if tr.get("tool") == "verify_identifier" and tr.get("ok"):
                d = tr.get("data") or {}
                if isinstance(d, dict):
                    extra["verdict"] = d.get("verdict") or "NOT_VERIFIED"
                break
    base, status = deterministic_answer(state["intent"], state["entities"],
                                        bundles, evidence, extra=extra)
    # asked-for IS number that never resolved: the bundle belongs to some
    # OTHER standard - the question was not answered
    asked = state["entities"].get("is_number")
    if asked and bundles:
        import re as _re
        want_d = "".join(c for c in str(asked) if c.isdigit())
        got_d = "".join(c for c in str(
            (bundles[0].get("standard") or {}).get(
                "canonical_is_number") or "") if c.isdigit())
        if want_d and got_d and want_d != got_d:
            base, status = (unknown_answer("the requested IS %s is not "
                                           "established in the available "
                                           "BIS data" % asked), "UNKNOWN")
    answer, conf = base, evidence_confidence(evidence)
    if llm_available() and (bundles or evidence):
        polished = llm_complete(
            "You are a precise BIS (Bureau of Indian Standards) assistant. "
            "Answer ONLY from the provided structured data and evidence. "
            "Never invent IS numbers, dates, statuses, tests, labs or "
            "citations. If something is not established in the data, say "
            "UNKNOWN.",
            evidence_prompt(state["user_query"], bundles, evidence,
                            state["intent"]))
        if polished:
            answer = polished
    if not bundles and not evidence:
        answer, status, conf = unknown_answer(), "UNKNOWN", 0.0
    return {"final_answer": answer, "confidence": conf, "status": status,
            "trace": _t("synthesize_answer", "-", status)}


def validate_citations(state: AgentState):
    """Citations from evidence only; validate; revise or finalize."""
    evidence = state.get("evidence", [])
    citations = citations_from_evidence(evidence)
    answer = state.get("final_answer", "")
    answer, problems = screen_answer(answer, state.get("bundles", []),
                                     evidence, state.get("unresolved_items"))
    ok, cite_problems = check_citations(answer, citations, evidence)
    if not ok:
        # drop unsupported citations rather than ship them
        keep_ids = {str(e.get("document_id") or e.get("evidence_id") or "")
                    for e in evidence}
        citations = [c for c in citations
                    if str(c.get("document_id") or "") in keep_ids]
        ok, cite_problems = check_citations(answer, citations, evidence)
    status = state.get("status", "COMPLETED")
    if status not in ("UNKNOWN", "REQUIRES_REVIEW"):
        status = "COMPLETED" if (state.get("bundles") or evidence) else "UNKNOWN"
    # an answer that itself states UNKNOWN (LLM honestly refusing from thin
    # evidence, or the deterministic unknown text) must never ship as COMPLETED
    stripped = (answer or "").lstrip("*# \n").lower()
    if stripped.startswith("unknown") or "couldn't determine" in stripped[:80]:
        status = "UNKNOWN"
    return {"final_answer": answer, "citations": citations, "status": status,
            "trace": _t("validate_citations", "-",
                        "citations ok" if ok else "citations revised")}


def finalize(state: AgentState):
    """Memory write-back + trace close."""
    cid = state.get("conversation_id", "")
    memory.remember_message(cid, "user", state["user_query"])
    memory.remember_message(cid, "assistant", (state.get("final_answer") or "")[:500])
    # entities resolved this turn (incl. mid-flight IS numbers from tools)
    # survive into follow-ups - bare 'which standard applies?' then works.
    memory.remember_resolved(cid, state.get("entities", {}))
    if state.get("execution_mode") == "AGENT":
        memory.remember_task(
            cid, state.get("intent", ""),
            [s["name"] for s in state.get("plan", [])],
            [c["name"] for c in state.get("completed_steps", [])],
            state.get("pending_steps", []), state.get("evidence", []))
    return {"trace": _t("finalize", "-", state.get("status", "")),
            "status": state.get("status", "COMPLETED")}


# --------------------------------------------------------------------------
def _slim(data):
    """Tool results stay serializable + small (no raw DB dumps)."""
    if isinstance(data, list):
        return data[:10]
    if isinstance(data, dict):
        out = {}
        for k, v in data.items():
            if isinstance(v, list):
                out[k] = v[:10]
            elif isinstance(v, (str, int, float, bool)) or v is None:
                out[k] = v
            else:
                out[k] = str(v)[:200]
        return out
    return data


def build_graph():
    """Compiles the single orchestrator graph."""
    from langgraph.graph import END, START, StateGraph

    g = StateGraph(AgentState)
    g.add_node("understand_query", understand_query)
    g.add_node("quick_lookup", quick_lookup)
    g.add_node("create_plan", create_plan)
    g.add_node("route_specialized_node", route_specialized_node)
    g.add_node("execute_tool", execute_tool)
    g.add_node("collect_evidence", collect_evidence)
    g.add_node("synthesize_answer", synthesize_answer)
    g.add_node("validate_citations", validate_citations)
    g.add_node("finalize", finalize)

    g.add_edge(START, "understand_query")
    g.add_conditional_edges(
        "understand_query", route_after_understanding,
        {"SIMPLE": "quick_lookup", "AGENT": "create_plan"})
    g.add_edge("quick_lookup", "collect_evidence")
    g.add_edge("create_plan", "route_specialized_node")
    g.add_edge("route_specialized_node", "execute_tool")
    g.add_conditional_edges(
        "execute_tool", decide_after_tool,
        {"loop": "execute_tool", "collect": "collect_evidence"})
    g.add_edge("collect_evidence", "synthesize_answer")
    g.add_edge("synthesize_answer", "validate_citations")
    g.add_edge("validate_citations", "finalize")
    g.add_edge("finalize", END)
    return g.compile()


_GRAPH = None


def get_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH


def run(query, conversation_id="", language="en", force_agent=False):
    """Runs the orchestrator once. Returns the final state dict."""
    _reset_trace()
    st = new_state(query, conversation_id=conversation_id, language=language)
    st["force_agent"] = force_agent
    final = get_graph().invoke(
        st, config={"recursion_limit": 6 + 2 * cfg.MAX_AGENT_STEPS})
    final.pop("force_agent", None)
    return final
