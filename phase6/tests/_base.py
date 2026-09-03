"""Phase-6 test base: fixture paths + DB availability + validation writer."""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))          # workspace root
# phase6 first (config/tools/agent resolution), phase5 second
sys.path.insert(0, os.path.join(ROOT, "phase5"))
sys.path.insert(0, os.path.dirname(HERE))              # phase6/

FIXTURES = os.path.join(HERE, "fixtures")


class SkipTest(Exception):
    """Raised when a live dependency (DB configured but not yet loaded) makes
    the test unrunnable - recorded as SKIP, not FAIL."""


def bis_db_loaded():
    """True when Supabase is configured AND actually holds BIS rows."""
    if not db_available():
        return False
    try:
        from tools._shared import supabase
        with supabase().impl.conn.cursor() as cur:
            cur.execute("SELECT 1 FROM bis.is_master LIMIT 1")
            return cur.fetchone() is not None
    except Exception:
        return False


def db_available():
    import config as cfg
    cfg.load_env()
    return bool(os.environ.get("SUPABASE_DATABASE_URL")
                and os.environ.get("QDRANT_URL"))


def record(tag, summary):
    """Merge one section into tests/PHASE6_VALIDATION.json."""
    path = os.path.join(HERE, "PHASE6_VALIDATION.json")
    data = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            try:
                data = json.load(f)
            except Exception:
                data = {}
    data[tag] = summary
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    return path


def run_cases(tag, cases):
    """cases = [(name, fn)] -> PASS/FAIL/SKIP lines + section record."""
    out, t0 = [], time.time()
    passed = failed = skipped = 0
    for name, fn in cases:
        t1 = time.time()
        try:
            err = fn()
            status = "PASS" if not err else "FAIL"
        except SystemExit as e:
            err, status = "credentials missing (exit %s)" % e.code, "SKIP"
        except SkipTest as e:
            err, status = str(e)[:150], "SKIP"
        except Exception as e:
            err, status = "%s: %s" % (type(e).__name__, str(e)[:150]), "FAIL"
        if status == "PASS":
            passed += 1
        elif status == "SKIP":
            skipped += 1
        else:
            failed += 1
        out.append({"name": name, "status": status,
                    "detail": (err or "")[:160],
                    "latency_sec": round(time.time() - t1, 2)})
        print("  %-34s %s%s" % (name, status,
                                (" | " + str(err)[:90]) if err else ""))
    summary = {"tests": out, "passed": passed, "failed": failed,
               "skipped": skipped,
               "avg_latency_sec": round((time.time() - t0) / len(cases), 2),
               "db_live": db_available()}
    path = record(tag, summary)
    print("[%s] %d pass, %d skip, %d fail -> %s"
          % (tag, passed, skipped, failed, path))
    return failed == 0
