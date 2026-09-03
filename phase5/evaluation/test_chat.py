"""test_chat.py - the /api/chat path (SIMPLE mode cases)."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _base import check_case, db_available, evaluate, run_chat


def runner(case):
    results, fails = [], []
    cid = "chat-%d" % case["id"]
    if "steps" in case:
        for st in case["steps"]:
            r = run_chat(st["q"], cid=cid)
            results.append(r)
            if "expect_answer_contains" in st and db_available():
                for s in st["expect_answer_contains"]:
                    if s.lower() not in r["answer"].lower():
                        fails.append("answer missing '%s'" % s)
            if "expect_answer_contains_any" in st and db_available():
                if not any(s.lower() in r["answer"].lower() for s in
                           st["expect_answer_contains_any"]):
                    fails.append("answer missing any of %s"
                                 % st["expect_answer_contains_any"])
    else:
        if case.get("conversation_seed"):
            run_chat(case["conversation_seed"], cid=cid)
        results = [run_chat(case["query"], cid=cid)]
    fails.extend(check_case(case, results))
    return results, fails


if __name__ == "__main__":
    evaluate("chat_tests", runner)
