"""Phase-4 orchestrator: Supabase load + Qdrant load + validation + smoke tests.

Each step is an independent script run in its own subprocess, so a step can
also be re-run by hand and the flat module names (connect.py x2) never collide.
Nothing here re-reads the original 49 source files; every input is a frozen
Phase-3 output under BIS_SIH26107_DATA/.

  python run_phase4.py                # full pipeline, in order
  python run_phase4.py --skip-supabase
  python run_phase4.py --skip-qdrant
  python run_phase4.py --smoke-only   # retrieval smoke tests only
  python run_phase4.py --check        # offline checks (no credentials needed)
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import config  # noqa: E402

PY = sys.executable

STEPS = [
    ("supabase", "connect", os.path.join("supabase", "connect.py")),
    ("supabase", "schema", os.path.join("supabase", "create_schema.py")),
    ("supabase", "load", os.path.join("supabase", "load_data.py")),
    ("supabase", "validate", os.path.join("supabase", "validate.py")),
    ("qdrant", "connect", os.path.join("qdrant", "connect.py")),
    ("qdrant", "collection", os.path.join("qdrant", "create_collection.py")),
    ("qdrant", "embed+upsert", os.path.join("qdrant", "embed_and_upsert.py")),
    ("qdrant", "validate", os.path.join("qdrant", "validate.py")),
]


def run(label, script, expect_zero=True, extra=()):
    print("\n" + "=" * 70)
    print("STEP %s" % label)
    print("=" * 70)
    t0 = time.time()
    p = subprocess.run([PY, os.path.join(HERE, script)] + list(extra), cwd=HERE)
    dt = time.time() - t0
    print("[step] %s -> %s in %.0fs" % (label, "OK" if p.returncode == 0
                                        else "FAILED(%d)" % p.returncode, dt))
    if expect_zero and p.returncode != 0:
        sys.exit("[run_phase4] step %s failed with exit %d - stopping. "
                 "Phase-3 outputs are untouched; fix and re-run."
                 % (label, p.returncode))
    return p.returncode


def offline_check():
    """No credentials needed: frozen inputs + code sanity."""
    print("[check] offline verification (no network, no credentials)")
    run("qdrant-input-check", os.path.join("qdrant", "embed_and_upsert.py"),
        extra=["--check"])
    compile_ok = subprocess.run([PY, "-m", "compileall", "-q", HERE])
    if compile_ok.returncode != 0:
        sys.exit("[check] compileall failed")
    print("[check] PASS - code compiles, frozen JSONL intact")


def acceptance_report():
    """Prints the Phase-4 completion block required by the spec."""
    vpath = os.path.join(config.VALIDATION_DIR, "PHASE4_VALIDATION.json")
    v = {}
    if os.path.exists(vpath):
        with open(vpath, encoding="utf-8") as f:
            v = json.load(f)
    sup = v.get("supabase", {})
    qdr = v.get("qdrant", {})
    smoke = v.get("smoke_tests", {})

    sup_pass = sup.get("pass", False)
    qdr_pass = qdr.get("pass", False)
    smoke_ok = (smoke.get("queries") and
                all(q.get("standards_found") or q.get("semantic_hits")
                    for q in smoke["queries"]))

    print("\n" + "=" * 70)
    print("ACCEPTANCE CRITERIA")
    print("=" * 70)
    for name, ok in [
        ("Supabase connection works", bool(sup.get("connection"))),
        ("Supabase tables created", sup.get("checks", {}).get("tables_exist", {}).get("pass")),
        ("Phase-3 structured data loaded", sup.get("checks", {}).get("row_counts_vs_csv", {}).get("pass")),
        ("Supabase row counts verified", sup.get("checks", {}).get("row_counts_vs_csv", {}).get("pass")),
        ("PK checks pass", sup.get("checks", {}).get("blank_primary_keys", {}).get("pass")
         and sup.get("checks", {}).get("duplicate_primary_keys", {}).get("pass")),
        ("FK checks pass", sup.get("checks", {}).get("fk_constraints_present", {}).get("pass")
         and sup.get("checks", {}).get("fk_orphans", {}).get("pass")),
        ("Qdrant Cloud connection works", qdr.get("checks", {}).get("collection_exists", {}).get("pass")),
        ("bis_knowledge collection created", qdr.get("checks", {}).get("collection_exists", {}).get("pass")),
        ("BGE-M3 embeddings + vectors uploaded", qdr.get("checks", {}).get("point_count_vs_chunks", {}).get("pass")),
        ("Qdrant point count verified", qdr.get("checks", {}).get("point_count_vs_chunks", {}).get("pass")),
        ("Qdrant metadata verified", qdr.get("checks", {}).get("payload_presence", {}).get("pass")),
        ("Semantic search works", qdr.get("checks", {}).get("semantic_search", {}).get("pass")),
        ("Supabase exact lookup works (IS 17631 e2e)",
         sup.get("checks", {}).get("smoke_is_17631_lookup", {}).get("pass")
         and sup.get("checks", {}).get("smoke_is_17631_connected", {}).get("pass")),
        ("IS 2347:2023 present", sup.get("checks", {}).get("smoke_is_2347_2023", {}).get("pass")),
        ("Hybrid retrieval works", bool(smoke_ok)),
    ]:
        print("  [%s] %s" % ("x" if ok else " ", name))

    print("\n" + "-" * 70)
    if sup_pass and qdr_pass and smoke_ok:
        print("PHASE 4 COMPLETE\n")
        print("SUPABASE POSTGRESQL: PASS")
        print("QDRANT CLOUD: PASS")
        print("SEMANTIC SEARCH: PASS")
        print("EXACT SQL RETRIEVAL: PASS")
        print("HYBRID RETRIEVAL: PASS")
        print()
        print("Supabase tables : %d" % len(sup.get("tables", {})))
        print("Supabase rows   : %d" % sup.get("total_rows", 0))
        print("Qdrant points   : %s" % (qdr.get("checks", {}).get(
            "point_count_vs_chunks", {}).get("detail", "?")))
        print("Embedding model : %s" % config.EMBEDDING_MODEL)
        print("Collection      : %s" % config.QDRANT_COLLECTION)
        qs = smoke.get("queries", [])
        print("Smoke tests     : %d queries" % len(qs))
        for q in qs:
            print("  - %-52s standards=%s semantic=%s" % (
                q.get("query", "")[:52], q.get("standards_found"),
                q.get("semantic_hits")))
        return True
    print("PHASE 4 INCOMPLETE - see validation/PHASE4_VALIDATION.json")
    return False


def main():
    args = set(sys.argv[1:])
    if "--check" in args:
        offline_check()
        return
    skip_sup, skip_qdr = "--skip-supabase" in args, "--skip-qdrant" in args
    if not (skip_sup or skip_qdr or "--smoke-only" in args):
        config.load_env()   # fail fast with a readable message if .env is absent
    if "--smoke-only" not in args:
        for part, label, script in STEPS:
            if part == "supabase" and skip_sup:
                continue
            if part == "qdrant" and skip_qdr:
                continue
            run("%s/%s" % (part, label), script)
    run("retrieval/smoke", os.path.join("retrieval", "hybrid_retriever.py"),
        extra=["--smoke"])
    ok = acceptance_report()
    sys.exit(0 if ok else 7)


if __name__ == "__main__":
    main()
