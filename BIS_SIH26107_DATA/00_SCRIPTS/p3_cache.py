"""Primes the Phase 3 row cache. Idempotent and resumable: one pickle per source file,
written only after the file parses completely. Parses nothing twice, changes no source.
"""
import os
import pickle
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_lib as L
import p3_model as M
import p1_run as P1

SRC = "/sessions/optimistic-gallant-gauss/mnt/SIH-DATASETS-EXCEL-SHEET"
CD = os.path.join(SRC, "BIS_SIH26107_DATA/01_ANALYSIS/_cache/rows")
os.makedirs(CD, exist_ok=True)
INV = {r["file_id"]: r for r in
       L.rcsv(os.path.join(SRC, "BIS_SIH26107_DATA/01_ANALYSIS/FILE_INVENTORY.csv"))}


def raw(fid):
    path = INV[fid]["exact_path"]
    ext = (INV[fid]["extension"] or "").lower().lstrip(".")
    if ext in ("xlsx", "xlsm", "xls"):
        for sheet, headers, rows, struct in P1.load_xlsx(path):
            for n, r in enumerate(rows, start=2):
                yield sheet, n, headers, r
    elif ext in ("csv", "tsv", "txt"):
        headers, rows, struct = P1.load_csv(path)
        for n, r in enumerate(rows, start=2):
            yield "", n, headers, r


done = tot = 0
for fid in sorted(INV):
    cp = os.path.join(CD, "%s.pkl" % fid)
    if os.path.exists(cp):
        continue
    out = list(raw(fid))
    with open(cp + ".tmp", "wb") as fh:
        pickle.dump(out, fh, protocol=4)
    os.replace(cp + ".tmp", cp)
    done += 1
    tot += len(out)
    print("cached %s %6d rows  %s" % (fid, len(out), INV[fid]["original_filename"][:60]),
          flush=True)
have = len([f for f in os.listdir(CD) if f.endswith(".pkl")])
print("CACHE %d/%d files present (this run cached %d files, %d rows)"
      % (have, len(INV), done, tot))
