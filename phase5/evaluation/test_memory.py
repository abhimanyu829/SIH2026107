"""test_memory.py - L1 conversation memory + L2 task memory behaviour."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _base import db_available, evaluate


def runner(case):
    from agent import memory
    fails, results = [], []
    memory.clear("mem-test")
    memory.remember_message("mem-test", "user", "I manufacture office work chairs.")
    ents = memory.resolve_entities("mem-test", {"is_number": "17631"})
    if ents.get("is_number") != "17631":
        fails.append("entity not remembered")
    memory.remember_message("mem-test", "user", "Which standard applies?")
    ctx = memory.context_for("mem-test")
    if not any("chair" in (m.get("text") or "") for m in ctx["messages"]):
        fails.append("L1 message missing")
    if memory.select_standard("mem-test") != "17631":
        fails.append("selected IS not remembered")
    memory.remember_task("mem-test", "TEST_LOOKUP", ["get_tests"], [], [],
                         [{"evidence_id": "CHK-1"}])
    if memory.context_for("mem-test")["task"].get("type") != "TEST_LOOKUP":
        fails.append("L2 task memory missing")
    # new conversation must NOT inherit another conversation's memory
    if memory.select_standard("other-conv") == "17631":
        fails.append("memory leaked across conversations")
    results.append({"answer": "memory ok"})
    return results, fails


if __name__ == "__main__":
    evaluate("memory_tests", runner)
