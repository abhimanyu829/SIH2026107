"""Shared, deliberately tiny: paths, .env loading, secret redaction.

Kept in one place so the eight Phase-4 scripts do not each re-implement it. No framework,
no abstraction layer - three functions and a few constants.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# Phase-3 outputs are read-only inputs to Phase 4. Override with PHASE3_DATA_DIR.
DATA_DIR = os.environ.get("PHASE3_DATA_DIR") or os.path.join(
    os.path.dirname(HERE), "BIS_SIH26107_DATA")
SQL_DIR = os.path.join(HERE, "sql")
VALIDATION_DIR = os.path.join(HERE, "validation")
MANIFEST = os.path.join(DATA_DIR, "POSTGRES_READY", "TABLE_MANIFEST.csv")
FROZEN_DDL = os.path.join(DATA_DIR, "POSTGRES_READY", "DDL.sql")
CHUNKS = os.path.join(DATA_DIR, "QDRANT_READY", "qdrant_chunks.jsonl")
PG_SCHEMA = "bis"


def load_env(path=None):
    """Reads phase4/.env into os.environ without overwriting anything already set.

    python-dotenv is not required; the file format is KEY=VALUE, # comments allowed.
    """
    path = path or os.path.join(HERE, ".env")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v
    # HuggingFace cache inside the workspace: the BGE-M3 download stays with the
    # project (and sandbox-friendly). Set HF_HOME yourself to use a global cache.
    os.environ.setdefault("HF_HOME", os.path.join(HERE, ".hf_cache"))
    return True


def require(name, hint=""):
    """Returns an environment variable or exits with a clear, secret-free message."""
    load_env()
    v = os.environ.get(name, "").strip()
    if not v:
        sys.stderr.write(
            "\n[CONFIG ERROR] %s is not set.\n"
            "  Copy phase4/.env.example to phase4/.env and fill it in.%s\n"
            % (name, ("\n  " + hint) if hint else ""))
        sys.exit(2)
    return v


def redact(url):
    """A loggable form of a URL: scheme, host, port, path. Never the credentials.

    Used everywhere instead of printing the connection string, so no password or API
    key can reach a log, a terminal transcript or a screenshot.
    """
    if not url:
        return "<unset>"
    try:
        from urllib.parse import urlsplit
        p = urlsplit(url)
        host = p.hostname or "?"
        port = (":%d" % p.port) if p.port else ""
        user = ("%s:***@" % p.username) if p.username else ""
        return "%s://%s%s%s%s" % (p.scheme or "?", user, host, port, p.path or "")
    except Exception:
        return "<unparseable url, redacted>"


EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-m3")
QDRANT_COLLECTION = os.environ.get("QDRANT_COLLECTION", "bis_knowledge")
VECTOR_SIZE = 1024          # BAAI/bge-m3 dense dimension
DISTANCE = "Cosine"
EXPECTED_CHUNKS = 45523     # Phase-3 QDRANT_READY/README.md
EXPECTED_TABLES = 50        # Phase-3 POSTGRES_READY/TABLE_MANIFEST.csv

# ------------------------- tunable knobs (all optional) -------------------
# CPU embedding of 45.5k chunks is the slow part; defaults keep it practical
# and resumable. Every value can be overridden in .env.
EMBEDDING_DEVICE = os.environ.get("EMBEDDING_DEVICE", "")  # "" = auto (cuda if free)
EMBEDDING_MAX_SEQ = int(os.environ.get("EMBEDDING_MAX_SEQ", "1024"))  # tokens
EMBEDDING_BATCH = int(os.environ.get("EMBEDDING_BATCH", "64"))        # texts per encode
EMBEDDING_SHARD = int(os.environ.get("EMBEDDING_SHARD", "512"))      # cache/upsert unit
UPSERT_BATCH = int(os.environ.get("UPSERT_BATCH", "256"))             # points per request
QDRANT_TIMEOUT = int(os.environ.get("QDRANT_TIMEOUT", "60"))          # seconds
QDRANT_PREFER_GRPC = os.environ.get("QDRANT_PREFER_GRPC", "0") == "1"
QDRANT_LIMIT = int(os.environ.get("QDRANT_LIMIT", "8"))               # semantic top-k
# Dotted prefix keeps every Phase-4 point id reproducible from chunk_id alone.
POINT_ID_NAMESPACE = "bis-sih26107-phase4/"


def point_id(chunk_id):
    """Deterministic UUID5 from chunk_id: re-running never duplicates a point."""
    import uuid
    return str(uuid.uuid5(uuid.NAMESPACE_URL, POINT_ID_NAMESPACE + chunk_id))


def merge_validation(key, obj):
    """Merges one section into validation/PHASE4_VALIDATION.json, creating or
    updating the file. Called by validate scripts and the smoke test."""
    import datetime
    import json
    path = os.path.join(VALIDATION_DIR, "PHASE4_VALIDATION.json")
    data = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    data[key] = obj
    data.setdefault("phases", {})["phase4"] = {
        "updated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    os.makedirs(VALIDATION_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return path
