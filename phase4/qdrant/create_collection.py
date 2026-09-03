"""Creates the ONE Phase-4 collection: bis_knowledge. Re-runnable.

No per-type collections - document_type lives in the payload and is filtered
on. Three payload indexes only: canonical_is_number, document_type, is_id.
Nothing here redesigns Phase-3 chunking; it just makes the chunks searchable.

  python qdrant/create_collection.py             # create if missing
  python qdrant/create_collection.py --recreate # drop + recreate (empty)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402
from connect import get_client  # noqa: E402

# The three fields retrieval actually filters on. Anything more is over-engineering.
PAYLOAD_INDEXES = ["canonical_is_number", "document_type", "is_id"]


def create(recreate=False):
    from qdrant_client import models

    client = get_client()
    name = config.QDRANT_COLLECTION
    exists = False
    try:
        exists = client.collection_exists(name)
    except AttributeError:  # older client: fall back to the listing
        exists = any(c.name == name for c in client.get_collections().collections)

    if exists:
        info = client.get_collection(name)
        size = _vector_size(info)
        if recreate:
            print("[collection] dropping existing %s (--recreate)" % name)
            client.delete_collection(name)
            exists = False
        elif size and size != config.VECTOR_SIZE:
            sys.exit("[collection] %s exists with %d-dim vectors, Phase 4 needs %d.\n"
                     "  Re-run with --recreate to drop and recreate it (vectors are\n"
                     "  rebuilt from QDRANT_READY/qdrant_chunks.jsonl, nothing is lost)."
                     % (name, size, config.VECTOR_SIZE))
        else:
            print("[collection] %s already exists - keeping it (upsert is idempotent)"
                  % name)
    if not exists:
        client.create_collection(
            collection_name=name,
            vectors_config=models.VectorParams(
                size=config.VECTOR_SIZE,
                distance=models.Distance.COSINE,
            ),
            on_disk_payload=True,   # keeps payload text out of RAM; free tier friendly
        )
        print("[collection] created %s (%d-dim, Cosine)" % (name, config.VECTOR_SIZE))

    for field in PAYLOAD_INDEXES:
        client.create_payload_index(collection_name=name, field_name=field,
                                    field_schema=models.PayloadSchemaType.KEYWORD)
    print("[collection] payload indexes: %s" % ", ".join(PAYLOAD_INDEXES))

    info = client.get_collection(name)
    print("[collection] status=%s vectors=%d-dim distance=%s points=%d"
          % (info.status, _vector_size(info) or 0,
             _distance(info) or "?", info.points_count))
    return {"collection": name, "vector_size": _vector_size(info),
            "distance": _distance(info), "points": info.points_count,
            "payload_indexes": PAYLOAD_INDEXES}


def _vector_size(info):
    try:
        return info.config.params.vectors.size
    except Exception:
        return None


def _distance(info):
    try:
        return info.config.params.vectors.distance
    except Exception:
        return None


if __name__ == "__main__":
    create(recreate="--recreate" in sys.argv)
