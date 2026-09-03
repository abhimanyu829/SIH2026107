# BIS SIH26107 - Phase 5: Intelligent Chatbot + Single LangGraph Agent

Consumes the completed Phase-4 infrastructure only (Supabase PostgreSQL,
Qdrant Cloud collection `bis_knowledge`, Phase-4 retrievers). No earlier
phase is rebuilt; no source file is reprocessed; no frontend is built.

## Architecture

ONE LangGraph orchestrator. The four specialized nodes (standards /
verification / compliance / comparison) are routing policies inside the same
graph - same state, same memory, same tool registry, same guardrails. No
multi-agent swarm, no agent-to-agent chatter.

```
START -> understand_query
  -> SIMPLE: quick_lookup -> collect_evidence -> synthesize -> cite -> finalize
  -> AGENT : create_plan -> route_specialized_node
             -> execute_tool (bounded loop, MAX_AGENT_STEPS=8)
             -> collect_evidence -> synthesize -> cite -> finalize
```

## LLM policy (cost control)

- Deterministic understanding/planning/reranking everywhere - zero LLM calls.
- The LLM (optional, `LLM_API_KEY` in .env) only rewords answers from the
  grounded evidence; without it the system runs in deterministic mode and
  still answers (UNKNOWN when evidence is insufficient).
- One shared ChatOpenAI-compatible model; no per-node model fan-out.

## Run

```powershell
pip install -r phase5/requirements.txt
python phase5/run_phase5.py --check    # offline: graph compile, registry, no creds
python phase5/run_phase5.py            # + full evaluation suite + report
python phase5/run_phase5.py --serve    # uvicorn on http://127.0.0.1:8001
```

## API (11 endpoints)

POST /api/chat - conversational BIS assistance (SIMPLE path)
POST /api/agent/run - agent workflow (plan, tools, evidence, citations)
POST /api/search - direct Qdrant evidence search
GET /api/standards/{is_number}  GET /api/products/{product_id}
GET /api/qco/{is_number}        GET /api/schemes/{is_number}
GET /api/tests/{is_number}     GET /api/labs/{is_number}
GET /api/evidence/{document_id}
GET /api/health

## Tools (16, one registry)

find_product, get_product, search_standards, get_standard, get_related_standards,
get_qco, get_notifications, get_scheme, get_product_manual, get_document,
search_evidence, get_tests, find_labs, get_lab_scope, verify_identifier,
compare_standards, compare_requirements.
The LLM never sees SQL - only these functions.

## Memory

L1 conversation (messages, topic, resolved entities, selected IS) +
L2 task (plan, completed/pending steps, evidence). In-process dict, no Redis,
no vector memory, no personal data.

## Guardrails

No invented IS numbers / statuses / dates / labs / tests / citations; citations
validated against the evidence set; UNKNOWN forced when evidence is absent;
conflicts preserved, never silently resolved.

## Evaluation

`evaluation/test_queries.json` holds the 12 spec tests; `python run_phase5.py`
runs test_tools/test_memory/test_chat/test_agent and writes
`evaluation/evaluation_report.json`. DB-dependent tests SKIP (not FAIL) when
credentials are absent, so the suite is always runnable.
