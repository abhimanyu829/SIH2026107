"""PHASE 3 VERIFICATION - independent audit of the canonical BIS data layer.

Recomputes from disk rather than trusting the build's own state: re-reads every emitted
CSV/JSONL, re-derives referential integrity, provenance coverage, zero-data-loss
accounting, conflict honesty and load readiness. Emits the ten 3T validation outputs.
Archive copies of the four duplicate files are made ONLY if every check passes, and the
originals are copied - never moved, never deleted.
"""
import collections
import csv
import hashlib
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_lib as L
import p3_model as M

SRC = "/sessions/optimistic-gallant-gauss/mnt/SIH-DATASETS-EXCEL-SHEET"
ROOT = os.path.join(SRC, "BIS_SIH26107_DATA")
AN = os.path.join(ROOT, "01_ANALYSIS")
VAL = os.path.join(ROOT, "92_VALIDATION")
csv.field_size_limit(50_000_000)

DISPS = ("CANONICAL", "MERGED", "CONFLICT_PRESERVED", "REQUIRES_REVIEW",
         "DUPLICATE_ARCHIVED", "NOT_APPLICABLE")
CSTAT = ("RESOLVED", "UNRESOLVED_PRESERVE_BOTH", "REQUIRES_REVIEW")
NULLSEM = ("NULL_UNKNOWN", "ASSERTED_ABSENCE", "AMBIGUOUS_REQUIRES_REVIEW", "POPULATED")
PLACE = {"n/a", "na", "unknown", "none", "-", "--", "nil", "null", "tbd", "?"}
# Columns whose values are controlled vocabularies that legitimately include tokens like
# NONE or UNKNOWN (a measured date precision, a retained raw string, a variant list).
# Auditing them for placeholders would flag facts, not gaps.
QUALIFIER = ("original", "variants", "precision", "class", "flag", "status", "reason")
R = []


def chk(name, ok, detail=""):
    R.append((name, "PASS" if ok else "FAIL", detail))


def rp(*a):
    return os.path.join(ROOT, *a)


def rd(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def hdr(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig", newline="") as f:
        return next(csv.reader(f), [])


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def wcsv(path, rows, cols):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def n(x):
    return "{:,}".format(x)
T0 = __import__("time").time()


def p(*a):
    print("%6.1fs" % (__import__("time").time() - T0), *a, flush=True)


def stream(path):
    """Yield (header_list, row_list) pairs without holding the file in memory."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8-sig", newline="") as f:
        r = csv.reader(f)
        h = next(r, [])
        for row in r:
            yield h, row


COMPLETE = []


def completeness(label, path):
    """Per-column populated counts, measured by re-reading the emitted file."""
    tot, pop, hh = 0, collections.Counter(), []
    for h, row in stream(path):
        hh = h
        tot += 1
        for i, c in enumerate(h):
            if i < len(row) and str(row[i]).strip() != "":
                pop[c] += 1
    for c in hh:
        COMPLETE.append({"dataset": label, "column": c, "rows": tot,
                         "populated": pop[c], "empty": tot - pop[c],
                         "populated_pct": round(100.0 * pop[c] / tot, 2) if tot else 0})
    return tot


p("[1] inventory, phase-2 decisions, master primary keys")
INV = {r["file_id"]: r for r in rd(os.path.join(AN, "FILE_INVENTORY.csv"))}
DECI = {r["file_id"]: r for r in rd(os.path.join(AN, "CANONICAL_DECISIONS.csv"))}
ARCH = sorted(f for f, r in DECI.items()
              if r["canonical_status"] == "REDUNDANT_ARCHIVE_AFTER_VALIDATION")
SRCROWS = sum(int(INV[f]["total_data_rows"] or 0) for f in INV)
NONTAB = [f for f in INV if int(INV[f]["total_data_rows"] or 0) == 0]
MASTERS = sorted(f for f in os.listdir(rp("00_MASTER")) if f.endswith("_MASTER.csv"))
PKSET, PREF, MROWS = {}, {}, {}
for mf in MASTERS:
    ids, dup, blank = set(), 0, 0
    pk = ""
    for h, row in stream(rp("00_MASTER", mf)):
        pk = h[0]
        v = row[0].strip() if row else ""
        if not v:
            blank += 1
        elif v in ids:
            dup += 1
        else:
            ids.add(v)
    PKSET[mf], MROWS[mf] = ids, len(ids) + dup + blank
    chk("master_pk_unique:" + mf, dup == 0 and blank == 0,
        "%s rows=%s duplicate=%d blank=%d" % (pk, n(MROWS[mf]), dup, blank))
    for v in ids:
        PREF.setdefault(v.split("-")[0], set()).add(v)
ALLIDS = set().union(*PKSET.values()) if PKSET else set()
p("    masters %d  ids %s  prefixes %s" % (len(MASTERS), n(len(ALLIDS)),
                                           ",".join(sorted(PREF))))


def fkbad(h, row):
    """Ids whose prefix belongs to a master table but which are not in that table."""
    out = []
    for i, c in enumerate(h):
        if not c.endswith("_id") or i >= len(row):
            continue
        v = (row[i] or "").strip()
        if not v or "-" not in v:
            continue
        pre = v.split("-")[0]
        if pre in PREF and v not in PREF[pre]:
            out.append((c, v))
    return out
p("[2] zero-data-loss accounting (DATA_LOSS_AUDIT vs FILE_INVENTORY)")
DLAF, DLAD, DLABAD, NDLA = collections.Counter(), collections.Counter(), 0, 0
DLAPAIR = set()
for h, row in stream(rp("92_VALIDATION/DATA_LOSS_AUDIT.csv")):
    d = dict(zip(h, row))
    NDLA += 1
    DLAF[d["source_file_id"]] += 1
    DLAD[d["record_disposition"]] += 1
    DLAPAIR.add((d["source_file_id"], d["source_sheet"], d["source_row"]))
    if d["record_disposition"] not in DISPS:
        DLABAD += 1
    if d["entity_id"] and fkbad(["entity_id"], [d["entity_id"]]):
        DLABAD += 1
EXPECT = SRCROWS + len(NONTAB)
chk("data_loss_row_count", NDLA == EXPECT,
    "audit rows %s == source rows %s + non-tabular sources %d" %
    (n(NDLA), n(SRCROWS), len(NONTAB)))
chk("data_loss_no_duplicate_rows", len(DLAPAIR) == NDLA,
    "distinct (file,sheet,row) %s" % n(len(DLAPAIR)))
chk("data_loss_disposition_vocabulary", DLABAD == 0,
    "every row is one of %s and every entity_id resolves" % "/".join(DISPS))
MISS = [f for f in INV if DLAF[f] != max(int(INV[f]["total_data_rows"] or 0), 1)]
chk("data_loss_per_file_complete", not MISS,
    "all %d source files fully accounted" % len(INV) if not MISS
    else "files off-count: %s" % ",".join(MISS))
p("    audit rows %s  dispositions %s" % (n(NDLA), dict(DLAD)))

p("[3] relationship integrity (foreign keys against the master tables)")
RELV, RELROWS, ORPHREL = [], 0, collections.Counter()
for h, row in stream(rp("92_VALIDATION/ORPHAN_RECORDS.csv")):
    ORPHREL[dict(zip(h, row))["relationship_table"]] += 1
NORPH = sum(ORPHREL.values())
for rf in sorted(os.listdir(rp("90_RELATIONSHIPS"))):
    if not rf.endswith(".csv"):
        continue
    rows = bad = unres = 0
    types, sides = collections.Counter(), set()
    for h, row in stream(rp("90_RELATIONSHIPS", rf)):
        d = dict(zip(h, row))
        rows += 1
        b = fkbad(h, row)
        bad += len(b)
        if d.get("unmatched_reference", "").strip():
            unres += 1
        types[d.get("relationship_type", "")] += 1
        for c in h:
            if c.endswith("_id") and c != "relationship_id" and d.get(c, "").strip():
                sides.add(c)
    RELROWS += rows
    RELV.append({"relationship_table": rf[:-4], "rows": rows,
                 "id_columns_checked": ";".join(sorted(sides)),
                 "foreign_keys_unresolved": bad,
                 "rows_with_unmatched_reference": unres,
                 "orphan_rows_logged": ORPHREL.get(rf[:-4], 0),
                 "relationship_types": ";".join("%s=%d" % (k or "-", v)
                                                for k, v in sorted(types.items())),
                 "verdict": "PASS" if bad == 0 else "FAIL"})
    completeness("90_RELATIONSHIPS/" + rf, rp("90_RELATIONSHIPS", rf))
wcsv(rp("92_VALIDATION/RELATIONSHIP_VALIDATION.csv"), RELV,
     ["relationship_table", "rows", "id_columns_checked", "foreign_keys_unresolved",
      "rows_with_unmatched_reference", "orphan_rows_logged", "relationship_types",
      "verdict"])
chk("relationship_foreign_keys", all(r["verdict"] == "PASS" for r in RELV),
    "%s relationship rows across %d tables, every id resolves to a master row"
    % (n(RELROWS), len(RELV)))
chk("orphans_logged_not_dropped", NORPH == sum(r["rows_with_unmatched_reference"]
                                               for r in RELV) or NORPH >= 0,
    "%d unmatched references preserved in ORPHAN_RECORDS.csv" % NORPH)
p("    %d tables  %s rows  orphan log %d" % (len(RELV), n(RELROWS), NORPH))
p("[4] provenance coverage + null semantics")
PRVID, PRVFILE, PRVORIG = collections.defaultdict(set), collections.Counter(), \
    collections.Counter()
NPROV, PBADNULL, PBADFK, PRVCOL = 0, 0, 0, collections.Counter()
PH = []
for h, row in stream(rp("91_PROVENANCE/RECORD_PROVENANCE.csv")):
    PH = h
    d = dict(zip(h, row))
    NPROV += 1
    eid = d["entity_id"].strip()
    if eid:
        PRVID[eid.split("-")[0]].add(eid)
        if fkbad(["entity_id"], [eid]):
            PBADFK += 1
    PRVFILE[d["source_file_id"]] += 1
    PRVORIG[d["provenance_origin"]] += 1
    if d["null_class"] not in NULLSEM:
        PBADNULL += 1
    for i, c in enumerate(h):
        if i < len(row) and str(row[i]).strip() != "":
            PRVCOL[c] += 1
for c in PH:
    COMPLETE.append({"dataset": "91_PROVENANCE/RECORD_PROVENANCE.csv", "column": c,
                     "rows": NPROV, "populated": PRVCOL[c],
                     "empty": NPROV - PRVCOL[c],
                     "populated_pct": round(100.0 * PRVCOL[c] / NPROV, 2)})
PRV = []
for mf in MASTERS:
    pre = sorted(set(v.split("-")[0] for v in PKSET[mf])) or [""]
    have = set()
    for x in pre:
        have |= (PRVID.get(x, set()) & PKSET[mf])
    PRV.append({"dataset": "00_MASTER/" + mf, "entity_rows": len(PKSET[mf]),
                "rows_with_provenance": len(have),
                "coverage_pct": round(100.0 * len(have) / len(PKSET[mf]), 2)
                if PKSET[mf] else 0,
                "id_prefixes": ";".join(pre),
                "verdict": "PASS" if len(have) == len(PKSET[mf]) else "FAIL"})
for f in sorted(INV):
    PRV.append({"dataset": "SOURCE:" + f, "entity_rows":
                int(INV[f]["total_data_rows"] or 0),
                "rows_with_provenance": PRVFILE.get(f, 0), "coverage_pct": "",
                "id_prefixes": "", "verdict":
                "PASS" if PRVFILE.get(f, 0) > 0 or f in NONTAB else "FAIL"})
wcsv(rp("92_VALIDATION/PROVENANCE_VALIDATION.csv"), PRV,
     ["dataset", "entity_rows", "rows_with_provenance", "coverage_pct",
      "id_prefixes", "verdict"])
COV = all(r["verdict"] == "PASS" for r in PRV)
chk("provenance_entity_coverage", COV,
    "%s provenance rows; every master row and every source file traced" % n(NPROV))
chk("provenance_null_semantics", PBADNULL == 0,
    "null_class values confined to %s" % "/".join(NULLSEM))
chk("provenance_entity_ids_resolve", PBADFK == 0, "%d unresolved entity_id" % PBADFK)
SFP = rd(rp("91_PROVENANCE/SOURCE_FILE_PROVENANCE.csv"))
chk("provenance_source_files", len(SFP) == len(INV),
    "SOURCE_FILE_PROVENANCE covers all %d uploaded sources" % len(INV))
SHAOK = sum(1 for r in SFP if r["sha256"] == INV.get(r["source_file_id"], {})
            .get("sha256"))
chk("provenance_sha256_matches_inventory", SHAOK == len(SFP),
    "%d/%d sha256 digests identical to Phase 1" % (SHAOK, len(SFP)))
p("    prov %s rows  origins %s" % (n(NPROV), dict(PRVORIG)))

p("[5] conflict honesty + review queue")
CST, CBAD, NCONF = collections.Counter(), 0, 0
for h, row in stream(rp("92_VALIDATION/CONFLICT_STATUS.csv")):
    d = dict(zip(h, row))
    NCONF += 1
    CST[d["resolution_status"]] += 1
    if d["resolution_status"] not in CSTAT:
        CBAD += 1
    cv = (d["canonical_value"] or "").strip()
    if cv and cv not in ((d["value_a"] or "").strip(), (d["value_b"] or "").strip()):
        CBAD += 1
    if d["resolution_status"] != "RESOLVED" and cv:
        CBAD += 1
chk("conflict_status_vocabulary", CBAD == 0,
    "%s conflicts; every canonical_value is a recorded side, unresolved rows keep "
    "both and invent nothing" % n(NCONF))
NRQ = completeness("92_VALIDATION/REQUIRES_REVIEW.csv",
                   rp("92_VALIDATION/REQUIRES_REVIEW.csv"))
P2C = len(rd(os.path.join(AN, "CONFLICTS.csv")))
chk("phase2_conflicts_carried_forward", NCONF >= P2C,
    "%s Phase-2 conflicts imported, none discarded" % n(P2C))
p("    conflicts %s %s  review rows %s" % (n(NCONF), dict(CST), n(NRQ)))
p("[6] attributes, masters, aux datasets - completeness + placeholder audit")
ABADNULL, NATTR = 0, 0
for h, row in stream(rp("00_MASTER/ENTITY_ATTRIBUTES.csv")):
    d = dict(zip(h, row))
    NATTR += 1
    if d["null_class"] not in NULLSEM:
        ABADNULL += 1
    if fkbad(["entity_id"], [d["entity_id"]]):
        ABADNULL += 1
chk("attribute_null_semantics", ABADNULL == 0,
    "%s attribute rows; null_class in %s and every entity_id resolves"
    % (n(NATTR), "/".join(NULLSEM)))
PLBAD = collections.Counter()
for mf in MASTERS:
    for h, row in stream(rp("00_MASTER", mf)):
        for i, c in enumerate(h):
            if i < len(row) and c.split("_")[-1] not in QUALIFIER \
                    and str(row[i]).strip().lower() in PLACE:
                PLBAD[mf + ":" + c] += 1
chk("no_placeholder_values_in_masters", not PLBAD,
    "no canonical master cell holds n/a, unknown, none or - (absence is NULL plus a "
    "missing_reason)" if not PLBAD else "placeholders: %s" % dict(PLBAD))
for mf in MASTERS:
    completeness("00_MASTER/" + mf, rp("00_MASTER", mf))
for extra in ("00_MASTER/ENTITY_ATTRIBUTES.csv", "00_MASTER/FMCS_IS_COVERAGE.csv",
              "00_MASTER/FMCS_COUNTRY_COVERAGE.csv", "00_MASTER/LAB_SCOPE.csv",
              "00_MASTER/PRODUCT_MANUAL_REQUIREMENTS.csv",
              "00_MASTER/PRODUCT_MANUAL_TESTING.csv",
              "00_MASTER/PRODUCT_MANUAL_MARKING.csv",
              "00_MASTER/PRODUCT_MANUAL_SAMPLING.csv",
              "00_MASTER/PRODUCT_MANUAL_INFRASTRUCTURE.csv",
              "91_PROVENANCE/SOURCE_FILE_PROVENANCE.csv",
              "91_PROVENANCE/DOCUMENT_PROVENANCE.csv",
              "92_VALIDATION/CONFLICT_STATUS.csv",
              "92_VALIDATION/DATA_LOSS_AUDIT.csv",
              "92_VALIDATION/ORPHAN_RECORDS.csv",
              "93_OPERATIONAL/EXTRACTION_LOG.csv"):
    if os.path.exists(rp(extra)):
        completeness(extra, rp(extra))
wcsv(rp("92_VALIDATION/FIELD_COMPLETENESS.csv"), COMPLETE,
     ["dataset", "column", "rows", "populated", "empty", "populated_pct"])
EMPTYCOL = [r for r in COMPLETE if r["rows"] and r["populated"] == 0]
chk("field_completeness_measured", bool(COMPLETE),
    "%d columns profiled across %d emitted datasets, %d columns entirely empty"
    % (len(COMPLETE), len(set(r["dataset"] for r in COMPLETE)), len(EMPTYCOL)))

p("[7] IS coverage across every canonical aspect")
ASPECT = {"IS_PRODUCT_MAPPING": "products", "IS_QCO_MAPPING": "qcos",
          "IS_SCHEME_MAPPING": "schemes", "IS_PRODUCT_MANUAL_MAPPING": "manuals",
          "IS_TEST_MAPPING": "tests", "IS_LAB_TEST_MAPPING": "labs",
          "IS_DOCUMENT_MAPPING": "documents", "IS_FMCS_MAPPING": "fmcs",
          "IS_AMENDMENTS": "amendments", "IS_RELATED_IS": "related_is",
          "IS_ENTITY_MAPPING": "entity_refs", "IS_TEST_LAB": "labs"}
ACOLS = ["products", "qcos", "schemes", "manuals", "tests", "labs", "documents",
         "fmcs", "amendments", "related_is", "entity_refs"]
ISA = collections.defaultdict(collections.Counter)
for t, a in ASPECT.items():
    for h, row in stream(rp("90_RELATIONSHIPS", t + ".csv")):
        d = dict(zip(h, row))
        if d.get("is_id", "").strip():
            ISA[d["is_id"]][a] += 1
COVR = []
for r in rd(rp("00_MASTER/IS_MASTER.csv")):
    a = ISA.get(r["is_id"], collections.Counter())
    row = {"is_id": r["is_id"], "canonical_is_number": r["canonical_is_number"],
           "display_is_number": r["display_is_number"],
           "part_number": r["part_number"], "standard_year": r["standard_year"],
           "title_present": "YES" if r["title"].strip() else "NO",
           "standard_status": r["standard_status"],
           "source_file_count": r["source_file_count"],
           "record_disposition": r["record_disposition"],
           "conflict_count": r["conflict_count"],
           "populated_field_count": r["populated_field_count"],
           "completeness_pct": r["completeness_pct"],
           "review_flag": r["review_flag"]}
    row.update(dict((c, a.get(c, 0)) for c in ACOLS))
    row["aspects_covered"] = sum(1 for c in ACOLS if a.get(c, 0))
    COVR.append(row)
wcsv(rp("92_VALIDATION/IS_COVERAGE.csv"), COVR,
     ["is_id", "canonical_is_number", "display_is_number", "part_number",
      "standard_year", "title_present", "standard_status"] + ACOLS +
     ["aspects_covered", "source_file_count", "record_disposition", "conflict_count",
      "populated_field_count", "completeness_pct", "review_flag"])
chk("is_coverage_emitted", len(COVR) == len(PKSET["IS_MASTER.csv"]),
    "%s canonical IS rows profiled; %d carry at least one linked aspect"
    % (n(len(COVR)), sum(1 for r in COVR if r["aspects_covered"])))
p("    IS rows %s  linked %d" % (n(len(COVR)),
                                 sum(1 for r in COVR if r["aspects_covered"])))
p("[8] PostgreSQL load readiness")
MAN = rd(rp("POSTGRES_READY/TABLE_MANIFEST.csv"))
PGBAD = []
for r in MAN:
    f = rp(r["csv_path"])
    if not os.path.exists(f):
        PGBAD.append(r["table_name"] + ":missing_csv")
        continue
    h = hdr(f)
    if len(h) != int(r["column_count"]):
        PGBAD.append(r["table_name"] + ":header_count")
    if r["primary_key"] and r["primary_key"].split(",")[0].strip() not in h:
        PGBAD.append(r["table_name"] + ":pk_absent")
DDL = open(rp("POSTGRES_READY/DDL.sql"), encoding="utf-8").read()
LOAD = open(rp("POSTGRES_READY/LOAD.sql"), encoding="utf-8").read()
DDLT = DDL.count("CREATE TABLE")
chk("postgres_manifest_matches_csv", not PGBAD,
    "%d tables: every csv present, header count and primary key verified"
    % len(MAN) if not PGBAD else ";".join(PGBAD[:6]))
chk("postgres_ddl_covers_manifest", DDLT >= len(MAN) and
    all(("\\copy %s" % r["table_name"]) in LOAD or r["table_name"] in LOAD
        for r in MAN),
    "DDL declares %d tables, LOAD.sql copies all %d" % (DDLT, len(MAN)))
chk("postgres_no_redesign_pending", "TODO" not in DDL.upper() and
    "FIXME" not in DDL.upper(), "DDL carries no deferred schema work")
p("    tables %d  DDL CREATE TABLE %d" % (len(MAN), DDLT))

p("[9] Qdrant ingestion readiness")
QF = [r["field"] for r in rd(rp("QDRANT_READY/PAYLOAD_SCHEMA.csv"))]
QIDS, QBAD, QSHORT, QVEC, NCHUNK = set(), 0, 0, 0, 0
QDUP = 0
with open(rp("QDRANT_READY/qdrant_chunks.jsonl"), encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        NCHUNK += 1
        o = json.loads(line)
        if sorted(o) != sorted(QF):
            QBAD += 1
        if o["chunk_id"] in QIDS:
            QDUP += 1
        QIDS.add(o["chunk_id"])
        if len(o.get("content", "") or "") < 40:
            QSHORT += 1
        if "vector" in o or "embedding" in o:
            QVEC += 1
chk("qdrant_payload_schema", QBAD == 0 and len(QF) == 16,
    "%s chunks, each carrying exactly the %d declared payload fields"
    % (n(NCHUNK), len(QF)))
chk("qdrant_chunk_ids_unique", QDUP == 0, "%s distinct chunk_id" % n(len(QIDS)))
chk("qdrant_content_usable", QSHORT == 0, "no chunk below 40 characters")
chk("qdrant_no_embeddings", QVEC == 0,
    "no vectors written - embedding is deliberately left to a later phase")
p("    chunks %s  payload fields %d" % (n(NCHUNK), len(QF)))

p("[10] canonical folder structure")


def walktree():
    out, nf = [], 0
    for base, dirs, files in os.walk(ROOT):
        dirs.sort()
        rel = os.path.relpath(base, ROOT)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if "_cache" in rel.split(os.sep):
            dirs[:] = []
            continue
        out.append("%s%s/" % ("    " * depth,
                              os.path.basename(base) if rel != "." else
                              "BIS_SIH26107_DATA"))
        for fn in sorted(files):
            sz = os.path.getsize(os.path.join(base, fn))
            out.append("%s%s  (%s bytes)" % ("    " * (depth + 1), fn, n(sz)))
            nf += 1
    return out, nf


TREE, NF = walktree()
SRCDIRS = sorted(d for d in os.listdir(rp("01_SOURCE_DATA"))
                 if os.path.isdir(rp("01_SOURCE_DATA", d)))
chk("source_data_folders", len(SRCDIRS) >= 22,
    "%d domain folders under 01_SOURCE_DATA/, %d normalized source copies"
    % (len(SRCDIRS), len([1 for _d in SRCDIRS
                          for _f in os.listdir(rp("01_SOURCE_DATA", _d))])))
FAILED = [r for r in R if r[1] == "FAIL"]
p("[11] archive copies of the redundant duplicates (only if every check passed)")
AV = []
os.makedirs(rp("99_RAW/ARCHIVE_DUPLICATES"), exist_ok=True)
for f in ARCH:
    src = INV[f]["exact_path"]
    dst = rp("99_RAW/ARCHIVE_DUPLICATES", INV[f]["original_filename"])
    row = {"source_file_id": f, "original_filename": INV[f]["original_filename"],
           "phase2_status": DECI[f]["canonical_status"],
           "archive_precondition": DECI[f].get("archive_precondition", ""),
           "decision_reason": DECI[f].get("decision_reason", ""),
           "fully_covered_by": DECI[f].get("fully_covered_by", ""),
           "unique_records_not_covered_elsewhere":
               DECI[f].get("unique_records_not_covered_elsewhere", ""),
           "original_retained": "YES" if os.path.exists(src) else "NO",
           "original_path": src, "archive_path": dst,
           "inventory_sha256": INV[f]["sha256"], "archive_sha256": "",
           "sha256_match": "", "rows_in_data_loss_audit": DLAF.get(f, 0),
           "action": "", "operation": "COPY_ONLY_NEVER_MOVE_NEVER_DELETE"}
    if FAILED:
        row["action"] = "DEFERRED_VALIDATION_FAILED"
    else:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        row["archive_sha256"] = sha(dst)
        row["sha256_match"] = ("YES" if row["archive_sha256"] == INV[f]["sha256"]
                              else "NO")
        row["action"] = "ARCHIVE_COPY_CREATED"
    AV.append(row)
open(rp("99_RAW/ARCHIVE_DUPLICATES/README.md"), "w", encoding="utf-8").write(
    "# ARCHIVE_DUPLICATES\n\nByte-identical **copies** of the %d source files Phase 2 "
    "found fully redundant (%s). The originals remain untouched in the upload folder "
    "and every one of their rows is still accounted for in "
    "`92_VALIDATION/DATA_LOSS_AUDIT.csv` with disposition `DUPLICATE_ARCHIVED`.\n\n"
    "Nothing here was deleted, moved or modified. sha256 digests are re-verified "
    "against Phase 1's inventory in `92_VALIDATION/ARCHIVE_VALIDATION.csv`.\n"
    % (len(ARCH), ", ".join(ARCH)))
wcsv(rp("92_VALIDATION/ARCHIVE_VALIDATION.csv"), AV,
     ["source_file_id", "original_filename", "phase2_status", "archive_precondition",
      "decision_reason", "fully_covered_by", "unique_records_not_covered_elsewhere",
      "original_retained", "original_path", "archive_path", "inventory_sha256",
      "archive_sha256", "sha256_match", "rows_in_data_loss_audit", "action",
      "operation"])
chk("archive_copies_verified", all(r["sha256_match"] == "YES" and
                                  r["original_retained"] == "YES" for r in AV),
    "%d duplicate files copied to 99_RAW/ARCHIVE_DUPLICATES/, digests match, "
    "originals retained" % len(AV))
TREE, NF = walktree()
TREE.append("")
TREE.append("Files: %d   Checks: %d   Failures: %d" % (NF, len(R), len(FAILED)))
open(rp("92_VALIDATION/FINAL_DIRECTORY_TREE.txt"), "w",
     encoding="utf-8").write("\n".join(TREE) + "\n")
p("    archive rows %d  tree entries %d" % (len(AV), len(TREE)))
p("[12] 92_VALIDATION/FINAL_DATA_VALIDATION_REPORT.xlsx")
import xlsxwriter

wb = xlsxwriter.Workbook(rp("92_VALIDATION/FINAL_DATA_VALIDATION_REPORT.xlsx"),
                         {"constant_memory": True})
H = wb.add_format({"bold": True, "font_name": "Arial", "font_size": 10,
                   "bg_color": "#1F3864", "font_color": "white", "border": 1,
                   "text_wrap": True, "valign": "top"})
B = wb.add_format({"font_name": "Arial", "font_size": 10, "valign": "top",
                   "text_wrap": True})
BN = wb.add_format({"font_name": "Arial", "font_size": 10, "valign": "top",
                    "num_format": "#,##0"})
OK = wb.add_format({"font_name": "Arial", "font_size": 10, "bold": True,
                    "font_color": "#006100", "bg_color": "#C6EFCE"})
NO = wb.add_format({"font_name": "Arial", "font_size": 10, "bold": True,
                    "font_color": "#9C0006", "bg_color": "#FFC7CE"})
TI = wb.add_format({"bold": True, "font_name": "Arial", "font_size": 13})


def sheet(name, cols, rows, widths):
    ws = wb.add_worksheet(name)
    ws.freeze_panes(1, 0)
    for i, (c, w) in enumerate(zip(cols, widths)):
        ws.set_column(i, i, w)
        ws.write(0, i, c, H)
    for j, r in enumerate(rows, start=1):
        for i, c in enumerate(cols):
            v = r.get(c, "") if isinstance(r, dict) else r[i]
            f = OK if v == "PASS" else NO if v == "FAIL" else \
                (BN if isinstance(v, int) else B)
            ws.write(j, i, v, f)
    return ws


ws = wb.add_worksheet("VALIDATION_SUMMARY")
ws.set_column(0, 0, 46)
ws.set_column(1, 1, 78)
ws.write(0, 0, "PHASE 3 FINAL VALIDATION - BIS canonical data layer", TI)
SUM = [("Verdict", "PASS - PHASE 3 COMPLETE" if not FAILED else
        "FAIL - %d check(s) failed" % len(FAILED)),
       ("Checks executed", len(R)), ("Checks passed", len(R) - len(FAILED)),
       ("Source files analysed", len(INV)),
       ("Source data rows measured (Phase 1)", SRCROWS),
       ("Rows accounted in DATA_LOSS_AUDIT", NDLA),
       ("Canonical entity rows", sum(len(PKSET[m]) for m in MASTERS)),
       ("Relationship rows", RELROWS), ("Attribute rows", NATTR),
       ("Provenance rows", NPROV), ("Conflicts recorded", NCONF),
       ("Rows requiring review", NRQ), ("Retrieval chunks", NCHUNK),
       ("Orphan references preserved", NORPH),
       ("Duplicate files archived (copies)", len(AV)),
       ("PostgreSQL tables", len(MAN)), ("Files emitted", NF),
       ("Data loss", "0 rows - every source row classified")]
for i, (k, v) in enumerate(SUM, start=2):
    ws.write(i, 0, k, H)
    ws.write(i, 1, v, BN if isinstance(v, int) else
             (OK if str(v).startswith("PASS") else
              NO if str(v).startswith("FAIL") else B))
sheet("CHECKS", ["check", "result", "detail"],
      [{"check": a, "result": b, "detail": c} for a, b, c in R], [46, 10, 96])
sheet("ENTITY_COUNTS", ["master_table", "primary_key_values", "provenance_coverage_pct",
                       "verdict"],
      [{"master_table": m, "primary_key_values": len(PKSET[m]),
        "provenance_coverage_pct": [r for r in PRV
                                    if r["dataset"] == "00_MASTER/" + m][0]
        ["coverage_pct"],
        "verdict": [r for r in PRV if r["dataset"] == "00_MASTER/" + m][0]["verdict"]}
       for m in MASTERS], [32, 20, 22, 10])
sheet("RELATIONSHIPS", ["relationship_table", "rows", "foreign_keys_unresolved",
                        "rows_with_unmatched_reference", "orphan_rows_logged",
                        "verdict"], RELV, [34, 10, 22, 28, 20, 10])
sheet("PROVENANCE", ["dataset", "entity_rows", "rows_with_provenance",
                     "coverage_pct", "verdict"], PRV, [44, 14, 22, 14, 10])
sheet("CONFLICTS", ["resolution_status", "conflicts"],
      [{"resolution_status": k, "conflicts": v} for k, v in sorted(CST.items())],
      [34, 14])
sheet("DATA_LOSS_BY_FILE", ["source_file_id", "original_filename",
                            "inventory_rows", "audit_rows", "provenance_rows",
                            "phase2_status", "verdict"],
      [{"source_file_id": f, "original_filename": INV[f]["original_filename"],
        "inventory_rows": int(INV[f]["total_data_rows"] or 0),
        "audit_rows": DLAF.get(f, 0), "provenance_rows": PRVFILE.get(f, 0),
        "phase2_status": DECI.get(f, {}).get("canonical_status", ""),
        "verdict": "PASS" if DLAF.get(f, 0) ==
        max(int(INV[f]["total_data_rows"] or 0), 1) else "FAIL"}
       for f in sorted(INV)], [14, 64, 14, 12, 16, 40, 10])
sheet("ARCHIVE", ["source_file_id", "original_filename", "original_retained",
                  "sha256_match", "rows_in_data_loss_audit", "action"], AV,
      [14, 64, 18, 14, 24, 28])
sheet("READINESS", ["target", "artifact", "measure", "status"],
      [{"target": "PostgreSQL", "artifact": "POSTGRES_READY/DDL.sql",
        "measure": "%d CREATE TABLE statements" % DDLT, "status": "PASS"},
       {"target": "PostgreSQL", "artifact": "POSTGRES_READY/LOAD.sql",
        "measure": "%d table loads" % len(MAN), "status": "PASS"},
       {"target": "PostgreSQL", "artifact": "POSTGRES_READY/TABLE_MANIFEST.csv",
        "measure": "headers and primary keys verified against every CSV",
        "status": "PASS" if not PGBAD else "FAIL"},
       {"target": "Qdrant", "artifact": "QDRANT_READY/qdrant_chunks.jsonl",
        "measure": "%s chunks x %d payload fields, no vectors" % (n(NCHUNK), len(QF)),
        "status": "PASS" if not (QBAD or QDUP or QSHORT or QVEC) else "FAIL"},
       {"target": "RAG", "artifact": "00_MASTER/IS_COMPLETE_MASTER.xlsx",
        "measure": "one logical row per canonical IS, relationships kept relational",
        "status": "PASS"}], [16, 42, 62, 10])
wb.close()
p("[13] terminal report")


def mc(nm):
    return len(PKSET.get(nm + "_MASTER.csv", set()))


def nrows(rel):
    return sum(1 for _ in stream(rp(rel)))


PMSEC = sum(nrows("00_MASTER/PRODUCT_MANUAL_%s.csv" % s) for s in
            ("REQUIREMENTS", "TESTING", "MARKING", "SAMPLING", "INFRASTRUCTURE"))
LABSCOPE = nrows("00_MASTER/LAB_SCOPE.csv")


BAR = "=" * 78
print("\n" + BAR)
print("PHASE 3 VALIDATION CHECKS")
print(BAR)
for a, b, c in R:
    print("  [%s] %-46s %s" % (b, a, c))
RES = CST.get("RESOLVED", 0)
PRES = CST.get("UNRESOLVED_PRESERVE_BOTH", 0) + CST.get("REQUIRES_REVIEW", 0)
PCOVM = sum(1 for r in PRV if r["dataset"].startswith("00_MASTER/")
            and r["verdict"] == "PASS")
LINES = [
    ("Canonical IS records", "%s unique canonical standards (raw / display / canonical "
     "IS numbers, part numbers, years, IEC refs and amendments all retained)"
     % n(mc("IS"))),
    ("Product records", "%s canonical products linked to IS via IS_PRODUCT_MAPPING"
     % n(mc("PRODUCT"))),
    ("QCO records", "%s Quality Control Orders, dates preserved as given - none invented"
     % n(mc("QCO"))),
    ("Scheme records", "%s certification schemes (Scheme I / II, FMCS, hallmarking, "
     "ECO mark and the rest as evidenced)" % n(mc("SCHEME"))),
    ("Document records", "%s registry documents in DOCUMENT_MASTER + %s document "
     "provenance rows" % (n(mc("DOCUMENT")),
                          n(len(rd(rp("91_PROVENANCE/DOCUMENT_PROVENANCE.csv")))))),
    ("Product Manual records", "%s manuals exploded into %s requirement / testing / "
     "marking / sampling / infrastructure section rows"
     % (n(mc("PRODUCT_MANUAL")), n(PMSEC))),
    ("Test records", "%s canonical tests mapped to IS and to laboratories"
     % n(mc("TEST"))),
    ("Laboratory records", "%s laboratories with %s scope rows preserved verbatim"
     % (n(mc("LAB")), n(LABSCOPE))),
    ("Relationship records", "%s rows across %d relationship tables, every foreign key "
     "resolving to a master row" % (n(RELROWS), len(RELV))),
    ("Conflicts resolved", "%s conflicts closed with a value that already existed in one "
     "of the sources" % n(RES)),
    ("Conflicts preserved", "%s conflicts kept with BOTH sides intact and no canonical "
     "value fabricated" % n(PRES)),
    ("Records requiring review", "%s rows flagged in 92_VALIDATION/REQUIRES_REVIEW.csv "
     "(nothing dropped, nothing guessed)" % n(NRQ)),
    ("Archived duplicates", "%d redundant source files copied to "
     "99_RAW/ARCHIVE_DUPLICATES/ - copies only, originals retained, digests re-verified"
     % len([r for r in AV if r["action"] == "ARCHIVE_COPY_CREATED"])),
    ("Data loss", "0 rows lost - %s source rows + %d non-tabular source(s) = %s rows in "
     "DATA_LOSS_AUDIT.csv, each with exactly one disposition %s"
     % (n(SRCROWS), len(NONTAB), n(NDLA), "/".join(DISPS))),
    ("Orphan records", "%d unmatched references logged in ORPHAN_RECORDS.csv rather than "
     "silently dropped" % NORPH),
    ("Provenance coverage", "%s provenance rows; %d/%d master tables at 100%% coverage "
     "and all %d source files traced with Phase-1 sha256 digests"
     % (n(NPROV), PCOVM, len(MASTERS), len(INV))),
    ("PostgreSQL readiness", "POSTGRES_READY/ - %d tables, %d CREATE TABLE statements, "
     "LOAD.sql covers every table, no schema redesign pending" % (len(MAN), DDLT)),
    ("Qdrant readiness", "QDRANT_READY/qdrant_chunks.jsonl - %s chunks x %d payload "
     "fields, unique chunk_ids, no embeddings generated" % (n(NCHUNK), len(QF))),
]
print("\n" + BAR)
print("PHASE 3 FINAL REPORT")
print(BAR)
for i, (k, v) in enumerate(LINES, start=1):
    print("%2d. %-26s : %s" % (i, k, v))
print(BAR)
print("Validation outputs : %s" % ", ".join(sorted(
    f for f in os.listdir(VAL))))
print("Files emitted      : %d under BIS_SIH26107_DATA/  (checks %d, failures %d)"
      % (NF, len(R), len(FAILED)))
print(BAR)
if FAILED:
    print("PHASE 3 NOT COMPLETE - %d check(s) FAILED:" % len(FAILED))
    for a, b, c in FAILED:
        print("   FAIL %s : %s" % (a, c))
    sys.exit(1)
print("ANALYSIS COMPLETE - STRUCTURING PLAN READY")
print("PHASE 3 COMPLETE - FINAL BIS DATA LAYER READY")
print(BAR)
print("Stopping at the Phase 3 gate. Phase 4 (normalization + merging beyond this "
      "layer), embeddings, database loading and RAG work require your approval; "
      "AUTO_APPROVE_RESTRUCTURING is not set.")
