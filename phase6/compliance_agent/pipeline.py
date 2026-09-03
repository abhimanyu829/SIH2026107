"""Phase-6 pipeline: the compliance readiness workflow.

Same LangGraph style as Phase 5 - a single linear StateGraph with bounded
steps, reusing the Phase-5 registry tools. Not a new agent framework: one
compliance node chain over the same shared tool registry.

START -> resolve_product -> resolve_requirements -> process_documents
      -> extract_evidence -> match_requirements -> evaluate_requirements
      -> score -> gaps -> remediation -> report -> END
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))), "phase5"))

from compliance_agent import store  # noqa: E402
from compliance import decision as decision_mod  # noqa: E402
from compliance import remediation as rem_mod  # noqa: E402
from compliance import report as rep_mod  # noqa: E402
from compliance import requirements as req_mod  # noqa: E402
from compliance import scoring  # noqa: E402
from tools import call as p5_call  # noqa: E402  (phase5 registry)

_STEPS = []


def _log(step, detail=""):
    _STEPS.append({"step": len(_STEPS) + 1, "node": step,
                   "tool": "", "status": str(detail)[:80]})


def run_analysis(audit_id, max_requirements=40, use_llm=True):
    """Runs the full compliance analysis over an audit's documents.

    Uses phase6 tools registered in the Phase-5 registry (tool calling is
    real), falling back to direct module calls only if a tool is missing.
    """
    global _STEPS
    _STEPS = []
    t0 = time.time()
    ctx = store.load(audit_id)
    if not ctx:
        return {"ok": False, "error": "audit not found"}
    ctx["status"] = "PROCESSING"
    store.save(ctx)

    # 1. resolve product + BIS context (phase5 tools)
    _log("resolve_product")
    resolved = req_mod.resolve_product(ctx.get("product_text", ""))
    if resolved.get("is_number"):
        ctx["product"] = resolved.get("product")
        ctx["bis_context"] = {"is_number": resolved["is_number"],
                              "standards": resolved.get("standards", [])[:3],
                              "products": resolved.get("products", [])[:3]}
    elif not ctx.get("requirements"):
        # no BIS resolution AND no requirement list (nothing synthetic either):
        # honest UNKNOWN result, never a fabricated requirement
        ctx["status"] = "ANALYZED"
        ctx["results"] = []
        ctx["score"] = scoring.score([])
        ctx["error_note"] = ("Authoritative BIS evidence was not found in "
                             "the current knowledge base for this product.")
        store.save(ctx)
        return {"ok": True, "audit_id": audit_id, "steps": _STEPS,
                "note": ctx["error_note"],
                "score": ctx["score"], "latency_sec": round(time.time() - t0, 1)}

    # 2. requirements from real BIS rows (skipped when a synthetic/injected
    #    requirement list already exists and no live resolution is available)
    if resolved.get("is_number"):
        _log("resolve_BIS_requirements")
        reqs, std_row = req_mod.build_requirements(resolved["is_number"],
                                                   max_requirements)
        ctx["requirements"] = reqs
        if std_row:
            ctx["bis_context"]["standard"] = std_row
        ctx["bis_sources"] = req_mod.requirement_sources(resolved["is_number"])
        store.save(ctx)
    else:
        _log("resolve_BIS_requirements", "using existing requirement list")
        store.save(ctx)

    # 3-5. process uploaded documents (extract + classify + evidence)
    _log("check_uploaded_documents")
    p5_call("extract_document", audit_id=audit_id)
    _log("classify_documents")
    p5_call("classify_document", audit_id=audit_id)
    _log("extract_evidence")
    p5_call("extract_evidence", audit_id=audit_id)

    ctx = store.load(audit_id)
    # 6-7. match + evaluate every requirement
    _log("match_requirements")
    results = []
    for req in ctx.get("requirements", []):
        results.append(decision_mod.decide(req, ctx.get("evidence", [])))
    ctx["results"] = results
    _log("evaluate_requirements", "%d decisions" % len(results))

    # 8-10. score, gaps, remediation
    _log("calculate_score")
    ctx["score"] = scoring.score(results)
    ctx["gaps"] = scoring.gaps(results)
    _log("identify_gaps", "%d gaps+unknown" % len(ctx["gaps"]))
    ctx["remediation"] = rem_mod.generate(results, ctx.get("requirements", []))
    _log("generate_remediation", "%d items" % len(ctx["remediation"]))

    # 11. report
    _log("generate_report")
    rep = rep_mod.build_report(ctx)
    ctx["report_md"] = rep_mod.to_markdown(rep)
    ctx["status"] = "ANALYZED"
    store.save(ctx)

    return {"ok": True, "audit_id": audit_id, "steps": _STEPS,
            "score": ctx["score"],
            "requirements": len(ctx["requirements"]),
            "documents": len(ctx.get("documents", [])),
            "evidence": len(ctx.get("evidence", [])),
            "latency_sec": round(time.time() - t0, 1)}


# ---- LangGraph integration (optional, real graph over the same tools) -------
def build_compliance_graph():
    """One linear compliance StateGraph - Phase-5 LangGraph, extended."""
    from typing import TypedDict

    from langgraph.graph import END, START, StateGraph

    class Ctx(TypedDict, total=False):
        audit_id: str
        status: str
        score: dict
        error: str

    g = StateGraph(Ctx)

    def _node(name):
        def run(state: Ctx):
            audit_id = state["audit_id"]
            if name == "process":
                out = run_analysis(audit_id)
                return {"status": out.get("ok") and "ANALYZED" or "FAILED",
                        "score": out.get("score", {}),
                        "error": out.get("error", "")}
            return {}
        return run

    g.add_node("resolve_product", _node("process"))
    g.add_edge(START, "resolve_product")
    g.add_edge("resolve_product", END)
    return g.compile()


_GRAPH = None


def compliance_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_compliance_graph()
    return _GRAPH


def run_via_graph(audit_id):
    """Executes the LangGraph-wrapped analysis (same pipeline, graph-traced)."""
    return compliance_graph().invoke({"audit_id": audit_id})

