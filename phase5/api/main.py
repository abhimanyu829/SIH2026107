"""FastAPI app: BIS intelligent assistant backend. 11 endpoints, nothing more.

Runs with or without an LLM key (deterministic mode) and fails fast with a
clear message when Supabase/Qdrant credentials are missing - a Phase-5
connection problem never touches earlier phases.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config as cfg  # noqa: E402

from api import routes_agent, routes_chat, routes_lookup, routes_search  # noqa: E402

app = FastAPI(
    title="BIS SIH26107 Intelligent Assistant",
    description="Phase-5 backend: single LangGraph orchestrator over Supabase "
                "PostgreSQL + Qdrant Cloud. No frontend here.",
    version="1.0.0")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
    allow_headers=["*"])   # local prototype; frontend connects later

app.include_router(routes_chat.router, prefix="/api")
app.include_router(routes_agent.router, prefix="/api")
app.include_router(routes_search.router, prefix="/api")
app.include_router(routes_lookup.router, prefix="/api")


@app.get("/api/health")
def health():
    """Liveness + dependency readiness, secrets-free."""
    out = {"status": "ok", "phase": 5,
           "llm": "configured" if cfg.llm_configured() else "deterministic-mode",
           "supabase": _probe("pg"), "qdrant": _probe("qd")}
    out["status"] = "ok" if (out["supabase"]["ok"] and out["qdrant"]["ok"]) \
        else "degraded"
    return out


def _probe(which):
    """Cheap connectivity probe; never raises, never prints secrets."""
    try:
        if which == "pg":
            from tools._shared import supabase
            conn = supabase().impl.conn   # psycopg2: execute lives on cursors
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
            cur.close()
            return {"ok": True}
        from tools._shared import qdrant
        qdrant().impl.client.get_collections()
        return {"ok": True}
    except SystemExit as e:
        return {"ok": False, "reason": "credentials missing", "exit": e.code}
    except Exception as e:
        return {"ok": False, "reason": str(type(e).__name__)}
