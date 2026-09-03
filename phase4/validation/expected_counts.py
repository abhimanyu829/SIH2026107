"""Precomputes the expected Phase-4 row counts from the frozen Phase-3 CSVs.

Writes the "expected" section (per-table CSV row counts + chunk total) into
validation/PHASE4_VALIDATION.json so the first real run already has the
comparison baseline, measured - never assumed - from the frozen data.
Offline: no Supabase, no Qdrant, no credentials.
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import config  # noqa: E402

# supabase/load_data.py lives flat under supabase/ and imports `connect` at
# import time; give it a stub for that name (offline run never calls connect())
# and load the real file by path so nothing under supabase/ needs credentials.
sys.modules.setdefault("connect", type(sys)("connect"))
sys.modules["connect"].connect = lambda **k: (_ for _ in ()).throw(
    RuntimeError("connect() is not available in the offline expected-counts run"))
_ld = importlib.util.spec_from_file_location(
    "phase4_supabase_load_data", os.path.join(HERE, "..", "supabase", "load_data.py"))
load_data = importlib.util.module_from_spec(_ld)
_ld.loader.exec_module(load_data)


def main():
    counts = {t: load_data.csv_rows(p) for t, p, _, _ in load_data.manifest()}
    expected = {
        "tables": len(counts),
        "total_rows": sum(counts.values()),
        "row_counts": counts,
        "qdrant_chunks": sum(1 for _ in open(config.CHUNKS, encoding="utf-8")),
    }
    path = config.merge_validation("expected", expected)
    print("expected: %d tables, %d rows, %d chunks -> %s"
          % (expected["tables"], expected["total_rows"],
             expected["qdrant_chunks"], path))
    for t, n in sorted(counts.items(), key=lambda kv: -kv[1])[:8]:
        print("  %-38s %8d" % (t, n))
    return expected


if __name__ == "__main__":
    main()
