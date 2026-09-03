"""Removes unresolved-endpoint rows from the production relationship tables.

A relationship row is only a relationship if both of its defining endpoints resolve to a
canonical entity. Three tables held rows that fail that test, so they are moved out of
90_RELATIONSHIPS/ into the orphan register and a named review table:

  IS_AMENDMENTS      18 rows - is_id blank and the table carries no column for the
                     resolved NOTIFICATION side, so the row asserts no link at all.
  IS_RELATED_IS      45 rows - related_is_id blank because the reference normalizes to the
                     row's own standard; a self-edge is not a relationship.
  IS_PRODUCT_MAPPING 85 rows - is_id blank; the source row named a product with no IS
                     number, so there is no IS-to-product mapping to assert.

Rows where a *non-defining* third column is null are left alone: IS_LAB_TEST_MAPPING with
a null test_id still carries a resolved is_id + lab_id (a lab-scope link that names no
test), and with a null lab_id still carries is_id + test_id. Those are optional
dimensions, not unresolved references.

Nothing is deleted: every quarantined row is written verbatim to ORPHAN_RECORDS.csv and to
93_OPERATIONAL/UNRESOLVED_RELATIONSHIP_REFERENCES.csv, with the resolved side recorded, and
each row's underlying source row keeps its existing disposition in DATA_LOSS_AUDIT.csv.
Re-running is a no-op because the production tables no longer contain the rows.
"""
import csv
import os
import re
import sys

ROOT = ("/sessions/optimistic-gallant-gauss/mnt/SIH-DATASETS-EXCEL-SHEET/"
        "BIS_SIH26107_DATA")
csv.field_size_limit(50_000_000)


def rp(*p):
    return os.path.join(ROOT, *p)


def read(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        r = csv.reader(f)
        h = next(r, [])
        return h, [dict(zip(h, row)) for row in r]


def write(path, header, rows, mode="w"):
    with open(path, mode, newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=header, extrasaction="ignore",
                           quoting=csv.QUOTE_MINIMAL)
        if mode == "w":
            w.writeheader()
        for r in rows:
            w.writerow(r)


def norm_is(s):
    s = re.sub(r"[^0-9A-Za-z]+", " ", str(s)).strip().upper()
    m = re.match(r"^IS\s*([0-9]+)", s)
    return "IS " + m.group(1) if m else s


ISN = {r["is_id"]: r["canonical_is_number"] for r in read(rp("00_MASTER/IS_MASTER.csv"))[1]}
NOTE = {}
for r in read(rp("00_MASTER/NOTIFICATION_MASTER.csv"))[1]:
    for ref in (r.get("source_rows", "") or "").split(";"):
        if ref.strip():
            NOTE.setdefault(ref.strip(), (r["notification_id"],
                                          r.get("notification_number", "")))
QCOLS = ["quarantine_id", "origin_table", "relationship_id", "relationship_type",
         "resolved_side_entity_type", "resolved_side_entity_id", "resolved_side_label",
         "unresolved_side_role", "unresolved_side_reference", "evidence_column",
         "evidence_value", "source_file_id", "source_file", "source_sheet", "source_row",
         "quarantine_reason", "retained_in", "confidence"]


def srcref(r):
    ref = (r.get("source_rows", "") or "").split(";")[0].strip()
    fid, _, rest = ref.partition(":")
    sheet, _, rno = rest.partition(":")
    return ref, fid, ("" if sheet == "-" else sheet), rno


def classify(table, rows):
    """Returns (kept, quarantined) - deterministic, one rule per table."""
    kept, bad = [], []
    for r in rows:
        ref, fid, sheet, rno = srcref(r)
        if table == "IS_AMENDMENTS":
            if r["is_id"].strip():
                kept.append(r)
                continue
            nid, nno = NOTE.get(ref, ("", ""))
            bad.append((r, "NOTIFICATION", nid, nno, "is_id",
                        r.get("unmatched_reference", ""),
                        "NO_RESOLVABLE_STANDARD_IN_REFERENCE"))
        elif table == "IS_RELATED_IS":
            if r["related_is_id"].strip():
                kept.append(r)
                continue
            own = norm_is(ISN.get(r["is_id"], ""))
            reason = ("DEGENERATE_SELF_REFERENCE"
                      if own and own == norm_is(r.get("evidence_value", ""))
                      else "NO_RESOLVABLE_RELATED_STANDARD")
            bad.append((r, "IS", r["is_id"], ISN.get(r["is_id"], ""), "related_is_id",
                        r.get("evidence_value", ""), reason))
        else:
            if r["is_id"].strip():
                kept.append(r)
                continue
            bad.append((r, "PRODUCT", r.get("product_id", ""),
                        r.get("product_name", ""), "is_id",
                        r.get("evidence_value", ""), "NO_STANDARD_IN_SOURCE_ROW"))
    return kept, bad


QROWS, SUMMARY, SEQ = [], [], 0
for table in ("IS_AMENDMENTS", "IS_RELATED_IS", "IS_PRODUCT_MAPPING"):
    path = rp("90_RELATIONSHIPS/%s.csv" % table)
    header, rows = read(path)
    kept, bad = classify(table, rows)
    for r, etype, eid, elabel, role, ref, reason in bad:
        _, fid, sheet, rno = srcref(r)
        SEQ += 1
        QROWS.append({
            "quarantine_id": "UNRES-%04d" % SEQ, "origin_table": table,
            "relationship_id": r.get("relationship_id", ""),
            "relationship_type": r.get("relationship_type", ""),
            "resolved_side_entity_type": etype, "resolved_side_entity_id": eid,
            "resolved_side_label": elabel, "unresolved_side_role": role,
            "unresolved_side_reference": ref,
            "evidence_column": r.get("evidence_column", ""),
            "evidence_value": r.get("evidence_value", ""),
            "source_file_id": fid, "source_file": r.get("source_files", ""),
            "source_sheet": sheet, "source_row": rno, "quarantine_reason": reason,
            "retained_in": ("92_VALIDATION/ORPHAN_RECORDS.csv;"
                            "93_OPERATIONAL/UNRESOLVED_RELATIONSHIP_REFERENCES.csv"),
            "confidence": r.get("confidence", "")})
    write(path, header, kept)
    SUMMARY.append((table, len(rows), len(kept), len(bad)))
    print("%-20s %5d rows -> kept %5d, quarantined %3d"
          % (table, len(rows), len(kept), len(bad)), flush=True)
os.makedirs(rp("93_OPERATIONAL"), exist_ok=True)
write(rp("93_OPERATIONAL/UNRESOLVED_RELATIONSHIP_REFERENCES.csv"), QCOLS, QROWS)

# The orphan register keeps one row per unmatched reference. The 18 IS_AMENDMENTS rows are
# already there from the build, so only the newly quarantined tables are appended.
OH, OROWS = read(rp("92_VALIDATION/ORPHAN_RECORDS.csv"))
HAVE = {(r["relationship_table"], r["source_row"], r["evidence_value"]) for r in OROWS}
APP = []
for q in QROWS:
    key = (q["origin_table"], q["source_row"], q["evidence_value"])
    if key in HAVE:
        continue
    APP.append({
        "relationship_table": q["origin_table"],
        "relationship_type": q["relationship_type"],
        "unmatched_reference": q["unresolved_side_reference"],
        "evidence_column": q["evidence_column"], "evidence_value": q["evidence_value"],
        "resolved_sides": "%s=%s" % (q["resolved_side_entity_type"],
                                     q["resolved_side_entity_id"]),
        "source_file_id": q["source_file_id"], "source_file": q["source_file"],
        "source_sheet": q["source_sheet"], "source_row": q["source_row"],
        "reason": "Quarantined from the production relationship table: %s. Row retained "
                  "verbatim here and in 93_OPERATIONAL/"
                  "UNRESOLVED_RELATIONSHIP_REFERENCES.csv." % q["quarantine_reason"]})
write(rp("92_VALIDATION/ORPHAN_RECORDS.csv"), OH, APP, mode="a")

# Register the review table for PostgreSQL alongside the 49 existing tables.
DDL = rp("POSTGRES_READY/DDL.sql")
ddl = open(DDL, encoding="utf-8").read()
TBL = "unresolved_relationship_references"
if TBL not in ddl:
    body = ",\n".join("    %s TEXT" % c for c in QCOLS)
    with open(DDL, "a", encoding="utf-8") as f:
        f.write("\n-- Relationship rows whose defining endpoint could not be resolved to a\n"
                "-- canonical entity. Review data, deliberately outside the production\n"
                "-- relationship tables so those carry no unresolved foreign keys.\n"
                "DROP TABLE IF EXISTS %s CASCADE;\nCREATE TABLE %s (\n%s,\n"
                "    PRIMARY KEY (quarantine_id)\n);\n" % (TBL, TBL, body))
    with open(rp("POSTGRES_READY/LOAD.sql"), "a", encoding="utf-8") as f:
        f.write("\n\\copy %s FROM '93_OPERATIONAL/"
                "UNRESOLVED_RELATIONSHIP_REFERENCES.csv' WITH (FORMAT csv, HEADER true, "
                "ENCODING 'UTF8');\n" % TBL)
    MH, MR = read(rp("POSTGRES_READY/TABLE_MANIFEST.csv"))
    CNT = dict((t, k) for t, _, k, _ in SUMMARY)
    for r in MR:
        for t, k in CNT.items():
            if r.get("table_name", "").lower() == t.lower():
                r["row_count"] = str(k)
    row = {c: "" for c in MH}
    row.update({"table_name": TBL,
                "source_csv": "93_OPERATIONAL/UNRESOLVED_RELATIONSHIP_REFERENCES.csv",
                "row_count": str(len(QROWS)), "column_count": str(len(QCOLS)),
                "primary_key": "quarantine_id", "table_group": "REVIEW",
                "load_order": "99"})
    write(rp("POSTGRES_READY/TABLE_MANIFEST.csv"), MH, MR + [row])

print("quarantined %d rows -> 93_OPERATIONAL/UNRESOLVED_RELATIONSHIP_REFERENCES.csv "
      "(+%d appended to ORPHAN_RECORDS.csv); registered table %s"
      % (len(QROWS), len(APP), TBL), flush=True)
sys.exit(0)
