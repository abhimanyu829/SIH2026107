"""test_agent.py - the /api/agent/run path (AGENT mode cases)."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _base import check_case, db_available, evaluate, run_agent


def runner(case):
    results, fails = [], []
    cid = "agent-%d" % case["id"]
    case = dict(case)
    # /api/agent/run always executes the agentic path; mode assertions
    # belong to the chat suite only
    case.pop("expect_mode", None)
    if "steps" in case:
        for st in case["steps"]:
            r = run_agent(st["q"], cid=cid)
            results.append(r)
    else:
        if case.get("conversation_seed"):
            run_agent(case["conversation_seed"], cid=cid)
        results = [run_agent(case["query"], cid=cid)]
    fails.extend(check_case(case, results))
    # agent-specific invariants
    if results and db_available():
        n_steps = len([s for s in results[-1].get("steps", [])])
        import config as cfg
        if n_steps > 2 * cfg.MAX_AGENT_STEPS:
            fails.append("unbounded loop: %d trace entries" % n_steps)
        if results[-1].get("status") not in ("COMPLETED", "UNKNOWN",
                                             "REQUIRES_REVIEW"):
            fails.append("bad status %s" % results[-1].get("status"))
    return results, fails


if __name__ == "__main__":
    evaluate("agent_tests", runner)
