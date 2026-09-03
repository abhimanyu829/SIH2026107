# QDRANT_READY

`qdrant_chunks.jsonl` - one JSON object per line, 45523 chunks, 16 payload fields each (see `PAYLOAD_SCHEMA.csv`).

**No embeddings are generated in Phase 3.** Every object carries text in `content` plus the payload needed for filtered hybrid retrieval; the dense and sparse vectors are produced in a later phase, after Phase 3 is approved.

Chunk text is assembled only from populated canonical fields and source-declared evidence text. Empty payload fields mean the uploaded data did not establish a value - nothing was inferred or filled in.
