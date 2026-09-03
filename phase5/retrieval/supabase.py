"""Supabase retrieval facade for Phase 5.

Thin wrapper over phase4/retrieval/postgres_retriever.py - Phase 5 adds no
SQL of its own and never lets the LLM touch the database. One process-wide
instance, plus a TTL cache for hot lookups (no Redis - just a dict).
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))          # workspace root
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "phase5"))

import config as cfg  # noqa: E402  (phase5 config)
from ._phase4_loader import (load_phase4_connect,  # noqa: E402
                             load_phase4_module)

_pg = None


def _impl():
    """phase4's PostgresRetriever, loaded by path (name collision-free).

    supabase.connect is preloaded with phase4's config bound: postgres_retriever
    does 'from supabase.connect import connect' at module import time.
    """
    global _pg
    if _pg is None:
        load_phase4_connect("supabase", "supabase.connect")
        _pg = load_phase4_module("retrieval/postgres_retriever.py",
                                 "phase4_postgres_retriever")
    return _pg


class _Cache:
    """Minimal TTL cache: {(kind, key): (timestamp, value)}."""

    def __init__(self, ttl):
        self.ttl, self.store = ttl or 300, {}

    def get(self, k, now):
        hit = self.store.get(k)
        return hit[1] if hit and now - hit[0] < self.ttl else None

    def put(self, k, v, now):
        self.store[k] = (now, v)


class SupabaseRetriever:
    """Same PostgresRetriever as Phase 4, with process-wide reuse + caching.

    The first real query pays the connection cost (config errors surface
    there, handled by the tool layer's SystemExit guard).
    """

    def __init__(self, ttl=None):
        import time
        self._time = time
        self.impl = _impl().PostgresRetriever()
        self.cache = _Cache(ttl if ttl is not None else cfg.CACHE_TTL)

    def _cached(self, kind, key, fn):
        now = self._time.time()
        k = (kind, str(key))
        v = self.cache.get(k, now)
        if v is None:
            v = fn()
            self.cache.put(k, v, now)
        return v

    # ---- cached hot paths -------------------------------------------------
    def find_standard(self, is_number, year=None):
        return self._cached("std", (is_number, year),
                            lambda: self.impl.find_standard(is_number, year))

    def standards_for_product(self, product_id):
        return self._cached("std_prod", product_id,
                            lambda: self.impl.standards_for_product(product_id))

    def search_products(self, term):
        return self._cached("prod", term, lambda: self.impl.search_products(term))

    # ---- pass-through (relationship traversal, low reuse value) ----------
    def products(self, is_id):
        return self.impl.products(is_id)

    def qcos(self, is_id):
        return self.impl.qcos(is_id)

    def schemes(self, is_id):
        return self.impl.schemes(is_id)

    def tests(self, is_id):
        return self.impl.tests(is_id)

    def manuals(self, is_id):
        return self.impl.manuals(is_id)

    def labs(self, is_id, limit=25):
        return self.impl.labs(is_id, limit)

    def search_standards(self, term, limit=5):
        return self.impl.search_standards(term, limit)

    def structured_lookup(self, query, context_is_number=None):
        return self.impl.structured_lookup(query, context_is_number)

    def close(self):
        self.impl.close()
