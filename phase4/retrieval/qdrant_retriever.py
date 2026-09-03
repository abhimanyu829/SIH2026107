"""Qdrant Cloud semantic retriever over bis_knowledge. No RAG, no LLM.

Embedding: BAAI/bge-m3 dense vectors via plain transformers (AutoModel + CLS
pooling + L2 normalize) - the exact dense configuration of the model card.
sentence-transformers 6.x breaks on this repo's modules.json, so Phase 4 does
not depend on it. One shared loader: validator, hybrid retriever and smoke
tests all embed through here, so model, device and truncation stay consistent.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402

_MODEL = {"st": None, "tok": None, "device": None}


def load_model():
    """Loads BAAI/bge-m3 once per process (GPU if available, else CPU)."""
    if _MODEL["st"] is None:
        try:
            import torch
            from transformers import AutoModel, AutoTokenizer
        except ImportError:
            sys.stderr.write("[DEPENDENCY] torch/transformers missing. "
                             "pip install -r phase4/requirements.txt\n")
            sys.exit(2)
        device = config.EMBEDDING_DEVICE or ("cuda" if torch.cuda.is_available()
                                             else "cpu")
        tok = AutoTokenizer.from_pretrained(config.EMBEDDING_MODEL)
        st = AutoModel.from_pretrained(config.EMBEDDING_MODEL)
        st.eval().to(device)
        _MODEL.update(st=st, tok=tok, device=device)
        print("[qdrant-retriever] model=%s device=%s max_seq=%d"
              % (config.EMBEDDING_MODEL, device, config.EMBEDDING_MAX_SEQ))
    return _MODEL


def embed_texts(texts):
    """Texts -> normalized 1024-dim dense vectors (float32), CLS pooling."""
    import numpy as np
    import torch
    m = load_model()
    out = []
    with torch.no_grad():
        for i in range(0, len(texts), config.EMBEDDING_BATCH):
            batch = texts[i:i + config.EMBEDDING_BATCH]
            enc = m["tok"](batch, padding=True, truncation=True,
                           max_length=config.EMBEDDING_MAX_SEQ,
                           return_tensors="pt").to(m["device"])
            cls = m["st"](**enc).last_hidden_state[:, 0]        # CLS pooling
            cls = torch.nn.functional.normalize(cls, p=2, dim=1)
            out.append(cls.cpu().numpy().astype("float32"))
    return np.vstack(out)


def embed_query(text):
    """One query text -> normalized 1024-dim vector as a plain list."""
    return embed_texts([text])[0].tolist()


class QdrantRetriever:
    """Semantic search over the single bis_knowledge collection.

    Payload filtering (document_type, canonical_is_number, is_id) replaces any
    per-type collections - that is the whole point of the one-collection design.
    """

    def __init__(self, collection=None):
        self.collection = collection or config.QDRANT_COLLECTION
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from qdrant.connect import get_client
            self._client = get_client()
        return self._client

    def search(self, query, limit=None, document_types=None,
               canonical_is_number=None, is_id=None):
        """Returns [{'score', 'chunk_id', 'document_type', 'title', 'section',
        'clause', 'page', 'source_url', 'content'}, ...] best-first."""
        from qdrant_client import models
        limit = limit or config.QDRANT_LIMIT
        must = []
        if document_types:
            must.append(models.FieldCondition(
                key="document_type",
                match=models.MatchAny(any=list(document_types))))
        if canonical_is_number:
            must.append(models.FieldCondition(
                key="canonical_is_number",
                match=models.MatchValue(value=canonical_is_number)))
        if is_id:
            must.append(models.FieldCondition(
                        key="is_id", match=models.MatchValue(value=is_id)))
        qfilter = models.Filter(must=must) if must else None
        res = self.client.query_points(collection_name=self.collection,
                                       query=embed_query(query), limit=limit,
                                       query_filter=qfilter,
                                       with_payload=True)
        out = []
        for p in res.points:
            pl = p.payload or {}
            out.append({
                "score": round(float(p.score), 4),
                "chunk_id": pl.get("chunk_id"),
                "document_type": pl.get("document_type"),
                "title": pl.get("title") or pl.get("canonical_is_number") or "",
                "section": pl.get("section"),
                "clause": pl.get("clause"),
                "page": _page(pl.get("page_start"), pl.get("page_end")),
                "source_url": pl.get("source_url"),
                "content": (pl.get("content") or "")[:300],
            })
        return out


def _page(start, end):
    if start is None and end is None:
        return None
    if start is not None and end is not None:
        return "pp. %s-%s" % (start, end)
    return "p. %s" % (start if start is not None else end)


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "What standard applies to office work chairs?"
    print("[qdrant-retriever] query: %s" % q)
    for r in QdrantRetriever().search(q, limit=5):
        print("  %.3f  %-18s %-40s %s" % (r["score"], r["document_type"] or "-",
                                           (r["title"] or "")[:40],
                                           r["source_url"] or ""))
