"""Shared retrieval singletons for the tool layer.

One SupabaseRetriever, one QdrantFacade, one HybridRetriever per process;
tools fetch them here so a workflow never opens duplicate connections.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config as cfg  # noqa: E402

_singletons = {}


def supabase():
    if "pg" not in _singletons:
        from retrieval.supabase import SupabaseRetriever
        _singletons["pg"] = SupabaseRetriever(ttl=cfg.CACHE_TTL)
    return _singletons["pg"]


def qdrant():
    if "qd" not in _singletons:
        from retrieval.qdrant import QdrantFacade
        _singletons["qd"] = QdrantFacade()
    return _singletons["qd"]


def hybrid():
    if "hy" not in _singletons:
        from retrieval.hybrid import HybridRetriever
        _singletons["hy"] = HybridRetriever(supabase=supabase(),
                                            qdrant=qdrant())
    return _singletons["hy"]


def close_all():
    pg = _singletons.pop("pg", None)
    if pg:
        try:
            pg.close()
        except Exception:
            pass
    _singletons.pop("qd", None)
    _singletons.pop("hy", None)
