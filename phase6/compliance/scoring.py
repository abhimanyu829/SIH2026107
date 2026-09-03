"""Readiness scoring (spec section 18). PASS counts, GAP/UNKNOWN don't.
Named 'Compliance Readiness Score' - never an official BIS compliance score."""
from collections import Counter


def score(results):
    """results -> {score, total, passed, gaps, unknown, label, by_type}."""
    c = Counter(r["decision"] for r in results)
    total = len(results)
    passed = c.get("PASS", 0)
    return {
        "score": int(round(100.0 * passed / total)) if total else 0,
        "total": total,
        "passed": passed,
        "gaps": c.get("GAP", 0),
        "unknown": c.get("UNKNOWN", 0),
        "label": "Compliance Readiness Score",
        "by_type": _by_type(results),
    }


def _by_type(results):
    out = {}
    for r in results:
        t = r.get("type") or "OTHER"
        d = out.setdefault(t, {"total": 0, "PASS": 0, "GAP": 0, "UNKNOWN": 0})
        d["total"] += 1
        d[r["decision"]] += 1
    return out


def gaps(results):
    """GAP + UNKNOWN items for the gap-analysis section (spec 19)."""
    return [r for r in results if r["decision"] in ("GAP", "UNKNOWN")]
