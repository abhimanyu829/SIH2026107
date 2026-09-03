"""Phase-5 shared config: paths, env loading, LLM + retrieval knobs.

Mirrors phase4/config.py deliberately: no framework, no settings magic - just
the environment, the frozen Phase-4 constants, and a few knobs. Secrets are
never printed; load_env() is idempotent and never overwrites real env vars.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                      # workspace root
PHASE4 = os.path.join(ROOT, "phase4")            # Phase-4 code, reused as a library
sys.path.insert(0, PHASE4)

MAX_AGENT_STEPS = 8                              # hard loop bound (spec)
DEFAULT_LANGUAGE = "en"

# ---------------------------------------------------------------------------
def load_env(path=None):
    """Reads phase5/.env (then phase4/.env) into os.environ; never overwrites."""
    read_any = False
    for p in (path or os.path.join(HERE, ".env"),
              os.path.join(PHASE4, ".env")):
        if not os.path.exists(p):
            continue
        read_any = True
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v
    os.environ.setdefault("HF_HOME", os.path.join(PHASE4, ".hf_cache"))
    return read_any


def get(name, default=""):
    load_env()
    v = os.environ.get(name, "").strip()
    return v or default


def llm_configured():
    """True when an LLM endpoint is configured; False = deterministic mode."""
    load_env()
    return bool(os.environ.get("LLM_API_KEY", "").strip()
                or os.environ.get("OPENAI_API_KEY", "").strip())


def merge_validation(key, obj):
    """Merges one section into evaluation/evaluation_report.json."""
    import datetime
    import json
    path = os.path.join(HERE, "evaluation", "evaluation_report.json")
    data = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    data[key] = obj
    data.setdefault("phases", {})["phase5"] = {
        "updated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    return path


# Retrieval knobs (inherit Phase-4 collection; same Qdrant cluster + Supabase)
QDRANT_COLLECTION = get("QDRANT_COLLECTION", "bis_knowledge")
QDRANT_LIMIT = int(get("QDRANT_LIMIT", "10"))         # semantic candidates
RERANK_TOP = int(get("RERANK_TOP", "6"))               # evidence set size
LLM_MODEL = get("LLM_MODEL", "gpt-4o-mini")
LLM_BASE_URL = get("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_TEMPERATURE = float(get("LLM_TEMPERATURE", "0.1"))
MEMORY_TURNS = int(get("MEMORY_TURNS", "12"))          # conversation window
CACHE_TTL = int(get("CACHE_TTL", "300"))               # seconds, lookup cache
