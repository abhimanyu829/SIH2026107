"""Validates the Qdrant Cloud side. Read-only; safe to re-run.

Checks: connection, collection exists, vector dimension, distance metric,
point count vs Phase-3 chunk count, payload presence, point-id uniqueness,
and one real semantic search. Writes the "qdrant" section of
validation/PHASE4_VALIDATION.json and exits non-zero on any failure.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402

SAMPLE_QUERY = "office work chairs specification IS 17631"
SCROLL_PAGE = 1000


def validate():
    from connect import get_client
    from embed_and_upsert import load_chunks
    from retrieval.qdrant_retriever import embed_query  # shared model loader

    print("[qdrant-validate] connecting ...")
    client = get_client()
    r = {"target": config.redact(os.environ.get("QDRANT_URL", "")),
         "collection": config.QDRANT_COLLECTION, "checks": {}}

    def record(name, passed, detail=""):
        r["checks"][name] = {"pass": bool(passed), "detail": str(detail)}
        print("  %-28s %s%s" % (name, "PASS" if passed else "FAIL",
                                ("  " + str(detail)) if detail else ""))
        return passed

    # 1. collection + config
    try:
        info = client.get_collection(config.QDRANT_COLLECTION)
    except Exception as e:
        record("collection_exists", False, e)
        return finish(r, False)
    record("collection_exists", True, "status=%s" % info.status)
    size = _vsize(info)
    dist = _dist(info)
    record("vector_dimension", size == config.VECTOR_SIZE, "%s-dim" % size)
    record("distance_metric", str(dist).upper().startswith("COS"),
           "configured=%s" % dist)

    # 2. point count vs frozen chunk count
    chunks = load_chunks()
    expected = len(chunks)
    count = client.count(collection_name=config.QDRANT_COLLECTION, exact=True).count
    record("point_count_vs_chunks", count == expected,
           "points=%d chunks=%d" % (count, expected))

    # 3. point ids on the server vs deterministic ids from the JSONL
    want = {config.point_id(cid) for cid, _ in chunks}
    have, offset = set(), None
    while True:
        points, offset = client.scroll(collection_name=config.QDRANT_COLLECTION,
                                       limit=SCROLL_PAGE, with_payload=False,
                                       offset=offset)
        have.update(str(p.id) for p in points)
        if not offset:
            break
    record("point_id_uniqueness", len(have) == count,
           "distinct=%d count=%d" % (len(have), count))
    record("point_id_coverage", have == want,
           "missing=%d extra=%d" % (len(want - have), len(have - want)))

    # 4. payload presence - scroll a page with payload, verify the fields
    #    retrieval depends on exist and are non-empty on every sampled point
    pts, _ = client.scroll(collection_name=config.QDRANT_COLLECTION,
                           limit=25, with_payload=True)
    bad = [p.payload.get("chunk_id") for p in pts
           if not p.payload.get("chunk_id") or not p.payload.get("content")]
    record("payload_presence", len(pts) == 25 and not bad,
           "sampled=%d bad=%d" % (len(pts), len(bad)))

    # 5. sample semantic search over the embedded query
    try:
        t0 = time.time()
        vec = embed_query(SAMPLE_QUERY)
        hits = client.query_points(collection_name=config.QDRANT_COLLECTION,
                                   query=vec, limit=3, with_payload=True).points
        top = hits[0] if hits else None
        record("semantic_search", bool(top) and top.score > 0.25,
               "top=%.3f '%s' in %.1fs" % (top.score if top else 0,
               (top.payload.get("title") or top.payload.get("canonical_is_number")
                or "")[:40] if top else "-", time.time() - t0))
        r["sample_search"] = {"query": SAMPLE_QUERY,
                              "top_score": top.score if top else None,
                              "top_payload": {k: top.payload.get(k) for k in
                                              ("chunk_id", "document_type", "title",
                                               "canonical_is_number")}
                              if top else None}
    except Exception as e:
        record("semantic_search", False, e)

    return finish(r, all(c["pass"] for c in r["checks"].values()))


def finish(r, all_ok):
    r["pass"] = bool(all_ok)
    path = config.merge_validation("qdrant", r)
    print("[qdrant-validate] %s -> %s" % ("PASS" if all_ok else "FAIL", path))
    if not all_ok:
        sys.exit(6)
    return r


def _vsize(info):
    try:
        return info.config.params.vectors.size
    except Exception:
        return None


def _dist(info):
    try:
        return info.config.params.vectors.distance
    except Exception:
        return None


if __name__ == "__main__":
    validate()
