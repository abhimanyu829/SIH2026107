#!/usr/bin/env python3
"""PHASE 3A - DESIGN FIRST.

Renders 03_CANONICAL_DESIGN/CANONICAL_DATA_MODEL.xlsx with exactly the 10 mandated
sheets. Reads nothing but the Phase 1 / Phase 2 analysis CSVs and the declarative
model in p3_model.py, and writes nothing except the workbook - no source file is
opened for transformation at this stage, because the design must exist before any
data moves.

Every sheet carries a `basis_evidence` (or equivalently named) column so each
decision states the measured fact it rests on, rather than leaving the reader to
guess. That satisfies "document every assumption where the reader will see it"
without adding an 11th sheet.
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import p3_model as M                                              # noqa: E402
from p3_lib import TRANSFORMS                                     # noqa: E402
from p1_lib import norm_header                                    # noqa: E402

from openpyxl import Workbook                                     # noqa: E402
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side  # noqa: E402
from openpyxl.utils import get_column_letter                      # noqa: E402

csv.field_size_limit(50_000_000)

ROOT = "/sessions/optimistic-gallant-gauss/mnt/SIH-DATASETS-EXCEL-SHEET"
ANA = os.path.join(ROOT, "BIS_SIH26107_DATA", "01_ANALYSIS")
DESIGN_DIR = os.path.join(ROOT, "BIS_SIH26107_DATA", "03_CANONICAL_DESIGN")
OUT = os.path.join(DESIGN_DIR, "CANONICAL_DATA_MODEL.xlsx")

FONT = "Arial"
HDR_FILL = PatternFill("solid", fgColor="1F3864")
HDR_FONT = Font(name=FONT, size=10, bold=True, color="FFFFFF")
CELL_FONT = Font(name=FONT, size=10)
NOTE_FONT = Font(name=FONT, size=10, italic=True, color="7F7F7F")
KEY_FONT = Font(name=FONT, size=10, bold=True)
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
ZEBRA = PatternFill("solid", fgColor="F2F2F2")


def rd(name):
    """Read an analysis CSV. utf-8-sig because Phase 1 wrote a BOM."""
    with open(os.path.join(ANA, name), newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def sheet(wb, name, cols, rows, notes=(), widths=None, freeze="A2"):
    """Write one sheet: header row, data rows, then an italic notes block."""
    ws = wb.create_sheet(name)
    ws.append(list(cols))
    for c in range(1, len(cols) + 1):
        cell = ws.cell(row=1, column=c)
        cell.font, cell.fill, cell.border = HDR_FONT, HDR_FILL, BORDER
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    for i, r in enumerate(rows):
        ws.append(["" if v is None else v for v in r])
        for c in range(1, len(cols) + 1):
            cell = ws.cell(row=i + 2, column=c)
            cell.font = KEY_FONT if c == 1 else CELL_FONT
            cell.border = BORDER
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            if i % 2:
                cell.fill = ZEBRA
    ws.freeze_panes = freeze
    ws.row_dimensions[1].height = 30
    for i, w in enumerate(widths or [], start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    if notes:
        base = len(rows) + 3
        for j, n in enumerate(notes):
            cell = ws.cell(row=base + j, column=1, value=n)
            cell.font = NOTE_FONT
            cell.alignment = Alignment(vertical="top", wrap_text=False)
    ws.sheet_properties.tabColor = "1F3864"
    return ws


# ---------------------------------------------------------------------------
# analysis inputs
# ---------------------------------------------------------------------------
PROF = rd("COLUMN_PROFILING.csv")
CLS = rd("DATASET_CLASSIFICATION.csv")
INV = rd("FILE_INVENTORY.csv")
PLAN = rd("PHASE2_MERGE_PLAN.csv")
NULLSEM = rd("PHASE1_NULL_SEMANTICS.csv")
CONF = rd("CONFLICTS.csv")

INV_BY = {r["file_id"]: r for r in INV}
CLS_BY = {r["file_id"]: r for r in CLS}
DOMAIN_OF = {}
for _fid, _f in CLS_BY.items():
    DOMAIN_OF[_fid] = _f["primary_domain"]
FOLDER_OF = {}
for _folder, _ids in M.FOLDER_PLAN:
    for _i in [x for x in _ids.split(",") if x]:
        FOLDER_OF[_i] = _folder
STEP_OF = {}
for _p in PLAN:
    for _i in [x.strip() for x in _p["source_files"].split(",") if x.strip()]:
        STEP_OF[_i] = _p["step_id"]
NULLCOLS = {(r["file_id"], r["exact_column_name"]): r for r in NULLSEM}
CONF_FILES = set()
for _c in CONF:
    CONF_FILES.add(_c["file_a"])
    CONF_FILES.add(_c["file_b"])

wb = Workbook()
wb.remove(wb.active)
COUNTS = []


def add(name, cols, rows, notes=(), widths=None):
    sheet(wb, name, cols, rows, notes, widths)
    COUNTS.append((name, len(rows), len(cols)))


# ---------------------------------------------------------------------------
# 1. ENTITY_MODEL
# ---------------------------------------------------------------------------
ent_rows = []
for e, prefix, master, nk, note in M.ENTITIES:
    files = sorted(f for f, r in M.ROUTE.items() if r[0] == e)
    ent_rows.append([
        e, prefix, prefix + "-00001", master, e.lower() + "_id"
        if e != "STANDARD" else "is_id", nk, len(M.MASTER_COLS[e]),
        len(files), ",".join(files) or "(populated via merge from other entities)",
        note,
    ])
add("ENTITY_MODEL",
    ["canonical_entity", "id_prefix", "first_id", "master_dataset", "id_column",
     "natural_key", "master_column_count", "primary_source_file_count",
     "primary_source_file_ids", "definition_and_boundary"],
    ent_rows,
    ["13 entities, exactly as specified. Boundary decisions are stated per row so a "
     "reader can see why two look-alike things are not one entity.",
     "STANDARD's id column is is_id (not standard_id) because standard_id already "
     "exists as a per-file surrogate in 3 sources and is demoted to source_standard_ids.",
     "primary_source_file_ids lists files whose ROUTE target is this entity; an entity "
     "can also gain rows from a file routed elsewhere (e.g. QCO rows contribute products)."],
    [18, 9, 10, 26, 15, 34, 12, 12, 30, 90])

# ---------------------------------------------------------------------------
# 2. DATASET_MODEL
# ---------------------------------------------------------------------------
ds_rows = []
for e, prefix, master, nk, note in M.ENTITIES:
    ds_rows.append(["MASTER", master.replace(".csv", ""), "00_MASTER/" + master,
                    "CSV", e, len(M.MASTER_COLS[e]), "one row per canonical " +
                    e.lower().replace("_", " "),
                    "Identity + cross-file core fields only. Singleton/narrative "
                    "columns go to ENTITY_ATTRIBUTES so the master never becomes a "
                    "sparse 290-column table."])
for name, path, purpose in M.AUX_DATASETS:
    ds_rows.append(["AUXILIARY", name, path,
                    "XLSX" if path.endswith(".xlsx") else "CSV",
                    "(multi)" if name in ("ENTITY_ATTRIBUTES", "RECORD_PROVENANCE",
                                          "CONFLICT_REGISTER", "REVIEW_QUEUE")
                    else "", "", "see purpose", purpose])
for name, fname, a, b, keys, purpose in M.REL:
    ds_rows.append(["RELATIONSHIP", name, "90_RELATIONSHIPS/" + fname, "CSV",
                    a + " -> " + b, len(M.REL_COLS[name]), "many-to-many id pairs",
                    purpose])
ds_rows.append(["LOAD", "postgres_tables", "POSTGRES_READY/*.csv + schema.sql", "CSV",
                "(all)", "", "relational load", M.POSTGRES_NOTE])
ds_rows.append(["LOAD", "qdrant_chunks", "QDRANT_READY/qdrant_chunks.jsonl", "JSONL",
                "DOCUMENT", len(M.QDRANT_FIELDS), "one row per retrievable chunk",
                "Payload fields: " + ", ".join(M.QDRANT_FIELDS) +
                ". Embeddings are NOT generated in Phase 3."])
add("DATASET_MODEL",
    ["dataset_group", "dataset_name", "output_path", "file_format", "entity_scope",
     "column_count", "grain", "purpose_and_design_note"],
    ds_rows,
    ["13 masters + 16 auxiliary + 17 relationship tables + 2 load targets = 48 declared "
     "outputs.",
     "column_count is blank where the width is data-driven (long-format tables) rather "
     "than fixed by this design.",
     "IS_COMPLETE_MASTER.xlsx is the 3M denormalised reading view; it is derived from the "
     "masters and relationships, never the source of truth."],
    [15, 30, 44, 11, 22, 11, 26, 96])

# ---------------------------------------------------------------------------
# 3. COLUMN_MAPPING  - one row per source column, all 685
# ---------------------------------------------------------------------------
cm_rows = []
unresolved = []
for p in PROF:
    fid = p["file_id"]
    exact = p["exact_column_name"]
    nh = p["normalized_column_name"] or norm_header(exact)
    route = M.ROUTE.get(fid)
    entity = route[0] if route else ""
    canon, sem, action, tname, target, src = M.resolve(fid, exact, entity)
    if tname and tname not in TRANSFORMS:
        unresolved.append((fid, exact, tname))
    ns = NULLCOLS.get((fid, exact))
    basis = ("%s%% populated, %s distinct of %s rows" %
             (p["percentage_populated"], p["unique_count"], p["total_rows"]))
    if p["is_multivalue_field"].strip().upper() in ("TRUE", "YES", "1"):
        basis += "; measured multi-value ratio %s -> explode to relationship rows" % \
                 p["multivalue_ratio"]
    if ns:
        basis += "; Phase 1 null policy %s (%s x %s)" % (
            ns["null_policy"], ns["placeholder_token"], ns["occurrences"])
    if src == "FILE_OVERRIDE":
        basis += "; file-specific rule (measured shape differs from the shared column name)"
    elif src == "ENTITY_SCOPED_HOMONYM":
        basis += "; homonym resolved by entity - NOT merged with same-named columns elsewhere"
    elif src == "DEFAULT_ATTRIBUTE":
        basis += "; no cross-file counterpart -> preserved losslessly as an attribute row"
    cm_rows.append([
        fid, p["original_filename"], p["sheet_name"], exact, nh, entity, canon, sem,
        action, tname, target, src, p["data_type"], p["percentage_populated"],
        p["is_multivalue_field"], basis,
    ])
add("COLUMN_MAPPING",
    ["file_id", "source_file", "source_sheet", "source_column", "normalized_column",
     "canonical_entity", "canonical_column", "semantic_type", "merge_action",
     "transformation_rule", "target_dataset", "rule_source", "measured_data_type",
     "percentage_populated", "is_multivalue_field", "basis_evidence"],
    cm_rows,
    ["One row for every one of the 685 source columns measured in Phase 1. Nothing is "
     "omitted, so no column can be silently dropped (Zero Data Loss Rule).",
     "rule_source shows which of the four precedence tiers decided the row: "
     "FILE_OVERRIDE > ENTITY_SCOPED > CMAP > DEFAULT_ATTRIBUTE.",
     "merge_action PRESERVE_AS_ATTRIBUTE means the value is kept in long format in "
     "00_MASTER/ENTITY_ATTRIBUTES.csv - preserved, not discarded.",
     "The 19 'scope' homonyms are split by canonical_column (document_scope, qco_scope, "
     "certification_scope, hallmarking_scope, assessment_scope, standard_scope, "
     "laboratory_scope) and are never blindly combined.",
     "transformation_rule names a callable in p3_lib.TRANSFORMS, so this sheet and the "
     "build scripts cannot drift apart."],
    [8, 34, 22, 34, 30, 16, 32, 18, 30, 22, 26, 18, 13, 12, 12, 100])

# ---------------------------------------------------------------------------
# 4. MERGE_RULES
# ---------------------------------------------------------------------------
mr_rows = []
for p in sorted(PLAN, key=lambda r: int(r["execution_order"])):
    ids = [x.strip() for x in p["source_files"].split(",") if x.strip()]
    mr_rows.append([
        p["step_id"], p["execution_order"], p["target_canonical_dataset"],
        p["target_domain"], p["source_files"], p["source_file_count"],
        p["join_key"], p["join_key_status"], p["input_records"],
        p["expected_output_records_min"], p["expected_output_records_max"],
        p["conflicts_to_carry"], p["different_entity_splits"], p["merge_rule"],
        p["conflict_rule"], p["null_rule"], p["blocking_precondition"],
        p["requires_human_approval"],
        "Union on the stated join key, never on row order and never on filename "
        "priority. Unique columns from every contributor are carried; unique records "
        "are added; conflicting values are preserved on both sides with provenance." +
        ("" if not [i for i in ids if i in M.ARCHIVE_AFTER_VALIDATION] else
         " Includes archivable file(s) " +
         ",".join(i for i in ids if i in M.ARCHIVE_AFTER_VALIDATION) +
         " - their records are incorporated BEFORE any archive copy is made."),
    ])
add("MERGE_RULES",
    ["step_id", "execution_order", "target_canonical_dataset", "target_domain",
     "source_files", "source_file_count", "join_key", "join_key_status",
     "input_records", "expected_output_min", "expected_output_max",
     "conflicts_to_carry", "different_entity_splits", "merge_rule", "conflict_rule",
     "null_rule", "blocking_precondition", "requires_human_approval",
     "phase3_execution_note"],
    mr_rows,
    ["PHASE2_MERGE_PLAN.csv is applied exactly - the 14 steps, order, join keys and "
     "expected record bounds are reproduced here unchanged, not re-derived.",
     "expected_output_min/max are the Phase 2 conservation bounds. A merge landing "
     "outside them is a defect and fails 92_VALIDATION/DATA_LOSS_AUDIT.csv.",
     "BIS_Schemes_Master and BIS_Schemes_Master_Scheme_2 stay DIFFERENT_ENTITY: they "
     "are never collapsed into one scheme row.",
     "Filename is never evidence: no step uses v2/v3/(1) naming to pick a winner."],
    [9, 9, 26, 22, 26, 8, 26, 15, 11, 12, 12, 11, 11, 46, 40, 34, 34, 11, 96])

# ---------------------------------------------------------------------------
# 5. ID_RULES
# ---------------------------------------------------------------------------
id_rows = []
for prefix, obj, dataset, nk, fmt, note in M.ID_RULES:
    id_rows.append([prefix, obj, dataset, nk, fmt,
                    "deterministic - Mint collects natural keys, seal() numbers them "
                    "in sorted order, so a re-run of the same corpus reproduces the "
                    "same ids", note])
add("ID_RULES",
    ["id_prefix", "object", "owning_dataset", "natural_key", "id_format",
     "stability_guarantee", "notes"],
    id_rows,
    ["The 10 mandated entity prefixes (STD, PROD, QCO, SCH, PM, TEST, LAB, DOC, FAQ, "
     "NOTIF) plus LEGAL, HM, FMCS for the remaining 3 entities, plus REL/ATTR/CONF/CHUNK "
     "for generated rows.",
     "Every relationship table joins on these ids only - never on a title, a filename "
     "or a row position.",
     "Source surrogate keys (standard_id, product_id, ... in 20 places) are DEMOTED to "
     "source_*_ids and never reused as canonical ids: two files reuse the same integers "
     "for different entities."],
    [11, 20, 30, 36, 74, 46, 88])

# ---------------------------------------------------------------------------
# 6. RELATIONSHIP_MODEL
# ---------------------------------------------------------------------------
rel_rows = []
MANDATED = {"IS_PRODUCT_MAPPING", "IS_QCO_MAPPING", "IS_SCHEME_MAPPING",
            "IS_DOCUMENT_MAPPING", "IS_TEST_MAPPING", "IS_LAB_TEST_MAPPING",
            "IS_RELATED_IS", "QCO_SCHEME_MAPPING", "PRODUCT_DOCUMENT_MAPPING",
            "TEST_LAB_MAPPING", "NOTIFICATION_ENTITY_MAPPING"}
for name, fname, a, b, keys, purpose in M.REL:
    rel_rows.append([
        name, "90_RELATIONSHIPS/" + fname, a, b, ", ".join(keys),
        ", ".join(M.REL_COLS[name]), "many-to-many",
        "SPEC_MANDATED" if name in MANDATED else "REQUIRED_BY_MEASURED_DATA",
        purpose,
        "Populated by exploding measured multi-value columns; every row keeps "
        "evidence_column + evidence_value + source_rows, and an id that could not be "
        "matched is kept in unmatched_reference with review_flag rather than dropped.",
    ])
add("RELATIONSHIP_MODEL",
    ["relationship_table", "output_path", "from_entity", "to_entity", "key_columns",
     "all_columns", "cardinality", "origin", "purpose", "population_rule"],
    rel_rows,
    ["11 tables are named in the specification; 6 more exist because Phase 1 measured "
     "multi-value columns that would otherwise have to be flattened into cells.",
     "No relationship is stored as a comma-separated list anywhere in the canonical "
     "layer - the list survives in ENTITY_ATTRIBUTES only as the original evidence string.",
     "relation_context distinguishes same-shaped edges from different regimes (e.g. FMCS "
     "vs domestic), so an edge is never merged on shape alone."],
    [30, 46, 16, 16, 44, 78, 14, 24, 70, 96])

# ---------------------------------------------------------------------------
# 7. CONFLICT_POLICY
# ---------------------------------------------------------------------------
cp_rows = []
for i, (pattern, detect, status, reason, conf) in enumerate(M.CONFLICT_POLICY, 1):
    cp_rows.append(["CP-%02d" % i, pattern, detect, status, conf, reason,
                    "Both sides are written to 92_VALIDATION/CONFLICT_STATUS.csv "
                    "regardless of status; a RESOLVED row still carries value_a and "
                    "value_b, so no discarded value is unrecoverable."])
add("CONFLICT_POLICY",
    ["rule_id", "conflict_pattern", "detection_basis", "resolution_status",
     "confidence", "resolution_reason", "preservation_guarantee"],
    cp_rows,
    ["Phase 2 measured %d conflicts across 63 file pairs. None is discarded." % len(CONF),
     "Permitted resolution_status values, and only these: " +
     ", ".join(M.CONFLICT_STATUSES) + ".",
     "CONFLICT_STATUS.csv columns: " + ", ".join(M.CONFLICT_COLS) + ".",
     "A canonical value is written ONLY when a rule above supports it on the evidence. "
     "Otherwise the status is UNRESOLVED_PRESERVE_BOTH and canonical_value stays empty - "
     "never fabricated.",
     "HOMONYM_NOT_A_CONFLICT exists because two same-named columns describing different "
     "facts are a mapping problem, not a data disagreement; treating them as a conflict "
     "would corrupt both."],
    [9, 34, 60, 30, 10, 66, 84])

# ---------------------------------------------------------------------------
# 8. NULL_SEMANTICS
# ---------------------------------------------------------------------------
ns_rows = []
for cls, meaning, stored, flags, rule in M.NULL_SEMANTICS:
    ns_rows.append([cls, meaning, stored, flags, ", ".join(M.NULL_FLAG_SUFFIX), rule])
add("NULL_SEMANTICS",
    ["null_class", "meaning", "stored_value", "detection_signal", "flag_columns",
     "rule"],
    ns_rows,
    ["Phase 1 measured %d placeholder-bearing columns; each is classified here rather "
     "than blanked." % len(NULLSEM),
     "The literal strings N/A, NA, Unknown, None, -, --, NIL, TBD are NEVER written to a "
     "canonical field. They become NULL plus a missing_reason.",
     "ASSERTED_ABSENCE is data: 'No exclusions' states that none exist. Converting it to "
     "NULL would destroy a regulatory fact, so it is stored as a positive assertion.",
     "For every value a transform changed, <field>_original_value retains the source text."],
    [30, 60, 30, 54, 44, 96])

# ---------------------------------------------------------------------------
# 9. SOURCE_TO_CANONICAL_MAPPING  - one row per source file (49)
# ---------------------------------------------------------------------------
sc_rows = []
for fid in sorted(M.ROUTE):
    entity, step, view, secondary = M.ROUTE[fid]
    inv = INV_BY.get(fid, {})
    cls = CLS_BY.get(fid, {})
    ncols = sum(1 for p in PROF if p["file_id"] == fid)
    if entity in M.MASTER:
        target = "00_MASTER/" + M.MASTER[entity]
    elif entity in {a[0] for a in M.AUX_DATASETS}:
        target = [a[1] for a in M.AUX_DATASETS if a[0] == entity][0]
    elif entity in M.REL_BY_NAME:
        target = "90_RELATIONSHIPS/" + M.REL_BY_NAME[entity][1]
    else:
        target = "(see COLUMN_MAPPING)"
    if fid in M.ARCHIVE_AFTER_VALIDATION:
        disp, arch = "DUPLICATE_ARCHIVED", ("COPY to 99_RAW/ARCHIVE_DUPLICATES/ ONLY "
                                           "after records incorporated, unique columns "
                                           "evaluated and 92_VALIDATION passes. Original "
                                           "never deleted.")
    elif fid in M.PENDING_REVIEW:
        disp, arch = "REQUIRES_REVIEW", "RETAIN - unresolved in Phase 2; rows flagged in 92_VALIDATION/REQUIRES_REVIEW.csv"
    else:
        disp, arch = "CANONICAL_OR_MERGED", "RETAIN"
    sc_rows.append([
        fid, inv.get("original_filename", ""), inv.get("extension", ""),
        inv.get("sheet_count", ""), inv.get("total_data_rows", ""), ncols,
        cls.get("primary_domain", ""), FOLDER_OF.get(fid, "OTHER_RELEVANT"),
        entity, target, view, secondary, STEP_OF.get(fid, "(no merge step - single source)"),
        disp, arch, "YES" if fid in CONF_FILES else "NO",
        inv.get("sha256", "")[:16],
        "Phase 1 classification confidence %s; %s" % (
            cls.get("confidence_score", ""),
            (cls.get("classification_evidence", "") or "")[:150]),
    ])
add("SOURCE_TO_CANONICAL_MAPPING",
    ["file_id", "original_filename", "extension", "sheets", "data_rows", "columns",
     "primary_domain", "domain_folder_01_SOURCE_DATA", "primary_canonical_entity",
     "primary_canonical_target", "canonical_source_view", "secondary_entities",
     "merge_step", "record_disposition_class", "archive_decision",
     "participates_in_conflicts", "sha256_prefix", "basis_evidence"],
    sc_rows,
    ["All 49 sources are listed - the 48 workspace files plus the 1 attached PDF. 45 are "
     "retained for merge; 4 are archivable only after validation.",
     "canonical_source_view is the filename this file's canonicalised view takes inside "
     "its 01_SOURCE_DATA domain folder, so the per-domain layout is reproducible.",
     "secondary_entities lists the other entities this file also feeds; a file is not "
     "restricted to one target just because it has one primary domain.",
     "No file is excluded because its filename looks duplicated, and no version is "
     "preferred on the basis of v2/v3/(1) in its name."],
    [8, 42, 10, 8, 10, 9, 24, 26, 20, 34, 40, 30, 24, 22, 60, 12, 18, 90])

# ---------------------------------------------------------------------------
# 10. FINAL_FOLDER_PLAN
# ---------------------------------------------------------------------------
fp_rows = []
order = 0
for path, ftype, cond, purpose in M.OUTPUT_TREE:
    order += 1
    fp_rows.append([order, path, ftype, cond, "", 0, purpose])
for folder, ids in M.FOLDER_PLAN:
    order += 1
    lst = [x for x in ids.split(",") if x]
    cond = "EMPTY_BY_MEASUREMENT" if folder in M.EMPTY_DOMAINS else "IF_NONEMPTY"
    if folder in M.EMPTY_DOMAINS:
        purpose = ("Phase 1 measured ZERO source files for this BIS domain. The folder is "
                   "created empty so the gap is visible and auditable; inventing a dataset "
                   "to fill it would fabricate data.")
    else:
        purpose = ("Canonicalised source-domain datasets for %s. Contains only the "
                   "canonical view of the %d file(s) Phase 1 measured into this domain; "
                   "00_MASTER and 90_RELATIONSHIPS remain the single authority."
                   % (folder.split("_", 1)[1].replace("_", " ").title(), len(lst)))
    fp_rows.append([order, "01_SOURCE_DATA/" + folder, "SOURCE_DOMAIN", cond,
                    ",".join(lst), len(lst), purpose])
add("FINAL_FOLDER_PLAN",
    ["sort_order", "folder_path", "folder_type", "creation_condition",
     "source_file_ids", "source_file_count", "purpose_and_contents"],
    fp_rows,
    ["Root: BIS_SIH26107_DATA/. %d structural folders + %d BIS source domains "
     "(22 numbered + OTHER_RELEVANT + UNKNOWN)." % (len(M.OUTPUT_TREE),
                                                    len(M.FOLDER_PLAN)),
     "Folders are created in Phase 5 only AFTER the canonicalisation rules in this "
     "workbook have been applied - never as an early file move.",
     "99_RAW/ARCHIVE_DUPLICATES receives COPIES. The original uploaded files stay exactly "
     "where they are, unmodified and unrenamed."],
    [9, 42, 20, 22, 30, 11, 108])

# ---------------------------------------------------------------------------
# assertions - fail loudly rather than ship a wrong contract
# ---------------------------------------------------------------------------
problems = list(M.self_check())
by = dict((n, r) for n, r, _c in COUNTS)
order_ok = [n for n, _r, _c in COUNTS]
EXPECT = ["ENTITY_MODEL", "DATASET_MODEL", "COLUMN_MAPPING", "MERGE_RULES", "ID_RULES",
          "RELATIONSHIP_MODEL", "CONFLICT_POLICY", "NULL_SEMANTICS",
          "SOURCE_TO_CANONICAL_MAPPING", "FINAL_FOLDER_PLAN"]
if order_ok != EXPECT:
    problems.append("sheet names/order wrong: %s" % order_ok)
if by["COLUMN_MAPPING"] != len(PROF) or len(PROF) != 685:
    problems.append("COLUMN_MAPPING must carry all 685 profiled columns, got %d of %d"
                    % (by["COLUMN_MAPPING"], len(PROF)))
if by["ENTITY_MODEL"] != 13:
    problems.append("ENTITY_MODEL must have 13 entities")
if by["SOURCE_TO_CANONICAL_MAPPING"] != 49:
    problems.append("SOURCE_TO_CANONICAL_MAPPING must cover 49 sources")
if by["MERGE_RULES"] != 14:
    problems.append("MERGE_RULES must reproduce the 14 Phase 2 steps")
if by["RELATIONSHIP_MODEL"] != 19:
    problems.append("RELATIONSHIP_MODEL must have 19 tables")
if by["NULL_SEMANTICS"] != 4:
    problems.append("NULL_SEMANTICS must have 4 classes")
if unresolved:
    problems.append("transform names not in p3_lib.TRANSFORMS: %s" % unresolved[:5])
missing_cols = [f for f in M.ROUTE if not any(p["file_id"] == f for p in PROF)]
if len(missing_cols) > 1:
    problems.append("files with no profiled columns: %s" % missing_cols)

# Every column the design marks EXPLODE_TO_RELATIONSHIP must have an EXPLODE_ROUTE
# entry, or its fragments would have nowhere to go at build time - a silent loss of
# exactly the relational information the spec forbids flattening.
explode_pairs = set()
for p in PROF:
    fid = p["file_id"]
    rt = M.ROUTE.get(fid)
    ent = rt[0] if rt else ""
    cc, _s, ma, _t, _tg, _rs = M.resolve(fid, p["exact_column_name"], ent)
    if ma == "EXPLODE_TO_RELATIONSHIP":
        explode_pairs.add((ent, cc))
unrouted_explodes = sorted(x for x in explode_pairs if x not in M.EXPLODE_ROUTE)
if unrouted_explodes:
    problems.append("EXPLODE columns with no EXPLODE_ROUTE: %s" % unrouted_explodes)

if problems:
    print("DESIGN BUILD FAILED")
    for p in problems:
        print("  -", p)
    sys.exit(1)

os.makedirs(DESIGN_DIR, exist_ok=True)
wb.save(OUT)
print("WROTE", OUT)
print("%-32s %8s %8s" % ("SHEET", "ROWS", "COLS"))
for n, r, c in COUNTS:
    print("%-32s %8d %8d" % (n, r, c))
print("files with no profiled columns (expected: the 1 attached PDF): %s" % missing_cols)
print("EXPLODE pairs measured %d, all routed" % len(explode_pairs))
print("PHASE 3A DESIGN WORKBOOK OK")
