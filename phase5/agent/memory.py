"""Simple two-level memory. Conversation (L1) + task (L2) in one process-wide
dict. No vector store, no persistence beyond the process, no personal data.

L1 remembers: recent messages, active topic, resolved entities (product,
selected IS number).
L2 remembers: task type, plan, completed/pending steps, evidence - bound to a
conversation id so a follow-up like "which labs can do them?" resolves "them"
against the remembered tests of the remembered IS number.
"""
import time

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as cfg  # noqa: E402

_STORE = {}


def _conv(cid):
    cid = cid or "default"
    if cid not in _STORE:
        _STORE[cid] = {"created": time.time(), "messages": [],
                       "topic": "", "resolved": {}, "task": {}}
    return _STORE[cid]


def remember_message(cid, role, text):
    c = _conv(cid)
    c["messages"].append({"role": role, "text": (text or "")[:2000],
                          "ts": time.time()})
    c["messages"] = c["messages"][-2 * cfg.MEMORY_TURNS:]
    if role == "user":
        c["topic"] = (text or "")[:120]


def resolve_entities(cid, entities):
    """Merges new entities over remembered ones (new wins when present).

    Keys the new extraction produced with empty values fall back to memory;
    all original keys survive (classify_task reads e['comparison'] etc.).
    """
    c = _conv(cid)
    out = {}
    for k, v in (entities or {}).items():
        remembered = c["resolved"].get(k)
        if v in (None, "", [], False) and remembered not in (None, "", [], False):
            out[k] = remembered
        else:
            if v not in (None, "", [], False):
                c["resolved"][k] = v
            out[k] = v
    return out


def remember_task(cid, task_type, plan, completed, pending, evidence):
    c = _conv(cid)
    c["task"] = {"type": task_type, "plan": plan, "completed": completed,
                 "pending": pending, "evidence": evidence[:5],
                 "ts": time.time()}


def remember_resolved(cid, entities):
    """Write-back of entity values the CURRENT turn resolved (e.g. an IS
    number a tool found mid-flight) so bare follow-ups like 'which standard
    applies?' inherit them. Pure additive merge, new values win."""
    c = _conv(cid)
    for k, v in (entities or {}).items():
        if v not in (None, "", [], False):
            c["resolved"][k] = v
    return dict(c["resolved"])


def context_for(cid):
    """Memory snapshot for a new request: last messages + resolved entities."""
    c = _conv(cid)
    return {"messages": c["messages"][-cfg.MEMORY_TURNS:],
            "topic": c["topic"], "resolved": dict(c["resolved"]),
            "task": dict(c["task"])}


def select_standard(cid):
    """Most recently resolved IS number for a conversation (or None)."""
    r = _conv(cid)["resolved"]
    return r.get("is_number")


def clear(cid=None):
    if cid is None:
        _STORE.clear()
    else:
        _STORE.pop(cid, None)
