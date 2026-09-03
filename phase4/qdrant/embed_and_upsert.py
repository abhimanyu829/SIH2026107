"""Chunks in QDRANT_READY -> BGE-M3 vectors -> batch upsert to Qdrant Cloud.

Re-runnable and resumable:
  - point ids are UUID5(chunk_id), so upsert can never create duplicates;
  - embeddings are cached per shard under qdrant/.embeddings_cache/, so an
    interrupted run (or a re-run after a collection wipe) embeds only what is
    missing instead of paying the full CPU cost again;
  - the frozen JSONL order is the shard order, so shard N always holds the same
    chunks.

Cost model: one local BGE-M3 encode per chunk, zero LLM calls, zero paid APIs.

  python qdrant/embed_and_upsert.py            # full pipeline
  python qdrant/embed_and_upsert.py --check    # offline integrity check, no network
  python qdrant/embed_and_upsert.py --no-cache # embed fresh, ignore stored shards
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".embeddings_cache")

# Payload sent verbatim: every field of the Phase-3 chunk. page_start/page_end
# are the only integer fields, so "" becomes None there; text fields keep "".
INT_FIELDS = ("page_start", "page_end")
PAYLOAD_FIELDS = ("chunk_id", "document_id", "is_id", "canonical_is_number",
                  "document_type", "title", "section", "clause", "page_start",
                  "page_end", "breadcrumb", "content", "source_url", "version",
                  "effective_date", "sha256")


def load_chunks():
    """All frozen chunks as [(chunk_id, payload)], one pass, order = file order."""
    out = []
    with open(config.CHUNKS, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            o = json.loads(line)
            chunk_id = (o.get("chunk_id") or "").strip()
            if not chunk_id:
                sys.exit("[EMBED] line %d has no chunk_id - refusing to guess" % i)
            payload = {k: o.get(k, "") for k in PAYLOAD_FIELDS}
            for k in INT_FIELDS:
                v = str(payload.get(k) or "").strip()
                payload[k] = int(v) if v.isdigit() else None
            out.append((chunk_id, payload))
    return out


def shard_vecs(si, chunk_slice, use_cache):
    """Vectors for shard si: cache hit (ids must match), else fresh encode + save."""
    import numpy as np
    ids = [cid for cid, _ in chunk_slice]
    path = os.path.join(CACHE_DIR, "shard_%05d.npz" % si)
    if use_cache and os.path.exists(path):
        z = np.load(path, allow_pickle=False)
        if list(z["ids"]) == ids:
            return z["vecs"]
        print("  shard %d cache stale (chunk order changed) - re-embedding" % si)
    from retrieval.qdrant_retriever import embed_texts   # ONE shared encoder
    vecs = np.asarray(embed_texts([pl["content"] for _, pl in chunk_slice]),
                      dtype="float32")
    if use_cache:
        np.savez(path, ids=np.array(ids), vecs=vecs)
    return vecs


def embed_and_upsert(use_cache=True):
    from qdrant_client import models
    from connect import get_client

    chunks = load_chunks()
    total = len(chunks)
    if total != config.EXPECTED_CHUNKS:
        sys.exit("[EMBED] %s has %d chunks, Phase-3 README declares %d - "
                 "Phase 4 does not proceed against drifted inputs."
                 % (config.CHUNKS, total, config.EXPECTED_CHUNKS))

    client = get_client()
    try:
        info = client.get_collection(config.QDRANT_COLLECTION)
    except Exception as e:
        sys.exit("[EMBED] collection %s not reachable (%s) - run "
                 "qdrant/create_collection.py first" % (config.QDRANT_COLLECTION, e))
    size = _vsize(info)
    if size != config.VECTOR_SIZE:
        sys.exit("[EMBED] collection dimension mismatch: %s vs %d needed"
                 % (size, config.VECTOR_SIZE))

    shard = config.EMBEDDING_SHARD
    shards = (total + shard - 1) // shard
    print("[embed] %d chunks in %d shards of %d (batch %d, upsert %d)"
          % (total, shards, shard, config.EMBEDDING_BATCH, config.UPSERT_BATCH))
    if use_cache:
        os.makedirs(CACHE_DIR, exist_ok=True)

    upserted, t_start = 0, time.time()
    for si in range(shards):
        chunk_slice = chunks[si * shard:(si + 1) * shard]
        t0 = time.time()
        vecs = shard_vecs(si, chunk_slice, use_cache)
        t_embed = time.time() - t0

        t0 = time.time()
        points = [models.PointStruct(id=config.point_id(cid), vector=v.tolist(),
                                     payload=pl)
                  for (cid, pl), v in zip(chunk_slice, vecs)]
        for j in range(0, len(points), config.UPSERT_BATCH):
            batch = points[j:j + config.UPSERT_BATCH]
            client.upsert(collection_name=config.QDRANT_COLLECTION,
                          points=batch, wait=True)
            upserted += len(batch)
        print("  shard %3d/%d  %6d pts  embed %5.1fs upsert %5.1fs  total %6d/%d"
              % (si + 1, shards, len(points), t_embed, time.time() - t0,
                 upserted, total), flush=True)

    count = client.count(collection_name=config.QDRANT_COLLECTION, exact=True).count
    elapsed = time.time() - t_start
    print("[embed] done: upserted %d, collection now holds %d, in %.0fs"
          % (upserted, count, elapsed))
    if count != total:
        sys.exit("[EMBED] MISMATCH: %d points in collection vs %d chunks - investigate"
                 % (count, total))
    return {"upserted": upserted, "points": count, "chunks": total,
            "elapsed_sec": round(elapsed, 1)}


def _vsize(info):
    try:
        return info.config.params.vectors.size
    except Exception:
        return None


def check():
    """Offline integrity check of the frozen JSONL: parseable, required payload,
    unique chunk ids, deterministic point ids. No network, no DB."""
    chunks = load_chunks()
    ids = [cid for cid, _ in chunks]
    problems = 0
    for cid, pl in chunks:
        if not pl["content"] or len(pl["content"]) < 40:
            problems += 1
            if problems <= 3:
                print("  short/empty content at %s" % cid)
    for cid, _ in chunks[:2]:
        pl = dict(chunks)[cid]
        print("  sample %s -> point %s (type=%s, %d chars)"
              % (cid, config.point_id(cid), pl["document_type"] or "-",
                 len(pl["content"])))
    dup = len(ids) - len(set(ids))
    print("[check] %d chunks, %d duplicate chunk ids, %d payload problems"
          % (len(ids), dup, problems))
    if dup or problems or len(ids) != config.EXPECTED_CHUNKS:
        sys.exit("[check] FAIL: dup=%d problems=%d count=%d expected=%d"
                 % (dup, problems, len(ids), config.EXPECTED_CHUNKS))
    for cid in ids[:50]:   # determinism smoke
        assert config.point_id(cid) == config.point_id(cid)
    print("[check] PASS (deterministic ids, payloads complete)")
    return True


if __name__ == "__main__":
    if "--check" in sys.argv:
        check()
    else:
        embed_and_upsert(use_cache="--no-cache" not in sys.argv)
