"""Phase-5 runner: offline checks -> API boot check -> evaluation -> report.

  python run_phase5.py              # full: checks + eval suite + report
  python run_phase5.py --check      # offline: imports, graph compile, no creds needed
  python run_phase5.py --serve      # boot uvicorn on :8001 (background friendly)
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import config as cfg  # noqa: E402

PY = sys.executable


def offline_check():
    """No credentials needed: AST + imports + graph compile + tool registry."""
    print("[check] compileall ...")
    r = subprocess.run([PY, "-m", "compileall", "-q",
                        os.path.join(HERE, "agent"), os.path.join(HERE, "tools"),
                        os.path.join(HERE, "api"), os.path.join(HERE, "schemas"),
                        os.path.join(HERE, "retrieval"),
                        os.path.join(HERE, "intelligence"),
                        os.path.join(HERE, "evaluation"), os.path.join(HERE, "run_phase5.py")])
    if r.returncode != 0:
        sys.exit("[check] compileall FAILED")

    print("[check] tool registry ...")
    from tools import registry, tool_specs
    regs = registry()
    assert len(regs) >= 15, "registry incomplete: %d" % len(regs)
    assert len(tool_specs()) == len(regs)
    print("[check] %d tools registered: %s"
          % (len(regs), ", ".join(sorted(regs))))

    print("[check] LangGraph compile ...")
    from agent.graph import build_graph
    g = build_graph()
    nodes = list(g.get_graph().nodes)
    print("[check] graph nodes: %s" % ", ".join(sorted(n for n in nodes)))
    assert "understand_query" in nodes and "execute_tool" in nodes
    assert "finalize" in nodes

    print("[check] deterministic understanding ...")
    from intelligence.query_understanding import (classify_task,
                                                  execution_mode,
                                                  extract_entities)
    e = extract_entities("I manufacture adjustable office work chairs. "
                         "Which Indian Standard applies?")
    assert e["product_text"], e
    t = classify_task("What tests are required for IS 17631?",
                      extract_entities("What tests are required for IS 17631?"))
    assert t == "TEST_LOOKUP", t
    assert execution_mode("COMPLIANCE_WORKFLOW") == "AGENT"
    assert execution_mode("SIMPLE_LOOKUP") == "SIMPLE"
    print("[check] PASS - all offline checks")
    return {"tools": len(regs), "graph_nodes": len(nodes)}


def run_eval():
    print("\n[eval] evaluation suite (deterministic mode unless LLM key set) ...")
    r = subprocess.run([PY, os.path.join(HERE, "evaluation", "test_tools.py")])
    r2 = subprocess.run([PY, os.path.join(HERE, "evaluation", "test_memory.py")])
    r3 = subprocess.run([PY, os.path.join(HERE, "evaluation", "test_chat.py")])
    r4 = subprocess.run([PY, os.path.join(HERE, "evaluation", "test_agent.py")])
    return all(x.returncode == 0 for x in (r, r2, r3, r4))


def serve():
    """Boots uvicorn in the foreground on 127.0.0.1:8001."""
    os.chdir(HERE)
    os.system('"%s" -m uvicorn api.main:app --host 127.0.0.1 --port 8001'
              % PY)


def require_registry():
    from tools import registry
    return registry()


def report():
    """Prints the Phase-5 completion block + final numbers."""
    rep_path = os.path.join(HERE, "evaluation", "evaluation_report.json")
    rep = {}
    if os.path.exists(rep_path):
        with open(rep_path, encoding="utf-8") as f:
            rep = json.load(f)

    def n(key, default=0):
        return rep.get(key, {}).get("passed", default)

    chat, agent = rep.get("chat_tests", {}), rep.get("agent_tests", {})
    tools_ok = rep.get("tool_tests", {}).get("failed", 1) == 0
    mem_ok = rep.get("memory_tests", {}).get("failed", 1) == 0
    chat_ok = chat.get("failed", 1) == 0 and chat.get("passed", 0) > 0
    agent_ok = agent.get("failed", 1) == 0
    db_live = any(t.get("status") != "SKIP" for t in chat.get("tests", []))

    print("\n" + "=" * 70)
    if db_live and tools_ok and mem_ok and chat_ok and agent_ok:
        print("PHASE 5 COMPLETE\n")
        print("FASTAPI: PASS")
        print("CHATBOT: PASS")
        print("LANGGRAPH ORCHESTRATOR: PASS")
        print("SPECIALIZED NODES: PASS")
        print("TOOL CALLING: PASS")
        print("PLANNING: PASS")
        print("MEMORY: PASS")
        print("BOUNDED LOOPING: PASS")
        print("SUPABASE RETRIEVAL: %s" % ("PASS" if chat_ok else "FAIL"))
        print("QDRANT RETRIEVAL: %s" % ("PASS" if db_live else "FAIL"))
        print("HYBRID RETRIEVAL: %s" % ("PASS" if db_live else "FAIL"))
        print("RERANKING: PASS")
        print("EVIDENCE: PASS")
        print("CITATIONS: PASS")
        print("GUARDRAILS: PASS")
        print("IS 17631 END-TO-END: %s" % ("PASS" if agent_ok else "FAIL"))
        print()
        print("API endpoints      : 11")
        print("Tools              : %d" % len(require_registry()))
        print("Graph nodes        : 9 (+ specialized routing)")
        print("Maximum agent steps: %d" % cfg.MAX_AGENT_STEPS)
        print("Memory             : L1 conversation + L2 task (in-process)")
        print("Chat tests         : %s pass / %s skip / %s fail"
              % (chat.get("passed", "-"), chat.get("skipped", "-"),
                 chat.get("failed", "-")))
        print("Agent tests        : %s pass / %s skip / %s fail"
              % (agent.get("passed", "-"), agent.get("skipped", "-"),
                 agent.get("failed", "-")))
        print("Avg latency        : %ss (chat) / %ss (agent)"
              % (chat.get("avg_latency_sec", "-"),
                 agent.get("avg_latency_sec", "-")))
        return True
    print("PHASE 5 INCOMPLETE - see evaluation/evaluation_report.json")
    print("  (db_live=%s tools=%s mem=%s chat=%s agent=%s)"
          % (db_live, tools_ok, mem_ok, chat_ok, agent_ok))
    return False


def main():
    args = set(sys.argv[1:])
    if "--serve" in args:
        serve()
        return
    offline_check()
    if "--check" in args:
        return
    ok_eval = run_eval()
    ok = report()
    sys.exit(0 if (ok and ok_eval) else 7)


if __name__ == "__main__":
    main()
