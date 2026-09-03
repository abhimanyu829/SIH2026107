"""Phase-6 config: reuses Phase-5 config wholesale, adds only compliance
knobs. No new databases, no new services."""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)                       # workspace root
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_ROOT, "phase5"))
sys.path.insert(0, os.path.join(_ROOT, "phase4"))

# Phase-5 config is the base (env loading, LLM settings, DB knobs).
# Loaded BY PATH under its own name: phase6 also has a config.py, so a plain
# `import config` inside THIS module would import itself.
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "phase5_config", os.path.join(_ROOT, "phase5", "config.py"))
base = importlib.util.module_from_spec(_spec)
sys.modules["phase5_config"] = base
_spec.loader.exec_module(base)

load_env = base.load_env
llm_configured = base.llm_configured
llm_complete = None   # filled lazily from phase5.intelligence

# Phase-6 storage: simple local dirs, nothing cloud, nothing enterprise.
DATA_DIR = os.path.join(_HERE, "data")
UPLOADS_DIR = os.path.join(DATA_DIR, "audits")
AUDITS_INDEX = os.path.join(DATA_DIR, "audits_index.json")

MAX_FILE_MB = 20                       # upload size limit
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".txt", ".png", ".jpg",
                      ".jpeg"}
# OCR fallback is only attempted when text extraction is empty/insufficient.
OCR_ENABLED = bool(os.environ.get("TESSERACT_CMD") or
                   os.path.exists(r"C:\Program Files\Tesseract-OCR\tesseract.exe"))
MIN_TEXT_CHARS = 40                     # below this a PDF page goes to OCR

DOCUMENT_CATEGORIES = (
    "CALIBRATION_CERTIFICATE", "TEST_REPORT", "FACTORY_DOCUMENT",
    "QC_DOCUMENT", "RAW_MATERIAL_DOCUMENT", "PROCESS_DOCUMENT",
    "MACHINERY_DOCUMENT", "OTHER",
)

DECISIONS = ("PASS", "GAP", "UNKNOWN")

# ---- passthrough of Phase-5 knobs -------------------------------------------
# Phase-5 modules do `import config` and read these; when running from phase6,
# sys.modules['config'] is THIS module, so re-export everything they need.
LLM_MODEL = getattr(base, "LLM_MODEL", "gpt-4o-mini")
LLM_BASE_URL = getattr(base, "LLM_BASE_URL", "")
LLM_TEMPERATURE = getattr(base, "LLM_TEMPERATURE", 0.1)
QDRANT_COLLECTION = getattr(base, "QDRANT_COLLECTION", "bis_knowledge")
QDRANT_LIMIT = getattr(base, "QDRANT_LIMIT", 10)
RERANK_TOP = getattr(base, "RERANK_TOP", 6)
MEMORY_TURNS = getattr(base, "MEMORY_TURNS", 12)
CACHE_TTL = getattr(base, "CACHE_TTL", 300)
MAX_AGENT_STEPS = getattr(base, "MAX_AGENT_STEPS", 8)


def get(key, default=None):
    """Env passthrough to the Phase-5 getter (reads .env chain)."""
    base.load_env()
    v = os.environ.get(key, "")
    return v if v else default


def llm_complete_cached(system, prompt, max_tokens=500):
    """Phase-5 LLM call (deterministic fallback returns None)."""
    global llm_complete
    if llm_complete is None:
        try:
            from intelligence.response_builder import llm_complete as f
            llm_complete = f
        except Exception as e:
            sys.stderr.write("[phase6 config] LLM import failed: %s: %s\n"
                             % (type(e).__name__, str(e)[:120]))
            llm_complete = lambda *a, **k: None
    if not base.llm_configured():
        return None
    try:
        return llm_complete(system, prompt, max_tokens=max_tokens)
    except Exception as e:
        sys.stderr.write("[phase6 config] LLM call failed: %s: %s\n"
                         % (type(e).__name__, str(e)[:120]))
        return None


def merge_validation(key, obj):
    """Same pattern as Phase 4/5: one JSON per phase section."""
    os.makedirs(os.path.join(_HERE, "tests"), exist_ok=True)
    path = os.path.join(_HERE, "tests", "PHASE6_VALIDATION.json")
    data = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            try:
                data = json.load(f)
            except Exception:
                data = {}
    data[key] = obj
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    return path


import json  # noqa: E402  (used by merge_validation above at call time)
