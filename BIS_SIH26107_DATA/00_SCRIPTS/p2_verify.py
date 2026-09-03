"""PHASE 2 VERIFICATION - independent audit of the Phase 2 evidence and decisions.

Recomputes from disk rather than trusting the pipeline's own state: re-hashes every source
file, re-reads every output CSV, and re-derives the safety properties that the spec makes
non-negotiable. Fails loudly. Nothing here writes to a source file or to an output CSV.
"""
import collections
import csv
import hashlib
import os
import sys

SRC = "/sessions/optimistic-gallant-gauss/mnt/SIH-DATASETS-EXCEL-SHEET"
OUT = os.path.join(SRC, "BIS_SIH26107_DATA", "01_ANALYSIS")
csv.field_size_limit(50_000_000)

ALLOWED = {"EXACT_DUPLICATE", "IDENTICAL_CONTENT", "DUPLICATE_WITH_UNIQUE_DATA",
           "COMPLEMENTARY", "VERSION_NEWER", "VERSION_OLDER", "DIFFERENT_ENTITY",
           "CONFLICTING", "LIKELY_DUPLICATE", "REQUIRES_REVIEW"}

MANDATORY = ["DATASET_COMPARISON.csv", "DUPLICATE_GROUPS.csv", "VERSION_ANALYSIS.csv",
             "CONFLICTS.csv", "ROW_LEVEL_DUPLICATES.csv", "SCHEMA_COMPARISON.csv",
             "CANONICAL_DECISIONS.csv", "PHASE2_MERGE_PLAN.csv"]

GROUP_REQ = ["group_id", "file_a", "file_b", "duplicate_type", "similarity_score",
             "common_rows", "unique_rows_a", "unique_rows_b", "common_IS_numbers",
             "unique_IS_numbers_a", "unique_IS_numbers_b", "common_columns",
             "unique_columns_a", "unique_columns_b", "conflicts", "decision",
             "decision_reason", "recommended_canonical_file", "records_to_merge",
             "records_to_archive", "requires_review"]

R = []


def chk(name, ok, detail=""):
    R.append((name, "PASS" if ok else "FAIL", detail))


def rd(name):
    with open(os.path.join(OUT, name), encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    inv = rd("FILE_INVENTORY.csv")

    # 1 - every source file is byte-identical to what Phase 1 recorded.
    # Resolve each file by the path Phase 1 actually recorded: 48 sit in the workspace
    # folder and 1 (the project PDF) was an attachment, so assuming a single root would
    # report a false modification.
    bad, missing = [], []
    for r in inv:
        p = r["exact_path"] or os.path.join(SRC, r["original_filename"])
        if not os.path.exists(p):
            missing.append(r["original_filename"])
        elif sha(p) != r["sha256"]:
            bad.append(r["original_filename"])
    chk("source files unmodified (SHA-256 re-hash)", not bad and not missing,
        "%d files re-hashed (%d workspace + %d attached); modified=%s missing=%s"
        % (len(inv), sum(1 for r in inv if r["source_location"] == "workspace"),
           sum(1 for r in inv if r["source_location"] != "workspace"),
           bad or "none", missing or "none"))

    # 2 - nothing added to or removed from the source root
    live = {f for f in os.listdir(SRC)
            if os.path.isfile(os.path.join(SRC, f)) and not f.startswith("~$")}
    known = {r["original_filename"] for r in inv if r["source_location"] == "workspace"}
    chk("source root unchanged (no file added or removed)", live == known,
        "%d files; extra=%s absent=%s" % (len(known), sorted(live - known) or "none",
                                          sorted(known - live) or "none"))

    # 3 - all eight mandatory outputs exist and carry rows
    empty = [m for m in MANDATORY
             if not os.path.exists(os.path.join(OUT, m)) or len(rd(m)) == 0]
    chk("all 8 mandatory Phase 2 outputs present and non-empty", not empty,
        "missing/empty=%s" % (empty or "none"))

    G = rd("DUPLICATE_GROUPS.csv")
    D = rd("DATASET_COMPARISON.csv")
    C = rd("CONFLICTS.csv")
    CD = rd("CANONICAL_DECISIONS.csv")
    V = rd("VERSION_ANALYSIS.csv")
    M = rd("PHASE2_MERGE_PLAN.csv")

    # 4 - the reporting schema the spec dictates, verbatim
    miss = [c for c in GROUP_REQ if c not in (G[0].keys() if G else [])]
    chk("DUPLICATE_GROUPS.csv carries every required column", not miss,
        "missing=%s" % (miss or "none"))

    # 5 - closed decision vocabulary
    seen = collections.Counter(g["decision"] for g in G)
    illegal = sorted(set(seen) - ALLOWED)
    chk("every decision is one of the 10 allowed categories", not illegal,
        "illegal=%s; distinct used=%d" % (illegal or "none", len(seen)))

    # 6 - one group per compared pair, no pair lost, no pair invented
    pg = collections.Counter(g["pair_id"] for g in G)
    pd = {p["pair_id"] for p in D}
    chk("one duplicate-group row per compared pair", set(pg) == pd and max(pg.values()) == 1,
        "pairs compared=%d groups=%d dup_pair_ids=%d"
        % (len(pd), len(G), sum(1 for v in pg.values() if v > 1)))

    # 7 - conflicts resolve nothing and keep both sides addressable
    unres = [c for c in C if c["resolution_status"] != "UNRESOLVED_PRESERVE_BOTH"]
    noprov = [c for c in C if not c["source_row_a"] or not c["source_row_b"]
              or not c["file_a"] or not c["file_b"]]
    bothblank = [c for c in C if not c["value_a"].strip() and not c["value_b"].strip()]
    chk("every conflict is UNRESOLVED_PRESERVE_BOTH", not unres,
        "%d conflicts; resolved-early=%d" % (len(C), len(unres)))
    chk("every conflict carries both sides with source rows", not noprov and not bothblank,
        "missing provenance=%d both-sides-blank=%d" % (len(noprov), len(bothblank)))

    # 8 - archive safety: nothing archivable may hold a record no retained file holds
    keepset = {c["original_filename"] for c in CD if c["archive_eligible"] == "NO"}
    arch = [c for c in CD if c["archive_eligible"] == "YES"]
    resid = [c["original_filename"] for c in arch
             if c["unique_records_not_covered_elsewhere"] not in ("NONE", "")]
    chk("no archive-eligible file holds uncovered unique records", not resid,
        "%d archive-eligible; offenders=%s" % (len(arch), resid or "none"))
    orphan = [c["original_filename"] for c in arch
              if not (set(x.strip() for x in c["fully_covered_by"].split(";")) & keepset)]
    chk("every archive-eligible file is covered by a RETAINED file", not orphan,
        "coverage chains resolve to a kept file; orphans=%s" % (orphan or "none"))

    # 9 - version pairs must lose no record
    vl = [v for v in V if v["content_verdict"].startswith("VERSION")
          and v["records_lost_if_older_archived"] not in ("0", "")]
    chk("no version pair loses a record if the older side is archived", not vl,
        "%d version rows analysed; lossy=%d" % (len(V), len(vl)))

    # 10 - no filename-derived verdict: every VERSION decision cites content evidence
    nofx = [g["group_id"] for g in G if g["decision"].startswith("VERSION")
            and not (g["version_direction_evidence"].startswith("ENRICHMENT")
                     or g["version_direction_evidence"].startswith("REPAIR"))]
    chk("every version verdict rests on ENRICHMENT/REPAIR content evidence", not nofx,
        "offenders=%s" % (nofx or "none"))

    # 11 - the rule-8 case is settled by content, not by filename
    sm = [g for g in G if "Schemes_Master.xlsx" in g["file_a"]
          and "Schemes_Master_Scheme_2.xlsx" in g["file_b"]]
    ok8 = bool(sm) and sm[0]["decision"] == "DIFFERENT_ENTITY" \
        and bool(sm[0]["entity_discriminator_columns"])
    chk("BIS_Schemes_Master vs _Scheme_2 checked by content", ok8,
        "decision=%s discriminators=%s"
        % (sm[0]["decision"] if sm else "PAIR_ABSENT",
           sm[0]["entity_discriminator_columns"] if sm else "-"))

    # 12 - every retained tabular file appears in the merge plan
    plan = set()
    for m in M:
        plan |= {s.strip() for s in m["source_files"].split(";") if s.strip()}
    tab = {c["original_filename"] for c in CD
           if c["canonical_status"] != "NOT_TABULAR_KEEP_AS_REFERENCE"
           and c["archive_eligible"] == "NO"}
    chk("every retained tabular file is claimed by a merge step", tab <= plan,
        "%d retained tabular; unclaimed=%s" % (len(tab), sorted(tab - plan) or "none"))

    # 13 - Phase 2 boundary: nothing archived, restructured or merged yet
    side = [d for d in ("99_RAW_ORIGINALS/ARCHIVE_OR_DUPLICATES", "02_CANONICAL",
                        "03_MERGED", "04_FINAL")
            if os.path.isdir(os.path.join(SRC, "BIS_SIH26107_DATA", d))
            and os.listdir(os.path.join(SRC, "BIS_SIH26107_DATA", d))]
    chk("Phase 2 boundary intact (no archive, no restructure, no canonical data)",
        not side, "non-empty premature dirs=%s" % (side or "none"))

    # 14 - review flags are never silently cleared where conflicts exist
    unflag = [g["group_id"] for g in G if int(g["conflicts"]) > 0
              and g["requires_review"] == "NO"
              and not g["decision"].startswith("VERSION")]
    chk("conflicting pairs carry a review flag unless direction was proven", not unflag,
        "offenders=%s" % (unflag[:5] or "none"))

    w = max(len(n) for n, _, _ in R)
    print("=" * 78)
    print("PHASE 2 VERIFICATION")
    print("=" * 78)
    for n, s, d in R:
        print("[%s] %-*s  %s" % (s, w, n, d))
    f = sum(1 for _, s, _ in R if s == "FAIL")
    print("-" * 78)
    print("%d checks, %d PASS, %d FAIL" % (len(R), len(R) - f, f))
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())
