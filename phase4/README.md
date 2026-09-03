# BIS SIH26107 - Phase 4: Supabase PostgreSQL + Qdrant Cloud

Consumes ONLY the frozen Phase-3 outputs under `BIS_SIH26107_DATA/`:

- `POSTGRES_READY/` (DDL, LOAD plan, TABLE_MANIFEST) + the canonical CSVs it points at
- `QDRANT_READY/qdrant_chunks.jsonl` (45,523 chunks, 16 payload fields)

Phase 3 is never re-run, re-analysed or modified here.

## Architecture (fixed by the spec)

| Store | Role |
|---|---|
| Supabase PostgreSQL (schema `bis`) | structured authority data: masters + relationship tables |
| Qdrant Cloud, ONE collection `bis_knowledge` | semantic document/evidence chunks, payload-filtered |

No duplication across the two. No Kubernetes, no queues, no Redis, no
self-hosted anything. BGE-M3 runs locally via `transformers` (CLS pooling,
1024-dim dense vectors); no LLM calls anywhere in this phase.

## Setup

```powershell
pip install -r phase4/requirements.txt
Copy-Item phase4/.env.example phase4/.env
# fill in SUPABASE_DATABASE_URL, QDRANT_URL, QDRANT_API_KEY
```

Secrets live only in `.env`; logs print redacted targets, never passwords or
keys.

## Run

```powershell
cd phase4
python run_phase4.py            # full pipeline: schema -> load -> validate -> embed -> upsert -> validate -> smoke
python run_phase4.py --check    # offline sanity, no credentials needed
python run_phase4.py --smoke-only
python run_phase4.py --skip-qdrant      # Supabase only
python run_phase4.py --skip-supabase    # Qdrant only
```

Steps are independent scripts too - every one is safe to re-run:

| Step | Command |
|---|---|
| Supabase connection test | `python supabase/connect.py` |
| Create schema (frozen Phase-3 DDL + alias views) | `python supabase/create_schema.py` |
| Bulk load (COPY, FKs after data) | `python supabase/load_data.py` |
| Validate + smoke SQL | `python supabase/validate.py` |
| Qdrant connection test | `python qdrant/connect.py` |
| Create `bis_knowledge` (+ 3 payload indexes) | `python qdrant/create_collection.py` |
| Embed + upsert (resumable, deterministic ids) | `python qdrant/embed_and_upsert.py` |
| Validate Qdrant | `python qdrant/validate.py` |
| One hybrid query | `python retrieval/hybrid_retriever.py "What standard applies to office work chairs?"` |
| The 5 smoke queries | `python retrieval/hybrid_retriever.py --smoke` |

## Idempotency

- Supabase: `create_schema.py` rebuilds empty tables; `load_data.py` TRUNCATEs
  all tables then COPYs - re-running twice gives the same row counts, never doubles.
- Qdrant: point ids are `UUID5(chunk_id)`, upserted - re-running overwrites the
  same points, never duplicates. Embeddings are cached per shard in
  `qdrant/.embeddings_cache/`, so an interrupted run resumes where it stopped.

## Performance / cost notes

- One COPY per table; FKs and indexes are added after the data lands.
- BGE-M3 downloads once (~2.3 GB) into `phase4/.hf_cache/` (self-contained;
  override `HF_HOME` for a global cache). CPU embedding of 45.5k chunks is on
  the order of an hour; GPU is minutes. Shards already embedded are cached in
  `qdrant/.embeddings_cache/`, so re-runs and interruptions resume.
- One batched upsert per 256 points. No per-row or per-chunk API calls, no
  per-chunk LLM calls.
- Query-side: one encode per query text, then one vector search.

## Failure handling

Connection failures print `[SUPABASE CONNECTION FAILED]` /
`[QDRANT CONNECTION FAILED]` with the redacted target and exit; they never
touch Phase-3 data. A Phase-4 connection problem is never a Phase-3 problem.

## Exit codes

2 config/dependency missing, 3 connection failed, 4 schema, 5 load,
6 validation, 7 acceptance incomplete.

## Later phases (NOT here)

RAG, LLM answers, chatbot, agent, frontend, user-document audit.
