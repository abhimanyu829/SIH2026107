"""Completes provenance coverage for entities that were minted from a reference.

Some canonical entities exist because another record pointed at them (an IS number cited
in a circular, a scheme named in a product row). The build wrote their field provenance
only where a source column fed a field, so reference-minted entities carried none. This
pass closes the gap deterministically from evidence already on disk: each master row
records the exact source rows that produced it (source_file_ids / source_sheets /
source_rows), so one ENTITY_MINT provenance row is emitted per (entity, source row).
Nothing is inferred, nothing is invented, and re-running changes nothing because the
entity ids are already present the second time.
"""
import csv
import os
import sys

ROOT = ("/sessions/optimistic-gallant-gauss/mnt/SIH-DATASETS-EXCEL-SHEET/"
        "BIS_SIH26107_DATA")
csv.field_size_limit(50_000_000)
PRVP = os.path.join(ROOT, "91_PROVENANCE/RECORD_PROVENANCE.csv")
LABEL = {"IS_MASTER.csv": ("canonical_is_number", "IS"),
         "PRODUCT_MASTER.csv": ("product_name", "PRODUCT"),
         "QCO_MASTER.csv": ("qco_number", "QCO"),
         "SCHEME_MASTER.csv": ("scheme_name", "SCHEME"),
         "TEST_MASTER.csv": ("test_name", "TEST"),
         "LAB_MASTER.csv": ("lab_name", "LAB"),
         "DOCUMENT_MASTER.csv": ("title", "DOCUMENT"),
         "FAQ_MASTER.csv": ("question", "FAQ"),
         "NOTIFICATION_MASTER.csv": ("notification_number", "NOTIFICATION"),
         "LEGAL_MASTER.csv": ("provision_title", "LEGAL"),
         "PRODUCT_MANUAL_MASTER.csv": ("manual_title", "PRODUCT_MANUAL"),
         "HALLMARKING_MASTER.csv": ("centre_name", "HALLMARKING"),
         "FMCS_MASTER.csv": ("applicant_name", "FMCS")}


def stream(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        r = csv.reader(f)
        h = next(r, [])
        for row in r:
            yield h, row


HAVE, MAXSEQ, PH = set(), 0, []
FILEHAVE = set()
for h, row in stream(PRVP):
    PH = h
    e = row[h.index("entity_id")].strip()
    if e:
        HAVE.add(e)
    FILEHAVE.add(row[h.index("source_file_id")].strip())
    pid = row[0]
    if "-" in pid and pid.split("-")[-1].isdigit():
        MAXSEQ = max(MAXSEQ, int(pid.split("-")[-1]))
WID = len(PH) and len(row[0].split("-")[-1])
print("existing provenance rows carry %d entities, last id %s-%0*d"
      % (len(HAVE), row[0].split("-")[0], WID, MAXSEQ), flush=True)

new, per = [], {}
for mf in sorted(LABEL):
    mp = os.path.join(ROOT, "00_MASTER", mf)
    if not os.path.exists(mp):
        continue
    lab, etype = LABEL[mf]
    added = 0
    for h, row in stream(mp):
        d = dict(zip(h, row))
        eid = row[0].strip()
        if not eid or eid in HAVE:
            continue
        refs = [x for x in (d.get("source_rows", "") or "").split(";") if x.strip()]
        if not refs:
            refs = ["%s::" % f for f in
                    (d.get("source_file_ids", "") or "").split(";") if f.strip()]
        files = [x for x in (d.get("source_files", "") or "").split(";") if x.strip()]
        for ref in refs:
            fid, _, rest = ref.partition(":")
            sheet, _, rno = rest.partition(":")
            MAXSEQ += 1
            new.append({
                "provenance_id": "PRV-%0*d" % (WID, MAXSEQ),
                "provenance_origin": "ENTITY_MINT",
                "entity_type": etype, "entity_id": eid,
                "entity_label": d.get(lab, ""),
                "canonical_column": lab, "canonical_value": d.get(lab, ""),
                "source_file_id": fid,
                "source_file": files[0] if len(files) == 1 else
                ";".join(files),
                "source_sheet": "" if sheet == "-" else sheet,
                "source_row": rno, "source_column": "", "source_value": "",
                "null_class": "POPULATED" if (d.get(lab, "") or "").strip()
                else "NULL_UNKNOWN",
                "missing_reason": "" if (d.get(lab, "") or "").strip() else
                "Entity created from a reference; no source column supplied this field",
                "transformation_rule": "ENTITY_MINTED_FROM_REFERENCE",
                "merge_action": "REFERENCE_MINT", "rule_source": "P3_PROVENANCE_FILL",
                "record_disposition": d.get("record_disposition", "CANONICAL"),
                "source_url": d.get("source_url", ""),
                "source_title": d.get("source_reference_label", ""),
                "source_type": "REFERENCE_IN_SOURCE_ROW",
                "document_id": d.get("document_id", ""),
                "document_title": "", "page": "", "section": "", "clause": "",
                "version": d.get("version", ""),
                "effective_date": "", "document_hash": d.get("sha256", ""),
                "retrieved_at": d.get("retrieved_at", ""),
                "evidence_text": d.get("review_reason", "")
                or "Entity referenced by source row %s" % ref,
                "verification_status": "SOURCE_REFERENCE_ONLY",
                "confidence": d.get("confidence", "") or "MEDIUM"})
            added += 1
        HAVE.add(eid)
    if added:
        per[mf] = added

# Stream-only sources (conflict register, extraction log, review queue, country
# coverage) hold auxiliary records rather than domain entities, so no field-level
# provenance was written for them. Their rows are still source rows, so each one gets a
# provenance record naming the dataset it was materialized into verbatim - taken straight
# from the data-loss audit, which already recorded that routing.
AUXP = 0
for h, row in stream(os.path.join(ROOT, "92_VALIDATION/DATA_LOSS_AUDIT.csv")):
    d = dict(zip(h, row))
    if d["source_file_id"] in FILEHAVE:
        continue
    MAXSEQ += 1
    AUXP += 1
    new.append({
        "provenance_id": "PRV-%0*d" % (WID, MAXSEQ),
        "provenance_origin": "AUX_DATASET_ROW",
        "entity_type": d.get("entity_type", "") or d.get("route_target", ""),
        "entity_id": d.get("entity_id", ""),
        "entity_label": d.get("entity_label", ""),
        "canonical_column": d.get("route_target", ""), "canonical_value": "",
        "source_file_id": d["source_file_id"], "source_file": d["source_file"],
        "source_sheet": d["source_sheet"], "source_row": d["source_row"],
        "source_column": "", "source_value": "",
        "null_class": "POPULATED", "missing_reason": "",
        "transformation_rule": "VERBATIM_STREAM_TO_AUX_DATASET",
        "merge_action": "PRESERVE_VERBATIM", "rule_source": "P3_PROVENANCE_FILL",
        "record_disposition": d.get("record_disposition", ""),
        "source_url": "", "source_title": "",
        "source_type": "AUXILIARY_SOURCE_RECORD",
        "document_id": "", "document_title": "", "page": "", "section": "",
        "clause": "", "version": "", "effective_date": "", "document_hash": "",
        "retrieved_at": "",
        "evidence_text": d.get("disposition_reason", ""),
        "verification_status": "SOURCE_VERBATIM", "confidence": "HIGH"})
with open(PRVP, "a", newline="", encoding="utf-8-sig") as fh:
    w = csv.DictWriter(fh, fieldnames=PH, extrasaction="ignore",
                       quoting=csv.QUOTE_MINIMAL)
    for r in new:
        w.writerow(r)
print("appended %d provenance rows: entity mints %s, aux source rows %d"
      % (len(new), per, AUXP), flush=True)
sys.exit(0)
