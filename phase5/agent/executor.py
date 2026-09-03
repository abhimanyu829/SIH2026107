"""Executor: runs plan steps one at a time through the tool registry.

- recomputes each step's args at execution time (the IS number may only
  become known mid-workflow);
- after a step resolves the standard, extends the plan with the now-usable
  steps (qco, scheme, manual, tests, labs) - never guessing, never exceeding
  MAX_AGENT_STEPS total tool calls;
- records a tool_call + tool_result + trace entry per step;
- handles failures: one retry only when the tool says retry helps (never a
  loop), otherwise the step is recorded failed and the workflow continues.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as cfg  # noqa: E402

from tools import call  # noqa: E402


def run_step(step, entities, ctx, state_lists):
    """Executes one plan step. Mutates ctx (is/product), returns the
    tool_result dict or a synthetic failure result. Never raises."""
    from agent.planner import STEPS
    name = step["name"]
    try:
        args = STEPS[name][1](dict(entities), ctx)
    except Exception:
        args = dict(step.get("args") or {})
    # drop empty-string args the tools would choke on
    args = {k: v for k, v in args.items() if v not in ("", None)}
    result = call(step["tool"], **args)
    if not result["ok"] and step.get("retried") is not True and \
            _retry_helps(result):
        step["retried"] = True
        result = call(step["tool"], **args)
    return result


def _retry_helps(result):
    """Retry only transient-looking failures; argument errors never retry."""
    err = (result.get("error") or "").lower()
    return any(w in err for w in ("timeout", "connection", "temporarily"))


def harvest(result, entities, ctx):
    """Pulls newly resolved facts out of a tool result (deterministic only)."""
    data = result.get("data") if result.get("ok") else None
    if not data:
        return
    tool = result.get("tool")
    if tool == "find_product" and isinstance(data, list) and data:
        ctx["product"] = data[0].get("product_name")
        ctx["product_id"] = data[0].get("product_id")
    elif tool in ("search_standards", "get_standard") and data:
        row = data[0] if isinstance(data, list) else data
        num = row.get("canonical_is_number") or row.get("display_is_number")
        isnum = row.get("is_id")
        if num or isnum:
            ctx["is"] = ctx.get("is") or num
            entities.setdefault("is_number", _digits(num) if num else None)
        if isinstance(data, list) and data and not ctx.get("is"):
            ctx["candidates"] = [d.get("canonical_is_number") for d in data[:3]
                                 if d.get("canonical_is_number")]


def _digits(s):
    out = "".join(ch for ch in str(s or "") if ch.isdigit())
    return out or None


def usable_after_resolution(task, entities, done_names):
    """Template steps that became usable once an IS number is known."""
    from agent.planner import PLAN_TEMPLATES, _usable
    out = []
    for n in PLAN_TEMPLATES.get(task, []):
        if n in done_names or n in ("identify_product", "identify_standard",
                                    "get_standard"):
            continue
        if _usable(n, entities, entities.get("_query", "")):
            out.append(n)
    return out
