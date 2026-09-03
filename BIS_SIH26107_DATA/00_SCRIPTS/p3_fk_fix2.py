"""Corrects the quarantine record written by p3_fk_fix.py.

p3_fk_fix.py parsed provenance with the wrong shape: relationship rows store the triple in
three parallel columns (source_file_ids / source_sheets / source_rows, the row column being
a bare number), not as one "Fxxx:sheet:row" string. The quarantine file therefore landed the
row number in source_file_id, left source_row empty, and could not resolve the NOTIFICATION
side of the 18 IS_AMENDMENTS rows. Appending those rows to ORPHAN_RECORDS.csv and then
de-duplicating on a key containing the empty source_row also collapsed distinct rows.

This pass rebuilds both files from evidence on disk:
  * file name -> file_id from FILE_INVENTORY.csv
  * sheet name recovered by matching (file_id, row) against the resolved entity's own
    source_rows triples in its master table
  * the 18 NOTIFICATION ids taken from the build's own ORPHAN_RECORDS rows, matched on
    (evidence_value, source_row)
ORPHAN_RECORDS.csv is rewritten as the build's original 18 rows plus one row for each of the
130 newly quarantined rows: 148 rows, one per quarantined relationship row, no duplicates.
"""
import csv
import os
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


def write(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=header, extrasaction="ignore",
                           quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        for r in rows:
            w.writerow(r)


FID = {}
for r in read(rp("01_ANALYSIS/FILE_INVENTORY.csv"))[1]:
    FID[r.get("original_filename", "").strip()] = r.get("file_id", "").strip()

# (file_id, row) -> sheet, from every master entity's recorded source triples.
SHEET = {}
for mf in os.listdir(rp("00_MASTER")):
    if not mf.endswith("_MASTER.csv"):
        continue
    h, rows = read(rp("00_MASTER", mf))
    if "source_rows" not in h:
        continue
    for r in rows:
        for ref in (r.get("source_rows", "") or "").split(";"):
            p = ref.strip().split(":")
            if len(p) == 3:
                SHEET.setdefault((p[0], p[2]), "" if p[1] == "-" else p[1])
OH, OROWS = read(rp("92_VALIDATION/ORPHAN_RECORDS.csv"))
BUILD18 = [r for r in OROWS
           if not r["reason"].startswith("Quarantined from the production")]
NOTEBY = {(r["evidence_value"], r["source_row"]): (r["resolved_sides"], r["source_file_id"],
                                                   r["source_sheet"])
          for r in BUILD18}
print("build-written orphan rows retained: %d" % len(BUILD18), flush=True)

QH, QROWS = read(rp("93_OPERATIONAL/UNRESOLVED_RELATIONSHIP_REFERENCES.csv"))
LABEL = {"IS_MASTER.csv": "canonical_is_number", "PRODUCT_MASTER.csv": "product_name",
         "NOTIFICATION_MASTER.csv": "notification_number"}
LOOK = {}
for mf, lab in LABEL.items():
    for r in read(rp("00_MASTER", mf))[1]:
        LOOK[r[list(r)[0]]] = r.get(lab, "")

FIXED, NEWORPH, unresolved_sheet = [], [], 0
for q in QROWS:
    # First pass reads the row number out of the mis-parsed source_file_id column; on a
    # re-run it is already in its proper place.
    rowno = q["source_row"].strip() or q["source_file_id"].strip()
    fname = q["source_file"].strip()
    fid = FID.get(fname, "")
    if q["origin_table"] == "IS_AMENDMENTS":
        rs, ofid, osheet = NOTEBY.get((q["evidence_value"], rowno), ("", "", ""))
        nid = rs.split("=")[-1] if rs else ""
        q["resolved_side_entity_id"] = nid
        q["resolved_side_label"] = LOOK.get(nid, "")
        fid = ofid or fid
        sheet = osheet
    else:
        sheet = SHEET.get((fid, rowno), "")
        q["resolved_side_label"] = (q["resolved_side_label"]
                                    or LOOK.get(q["resolved_side_entity_id"], ""))
    if not sheet:
        unresolved_sheet += 1
    q["source_file_id"], q["source_sheet"], q["source_row"] = fid, sheet, rowno
    FIXED.append(q)
    if q["origin_table"] != "IS_AMENDMENTS":
        NEWORPH.append({
            "relationship_table": q["origin_table"],
            "relationship_type": q["relationship_type"],
            "unmatched_reference": q["unresolved_side_reference"],
            "evidence_column": q["evidence_column"],
            "evidence_value": q["evidence_value"],
            "resolved_sides": "%s=%s" % (q["resolved_side_entity_type"],
                                         q["resolved_side_entity_id"]),
            "source_file_id": fid, "source_file": fname, "source_sheet": sheet,
            "source_row": rowno,
            "reason": "Quarantined from the production relationship table (%s): the "
                      "defining %s could not be resolved to a canonical entity. Row kept "
                      "verbatim in 93_OPERATIONAL/UNRESOLVED_RELATIONSHIP_REFERENCES.csv."
                      % (q["quarantine_reason"], q["unresolved_side_role"])})

write(rp("93_OPERATIONAL/UNRESOLVED_RELATIONSHIP_REFERENCES.csv"), QH, FIXED)
write(rp("92_VALIDATION/ORPHAN_RECORDS.csv"), OH, BUILD18 + NEWORPH)
print("quarantine rows repaired: %d (sheet unresolved for %d) | orphan register: %d rows "
      "= %d build-written + %d appended"
      % (len(FIXED), unresolved_sheet, len(BUILD18) + len(NEWORPH), len(BUILD18),
         len(NEWORPH)), flush=True)
miss = [q["quarantine_id"] for q in FIXED
        if not q["resolved_side_entity_id"].strip() or not q["source_row"].strip()]
print("rows still missing a resolved id or row number: %d %s"
      % (len(miss), miss[:6]), flush=True)
sys.exit(0)
