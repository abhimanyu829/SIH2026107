"""PHASE 2 DECISION LAYER - duplicate groups, version analysis, canonical decisions,
merge plan.

Consumes only the evidence produced by p2_run.py. Every verdict is derived from measured
content: bytes, row multisets, record-key overlap, entity overlap, conflict shape.
A filename NEVER contributes to a decision - `v2`, `v3`, `(1)`, `final` are treated as
opaque labels. Where the evidence does not settle a case the verdict is REQUIRES_REVIEW
rather than a guess.

Writes DUPLICATE_GROUPS.csv, VERSION_ANALYSIS.csv, CANONICAL_DECISIONS.csv,
PHASE2_MERGE_PLAN.csv. Archives nothing, restructures nothing, merges no data.
"""
import collections
import csv
import os
import pickle
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p1_lib import is_placeholder  # noqa: E402
from p2_lib import cap, entity_kind, jaccard, toks  # noqa: E402

SRC = "/sessions/optimistic-gallant-gauss/mnt/SIH-DATASETS-EXCEL-SHEET"
OUT = os.path.join(SRC, "BIS_SIH26107_DATA", "01_ANALYSIS")
csv.field_size_limit(50_000_000)

# Narrative non-answers seen in this corpus. They occupy a cell without asserting a
# value, so a side that carries one is NOT evidence of information.
NARRATIVE_NULL = (
    "not separately stated", "not stated", "not specified", "not applicable",
    "not available", "none", "none (new standard)", "nil", "no data", "tbd",
    "to be notified", "as applicable", "periodically updated", "multiple",
    "refer to standard", "see standard", "various", "not mentioned", "unknown",
)
# Markers of a raw-scrape artefact: a value that leaked plumbing into the data.
ARTEFACT = ("from standard record endpoint", "endpoint", "search_is_n", "javascript",
            "undefined", "nan", "#ref", "#value", "lorem")

ALLOWED = {"EXACT_DUPLICATE", "IDENTICAL_CONTENT", "DUPLICATE_WITH_UNIQUE_DATA",
           "COMPLEMENTARY", "VERSION_NEWER", "VERSION_OLDER", "DIFFERENT_ENTITY",
           "CONFLICTING", "LIKELY_DUPLICATE", "REQUIRES_REVIEW"}

GROUP_H = ["group_id", "file_a", "file_b", "duplicate_type", "similarity_score",
           "common_rows", "unique_rows_a", "unique_rows_b", "common_IS_numbers",
           "unique_IS_numbers_a", "unique_IS_numbers_b", "common_columns",
           "unique_columns_a", "unique_columns_b", "conflicts", "decision",
           "decision_reason", "recommended_canonical_file", "records_to_merge",
           "records_to_archive", "requires_review",
           # evidence columns retained so every verdict above is auditable
           "detection_level", "record_key_column", "common_records_by_key",
           "unique_records_a_by_key", "unique_records_b_by_key", "record_key_jaccard",
           "entity_identity_verdict", "entity_discriminator_columns",
           "homonym_columns_do_not_union", "attribute_sets_comparable",
           "row_metric_reliability", "schema_verdict", "identical_bytes",
           "identical_row_multiset", "version_direction_evidence", "pair_id"]


def rd(name):
    with open(os.path.join(OUT, name), encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def w(name, header, rows):
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8-sig") as f:
        wr = csv.DictWriter(f, header, extrasaction="ignore")
        wr.writeheader()
        wr.writerows(rows)
    return "%-30s %6d rows" % (name, len(rows))


def blank(v):
    """A cell that occupies space without asserting a value."""
    s = (v or "").strip().lower()
    return (not s) or is_placeholder(s) or s in NARRATIVE_NULL or s in ("—", "–", "-")


def artefact(v):
    s = (v or "").strip().lower()
    return any(a in s for a in ARTEFACT)


# ------------------------------------------------------------- conflict shape per pair
def shape(conflicts):
    """Per pair: which columns disagree, on how many distinct record keys, and how the
    two sides differ (one side blank / one side an artefact / both real). `by` repeats the
    same breakdown per column, which is what distinguishes a genuine disagreement from one
    column name carrying two different meanings."""
    def col():
        return dict(n=0, a_blank=0, b_blank=0, both_real=0, fmt=0, jsum=0.0, lensum=0)
    S = collections.defaultdict(lambda: dict(
        cols=collections.defaultdict(set), by=collections.defaultdict(col),
        a_blank=0, b_blank=0, a_artefact=0, b_artefact=0, both_real=0, fmt=0, n=0))
    for c in conflicts:
        d = S[c["pair_id"]]
        k = d["by"][c["conflicting_column"]]
        d["n"] += 1
        k["n"] += 1
        d["cols"][c["conflicting_column"]].add(c["record_key_value"])
        av, bv = c["value_a"], c["value_b"]
        k["jsum"] += jaccard(toks(av), toks(bv))
        k["lensum"] += (len(av) + len(bv)) // 2
        ab, bb = blank(av), blank(bv)
        if ab and not bb:
            d["a_blank"] += 1
            k["a_blank"] += 1
        elif bb and not ab:
            d["b_blank"] += 1
            k["b_blank"] += 1
        else:
            if artefact(av) and not artefact(bv):
                d["a_artefact"] += 1
            elif artefact(bv) and not artefact(av):
                d["b_artefact"] += 1
            d["both_real"] += 1
            k["both_real"] += 1
        if c["conflict_type"] == "VALUE_FORMAT_VARIANT":
            d["fmt"] += 1
            k["fmt"] += 1
    return S


def discriminators(p, sh):
    """Columns that identify an ENTITY and disagree on essentially every matched record.

    This is the test that clears the `BIS_Schemes_Master` vs `_Scheme_2` case by content.
    When two files hold the same key set but every record carries a different scheme_id /
    scheme_code / scheme_name, they are not two copies of one table - they are two
    different entities described over the same key. The key is therefore incomplete
    (here the true key is product + scheme), and neither file may be archived.
    """
    kcom = int(p["common_records_by_key"])
    if kcom <= 0:
        return []
    out = []
    for col, keys in sh["cols"].items():
        if entity_kind(col) and len(keys) >= 0.99 * kcom:
            out.append(col)
    return sorted(out)


def same_attributes(p):
    """Do the two sheets describe their subjects with the SAME attribute set?

    Sharing subjects is not the same as being a duplicate. `BIS_Combined_Testing_Master`
    and `BIS_QCO_Summary` both cover the same 40 IS numbers, yet share ZERO columns: one
    holds test parameters, the other QCO notification facts. Calling that a duplicate
    because the subjects coincide would invite Phase 4 to collapse two disjoint attribute
    sets into one table and lose half the columns. A duplicate claim therefore requires
    attribute agreement as well as subject agreement.
    """
    ca, cb = int(p["columns_a"]), int(p["columns_b"])
    com = int(p["common_columns"])
    if not ca or not cb:
        return False
    if p["schema_verdict"] in ("SCHEMA_IDENTICAL", "SCHEMA_SUBSTANTIALLY_IDENTICAL",
                               "SCHEMA_SUBSET"):
        return True
    return float(p["column_jaccard"]) >= 0.60 or com >= 0.60 * min(ca, cb)


def homonyms(p, sh, kcom):
    """Shared column NAMES that carry different MEANINGS in the two files.

    `BIS_QCO_Master_Scheme_1` and `BIS_Scheme_IV_FMCS` share a column called `scope` and
    disagree on it for all 40 matched standards - but A's scope describes the product
    ("covers indoor and outdoor furniture categories...") while B's describes the
    assessment ("compliance evaluation, factory audits..."). That is not a data conflict
    to resolve; it is one name for two fields. Phase 3 must split such a column instead of
    unioning it, so the finding is recorded rather than filed as a disagreement.

    Three conditions must hold together, or ordinary disagreements would be mislabelled:
    the column disagrees on essentially every matched record, the values are long enough
    for a name to hide two meanings (a differing date or code is a conflict, not a
    homonym), and the two sides share almost no vocabulary - two paraphrases of the same
    guidance overlap heavily in tokens and are therefore NOT reported here.
    """
    if kcom <= 0:
        return []
    out = []
    for col, keys in sh["cols"].items():
        d = sh["by"][col]
        n = d["n"] or 1
        if (len(keys) >= 0.95 * kcom and d["both_real"] >= 0.95 * d["n"]
                and d["fmt"] == 0 and d["lensum"] / n >= 40
                and d["jsum"] / n < 0.20):
            out.append(col)
    return sorted(out)


def version_direction(p, sh):
    """Which side is the later revision, decided ONLY from cell content.

    Three admissible kinds of evidence, in order:
      1 enrichment - one side leaves the field blank / narrative-null where the other
        carries a real value, consistently across the conflicts;
      2 repair - one side carries a scrape artefact where the other carries a clean
        value (`27280 (from standard record endpoint)` vs `IS 17631:2022`);
      3 nothing conclusive - the pair is NOT called a version pair.
    Filenames, `v2`/`v3` labels and file mtimes are never consulted: an mtime records
    when a file was downloaded, not which revision it holds.
    """
    n = sh["n"] or 1
    ab, bb = sh["a_blank"], sh["b_blank"]
    aa, ba = sh["a_artefact"], sh["b_artefact"]
    if bb == 0 and ab >= 0.70 * n:
        return "B", ("ENRICHMENT: B supplies a real value in %d/%d conflicting cells "
                     "where A is blank or a narrative non-answer; A supplies none in "
                     "the other direction" % (ab, n))
    if ab == 0 and bb >= 0.70 * n:
        return "A", ("ENRICHMENT: A supplies a real value in %d/%d conflicting cells "
                     "where B is blank or a narrative non-answer; B supplies none in "
                     "the other direction" % (bb, n))
    if ba == 0 and aa > 0:
        return "B", ("REPAIR: A carries a raw-scrape artefact in %d conflicting cells "
                     "that B has replaced with a clean value" % aa)
    if aa == 0 and ba > 0:
        return "A", ("REPAIR: B carries a raw-scrape artefact in %d conflicting cells "
                     "that A has replaced with a clean value" % ba)
    return "", ("INCONCLUSIVE: %d conflicts, both sides carry real values (a_blank=%d "
                "b_blank=%d a_artefact=%d b_artefact=%d) - no side is demonstrably the "
                "later revision" % (n, ab, bb, aa, ba))


# ----------------------------------------------------------------------- classifier
def classify(p, sh):
    """One pair -> one of the ten allowed decisions, plus reason, canonical file,
    merge/archive counts and a review flag. Precedence is strictest-evidence-first."""
    kcom = int(p["common_records_by_key"])
    kua, kub = int(p["unique_records_a_by_key"]), int(p["unique_records_b_by_key"])
    kj = float(p["record_key_jaccard"])
    cf = int(p["conflicts"])
    ej = float(p["entity_jaccard_max"])
    a, b = p["file_a"], p["file_b"]
    disc = discriminators(p, sh)
    hom = homonyms(p, sh, kcom)
    attrs = same_attributes(p)
    dirn, dev = ("", "NO_CONFLICTS_TO_JUDGE_DIRECTION_FROM") if not cf else \
        version_direction(p, sh)
    full = kj >= 0.95 and kua == 0 and kub == 0
    # Subject agreement without attribute agreement is complementarity, never duplication.
    # Every duplicate-flavoured verdict below is therefore gated on `attrs`; a pair that
    # covers the same subjects through a different attribute set falls through to the
    # COMPLEMENTARY branch, which unions rather than collapses them.
    aspect = ("The two files share their subjects but not their attributes (%s, column "
              "Jaccard %s, %d shared of %s/%s columns), so they describe different "
              "attributes of the same subjects. Union them side by side on the subject "
              "key; neither attribute set may be dropped."
              % (p["schema_verdict"], p["column_jaccard"], int(p["common_columns"]),
                 p["columns_a"], p["columns_b"]))
    if hom:
        aspect += (" Column name(s) %s disagree on essentially every matched record while "
                   "both sides hold real values - one name carrying two different "
                   "meanings. Phase 3 must SPLIT these into per-source fields, not union "
                   "them." % "; ".join(hom))

    if p["identical_bytes"] == "YES":
        return ("EXACT_DUPLICATE", 1,
                "Byte-for-byte identical files (same SHA-256). No content differs, so "
                "one copy carries the whole of both.", a, 0, int(p["rows_b"]), "NO",
                disc, dev)
    if p["identical_row_multiset"] == "YES":
        return ("IDENTICAL_CONTENT", 2,
                "Different bytes but an identical normalised row multiset (%s rows, "
                "row order %s): every record in one file is present in the other."
                % (p["rows_a"], "same" if p["identical_row_order"] == "YES" else
                   "different"), a, 0, int(p["rows_b"]), "NO", disc, dev)
    if full and disc:
        return ("DIFFERENT_ENTITY", 3,
                "Same %d record keys on `%s` in both files, but the entity-identifying "
                "column(s) %s disagree on every matched record. These are two different "
                "entities described over one key, not two copies of one table - the real "
                "key needs the entity dimension added. BOTH files must be kept in full."
                % (kcom, p["record_key_column"], "; ".join(disc)),
                "BOTH_KEEP_SEPARATE", kcom * 2, 0, "YES", disc, dev)
    if full and attrs and cf and dirn:
        newer, older = (b, a) if dirn == "B" else (a, b)
        return ("VERSION_NEWER" if dirn == "B" else "VERSION_OLDER", 4,
                "Identical record set (%d keys on `%s`, none unique to either side) with "
                "%d differing cells whose direction is settled by content: %s. Later "
                "revision = %s. No record is lost by treating %s as superseded, but its "
                "differing cells are preserved in CONFLICTS.csv."
                % (kcom, p["record_key_column"], cf, dev, newer, older),
                newer, 0, 0, "NO", disc, dev)
    if full and attrs and cf and not dirn:
        return ("CONFLICTING", 4,
                "Identical record set (%d keys on `%s`) and the same attribute set, but %d "
                "cells disagree with no content evidence of which side is later: %s. "
                "Preserve both; do not overwrite either."
                % (kcom, p["record_key_column"], cf, dev),
                "BOTH_PRESERVE_CONFLICTS", 0, 0, "YES", disc, dev)
    if full and attrs and not cf:
        return ("LIKELY_DUPLICATE", 4,
                "Identical record set (%d keys on `%s`, none unique to either side) and "
                "no disagreement in any shared column, yet the row multisets are not "
                "identical - the difference lies in columns absent from one side (%d in "
                "A, %d in B). Merge on the key; nothing is dropped."
                % (kcom, p["record_key_column"], int(p["unique_columns_a"]),
                   int(p["unique_columns_b"])), a, kcom, 0, "YES", disc, dev)
    if full and not attrs:
        return ("COMPLEMENTARY", 4,
                "All %d records match on `%s` with none unique to either side. %s"
                % (kcom, p["record_key_column"], aspect),
                "MERGE_UNION", kcom, 0, "YES", disc, dev)
    if kcom > 0 and attrs and kj >= 0.30:
        return ("DUPLICATE_WITH_UNIQUE_DATA", 4,
                "%d records shared on `%s` (key Jaccard %.2f) but %d are unique to A and "
                "%d unique to B, over the same attribute set. Overlapping records are the "
                "same entities; the unique ones are additional valid records. Union both - "
                "archiving either side would destroy records."
                % (kcom, p["record_key_column"], kj, kua, kub),
                "MERGE_UNION", kua + kub + kcom, 0, "YES" if cf else "NO", disc, dev)
    if kcom > 0 and not attrs:
        return ("COMPLEMENTARY", 4,
                "%d of %d records are shared on `%s` (key Jaccard %.2f; %d unique to A, %d "
                "to B). %s" % (kcom, kcom + kua + kub, p["record_key_column"], kj, kua,
                               kub, aspect),
                "MERGE_UNION", kcom + kua + kub, 0, "YES", disc, dev)
    if kcom > 0:
        return ("COMPLEMENTARY", 4,
                "Only %d of %d records are shared on `%s` (key Jaccard %.2f); A holds %d "
                "records B does not and B holds %d A does not. The files describe mostly "
                "different records in a related area, so both are required. Merge as a "
                "union, keyed on `%s`." % (kcom, kcom + kua + kub, p["record_key_column"],
                                           kj, kua, kub, p["record_key_column"]),
                "MERGE_UNION", kcom + kua + kub, 0, "YES" if cf else "NO", disc, dev)
    if p["entity_identity_verdict"] == "SAME_ENTITIES_DIFFERENT_KEY_NAMESPACE":
        lvl = "LIKELY_DUPLICATE" if (ej >= 0.60 and attrs) else "COMPLEMENTARY"
        return (lvl, 4,
                "No shared value in any candidate key column (%s), yet entity overlap "
                "reaches %.2f - the files describe overlapping entities under different "
                "identifier namespaces. Identity must be re-derived in Phase 3 from the "
                "entity columns before any merge; keying on the existing surrogate would "
                "duplicate every shared entity.%s"
                % (p["key_selection_note"][:150] or "none qualified", ej,
                   "" if attrs else " " + aspect),
                "MERGE_AFTER_REKEY", int(p["rows_a"]) + int(p["rows_b"]), 0, "YES",
                disc, dev)
    if ej < 0.05 and kcom <= 0:
        return ("DIFFERENT_ENTITY", 3,
                "Checked and cleared as a false duplicate candidate: no shared record "
                "key values and entity overlap only %.2f. Schema resemblance (%s, column "
                "Jaccard %s) is structural, not evidence of shared records."
                % (ej, p["schema_verdict"], p["column_jaccard"]),
                "BOTH_KEEP_SEPARATE", 0, 0, "NO", disc, dev)
    return ("REQUIRES_REVIEW", 4,
            "Evidence does not settle this pair: key overlap %d, entity overlap %.2f, "
            "schema %s, conflicts %d, row metric %s. Deliberately left unresolved rather "
            "than guessed." % (kcom, ej, p["schema_verdict"], cf,
                               p["row_metric_reliability"]),
            "UNDECIDED_REVIEW_REQUIRED", 0, 0, "YES", disc, dev)


# --------------------------------------------------------------- DUPLICATE_GROUPS.csv
def build_groups(deep, sh):
    rows = []
    for p in deep:
        s = sh[p["pair_id"]]
        dec, lvl, why, canon, mrg, arc, rev, disc, dev = classify(p, s)
        assert dec in ALLOWED, dec
        hom = homonyms(p, s, int(p["common_records_by_key"]))
        rows.append(dict(
            group_id="DG-%04d" % len(rows), file_a=p["file_a"], file_b=p["file_b"],
            duplicate_type=dec, similarity_score=p["similarity_score"],
            common_rows=p["common_rows"], unique_rows_a=p["unique_rows_a"],
            unique_rows_b=p["unique_rows_b"], common_IS_numbers=p["common_IS_numbers"],
            unique_IS_numbers_a=p["unique_IS_numbers_a"],
            unique_IS_numbers_b=p["unique_IS_numbers_b"],
            common_columns=p["common_columns"], unique_columns_a=p["unique_columns_a"],
            unique_columns_b=p["unique_columns_b"], conflicts=p["conflicts"],
            decision=dec, decision_reason=why, recommended_canonical_file=canon,
            records_to_merge=mrg, records_to_archive=arc, requires_review=rev,
            detection_level="L%d" % lvl, record_key_column=p["record_key_column"],
            common_records_by_key=p["common_records_by_key"],
            unique_records_a_by_key=p["unique_records_a_by_key"],
            unique_records_b_by_key=p["unique_records_b_by_key"],
            record_key_jaccard=p["record_key_jaccard"],
            entity_identity_verdict=p["entity_identity_verdict"],
            entity_discriminator_columns="; ".join(disc),
            homonym_columns_do_not_union="; ".join(hom),
            attribute_sets_comparable="YES" if same_attributes(p) else "NO",
            row_metric_reliability=p["row_metric_reliability"],
            schema_verdict=p["schema_verdict"], identical_bytes=p["identical_bytes"],
            identical_row_multiset=p["identical_row_multiset"],
            version_direction_evidence=dev, pair_id=p["pair_id"]))
    return rows


# ---------------------------------------------------------------- VERSION_ANALYSIS.csv
VER_H = ["version_group_id", "file_a", "file_b", "same_record_set", "record_key_column",
         "records_a", "records_b", "common_records", "unique_records_a",
         "unique_records_b", "columns_a", "columns_b", "populated_cells_a",
         "populated_cells_b", "differing_cells", "differing_columns",
         "filename_suggests", "content_verdict", "filename_agrees_with_content",
         "newer_by_content", "older_by_content", "direction_evidence",
         "records_lost_if_older_archived", "recommended_canonical_file",
         "requires_review", "phase4_action", "pair_id"]

VLABEL = ("_v2", "_v3", "_v4", " (1)", " (2)", "_final", "_latest", "_new", "_old",
          "_copy", "_updated", "_rev")


def fn_hint(a, b):
    """What the FILENAMES would suggest - recorded only so the report can state whether
    content agreed with the label. It never feeds a decision."""
    la = [t for t in VLABEL if t in a.lower()]
    lb = [t for t in VLABEL if t in b.lower()]
    if la and not lb:
        return "A labelled %s, B unlabelled" % "/".join(la)
    if lb and not la:
        return "B labelled %s, A unlabelled" % "/".join(lb)
    if la and lb:
        return "A labelled %s, B labelled %s" % ("/".join(la), "/".join(lb))
    return "neither filename carries a version label"


def build_versions(deep, sh, G):
    """Every pair that could be a version pair: same record set, or identical content,
    or a version-looking filename on either side. The last condition exists so the
    report can state, for each labelled pair, whether the label matched the content."""
    dg = {g["pair_id"]: g for g in G}
    rows = []
    for p in deep:
        s = sh[p["pair_id"]]
        kj = float(p["record_key_jaccard"])
        kua, kub = int(p["unique_records_a_by_key"]), int(p["unique_records_b_by_key"])
        labelled = fn_hint(p["file_a"], p["file_b"])
        same_set = kj >= 0.95 and kua == 0 and kub == 0
        if not (same_set or p["identical_row_multiset"] == "YES"
                or (labelled != "neither filename carries a version label"
                    and float(p["similarity_score"]) >= 0.30)):
            continue
        g = dg[p["pair_id"]]
        dec = g["decision"]
        dirn, dev = ("", "NO_CONFLICTS_TO_JUDGE_DIRECTION_FROM") if not int(p["conflicts"]) \
            else version_direction(p, s)
        if dec in ("EXACT_DUPLICATE", "IDENTICAL_CONTENT"):
            newer = older = "NEITHER_CONTENT_IS_EQUAL"
            agrees = ("filename implies a version difference that the content "
                      "contradicts - the files are content-equal"
                      if labelled != "neither filename carries a version label"
                      else "no label, no content difference")
            lost = 0
        elif dec in ("VERSION_NEWER", "VERSION_OLDER"):
            newer = p["file_b"] if dirn == "B" else p["file_a"]
            older = p["file_a"] if dirn == "B" else p["file_b"]
            lab_newer = ("_v3" in newer.lower() or "_v2" in newer.lower()
                         or "_v4" in newer.lower())
            lab_older = ("_v3" in older.lower() or "_v2" in older.lower()
                         or "_v4" in older.lower())
            agrees = ("YES - the higher label is also the later revision by content"
                      if lab_newer and not lab_older else
                      "NO - the higher label is the EARLIER revision by content"
                      if lab_older and not lab_newer else
                      "N/A - labels do not order these two files")
            lost = 0
        else:
            newer = older = "UNDETERMINED"
            agrees = "content does not establish a version order"
            lost = kua + kub
        rows.append(dict(
            version_group_id="VG-%03d" % len(rows), file_a=p["file_a"],
            file_b=p["file_b"], same_record_set="YES" if same_set else "NO",
            record_key_column=p["record_key_column"] or "NONE_QUALIFIED",
            records_a=p["rows_a"], records_b=p["rows_b"],
            common_records=p["common_records_by_key"], unique_records_a=kua,
            unique_records_b=kub, columns_a=p["columns_a"], columns_b=p["columns_b"],
            populated_cells_a=p["populated_cells_a"],
            populated_cells_b=p["populated_cells_b"], differing_cells=p["conflicts"],
            differing_columns=cap(sorted(s["cols"]), 12) or "NONE",
            filename_suggests=labelled, content_verdict=dec,
            filename_agrees_with_content=agrees, newer_by_content=newer,
            older_by_content=older, direction_evidence=dev,
            records_lost_if_older_archived=lost,
            recommended_canonical_file=g["recommended_canonical_file"],
            requires_review=g["requires_review"], pair_id=p["pair_id"],
            phase4_action=(
                "Archive the redundant copy to 99_RAW_ORIGINALS/ARCHIVE_OR_DUPLICATES/ "
                "AFTER the canonical dataset is built and validated; keep it recoverable."
                if dec in ("EXACT_DUPLICATE", "IDENTICAL_CONTENT") else
                "Load the later revision as canonical; retain the earlier file as an "
                "archived original and keep its differing cells in CONFLICTS.csv."
                if dec in ("VERSION_NEWER", "VERSION_OLDER") else
                "Do NOT treat as a version pair. Merge on the record key and preserve "
                "every record from both files.")))
    return rows


# ------------------------------------------------------------- CANONICAL_DECISIONS.csv
CAN_H = ["file_id", "original_filename", "primary_domain", "rows", "columns",
         "populated_cells", "sha256_16", "groups_participating", "canonical_status",
         "fully_covered_by", "contributes_unique_records_to", "max_unique_records",
         "unique_records_not_covered_elsewhere",
         "conflicts_involving_file", "different_entity_partners", "decision_reason",
         "archive_eligible", "archive_precondition", "phase3_action", "phase4_action"]

COVER = {"EXACT_DUPLICATE", "IDENTICAL_CONTENT"}


def build_canonical(inv, facts, G):
    """One row per source file. A file is archive-eligible ONLY if some other file
    demonstrably contains all of its content AND it contributes no unique record to any
    other file. A file that is an exact duplicate of one file may still hold records a
    third file lacks, so coverage is never inferred from a single relationship."""
    by_name = {}
    for k, v in facts.items():
        by_name.setdefault(v["fname"], v)
    covered = collections.defaultdict(list)      # file -> files that fully contain it
    unique_to = collections.defaultdict(dict)    # file -> {partner: unique record count}
    diff_ent = collections.defaultdict(set)
    ncf, groups = collections.Counter(), collections.Counter()
    for g in G:
        a, b = g["file_a"], g["file_b"]
        groups[a] += 1
        groups[b] += 1
        ncf[a] += int(g["conflicts"])
        ncf[b] += int(g["conflicts"])
        if g["decision"] in COVER:
            covered[b].append(a)
        if g["decision"] in ("VERSION_NEWER", "VERSION_OLDER"):
            nf = g["recommended_canonical_file"]
            old = b if nf == a else a
            # The superseded side is only "contained" in the newer one if it also has no
            # column of its own. An older revision that carries a field the newer dropped
            # is not covered, however clear the version direction is.
            lost = int(g["unique_columns_a"] if old == a else g["unique_columns_b"])
            if not lost:
                covered[old].append(nf)
        if g["decision"] == "DIFFERENT_ENTITY":
            diff_ent[a].add(b)
            diff_ent[b].add(a)
        ua, ub = int(g["unique_records_a_by_key"]), int(g["unique_records_b_by_key"])
        if ua > 0:
            unique_to[a][b] = ua
        if ub > 0:
            unique_to[b][a] = ub
    rows = []
    for r in sorted(inv, key=lambda x: x["file_id"]):
        f = r["original_filename"]
        s = by_name.get(f)
        cov = sorted(set(covered[f]))
        uq = unique_to[f]
        mx = max(uq.values()) if uq else 0
        # "Contributes unique records to X" only blocks archiving if the file that COVERS
        # this one does not itself carry those same records. For a byte-identical twin it
        # always does - the two files stand in the same relation to every third file - so
        # counting such records as a reason to keep both copies would make redundancy
        # undetectable. Where the covering file has no measured relationship to X at all,
        # coverage of those records is unproven and the file is kept.
        resid = {}
        for x, n in sorted(uq.items()):
            if x in cov:
                resid[x] = n
                continue
            if not any(unique_to[q].get(x, -1) >= n for q in cov):
                resid[x] = n
        if s is None:
            st, why, elig = ("NOT_TABULAR_KEEP_AS_REFERENCE",
                             "Not a tabular dataset, so it takes no part in duplicate "
                             "analysis. Retained unchanged as a source document.", "NO")
        elif not groups[f]:
            st, why, elig = ("KEEP_AS_CANONICAL_UNIQUE",
                             "No content link to any other file passed the deep-compare "
                             "gate: this dataset is unique in the corpus.", "NO")
        elif cov and not resid:
            st = "REDUNDANT_ARCHIVE_AFTER_VALIDATION"
            why = ("Fully contained in %s by measured content. Every record it contributes "
                   "to another file (%d partner(s)) is contributed at least as fully by "
                   "that containing file, so archiving this copy removes no record from "
                   "the corpus." % ("; ".join(cov), len(uq)))
            elig = "YES"
        elif cov and resid:
            st = "KEEP_CONTAINS_UNIQUE_RECORDS_ELSEWHERE"
            why = ("Fully contained in %s, BUT it still holds up to %d records that %s "
                   "lacks and that the containing file does not demonstrably carry. "
                   "Archiving it on the strength of the first relationship alone would "
                   "lose those records."
                   % ("; ".join(cov), max(resid.values()), cap(sorted(resid), 4)))
            elig = "NO"
        elif diff_ent[f]:
            st = "KEEP_DISTINCT_ENTITY"
            why = ("Checked against %s and cleared as a false duplicate: same keys, "
                   "different entity identity. Both files are required."
                   % cap(sorted(diff_ent[f]), 4))
            elig = "NO"
        elif uq:
            st = "KEEP_AND_MERGE_CONTRIBUTES_UNIQUE_RECORDS"
            why = ("Overlaps other files but holds up to %d records they do not (%s). "
                   "Every one of those records must survive the merge."
                   % (mx, cap(sorted(uq), 4)))
            elig = "NO"
        else:
            st = "KEEP_PENDING_REVIEW"
            why = ("Participates in %d compared pairs with no relationship strong enough "
                   "to establish coverage. Kept until Phase 3 review." % groups[f])
            elig = "NO"
        rows.append(dict(
            file_id=r["file_id"], original_filename=f,
            primary_domain=r["candidate_topic"],
            rows=s["rows"] if s else 0, columns=s["ncols"] if s else 0,
            populated_cells=s["informative"] if s else 0, sha256_16=r["sha256"][:16],
            groups_participating=groups[f], canonical_status=st,
            fully_covered_by="; ".join(cov) or "NONE",
            contributes_unique_records_to=cap(sorted(uq), 6) or "NONE",
            max_unique_records=mx,
            unique_records_not_covered_elsewhere=cap(sorted(resid), 6) or "NONE",
            conflicts_involving_file=ncf[f],
            different_entity_partners=cap(sorted(diff_ent[f]), 4) or "NONE",
            decision_reason=why, archive_eligible=elig,
            archive_precondition=("Phase 6 export validated AND record counts reconciled "
                                  "AND file copied to 99_RAW_ORIGINALS/ARCHIVE_OR_"
                                  "DUPLICATES/ so it stays recoverable"
                                  if elig == "YES" else "NOT_ARCHIVABLE"),
            phase3_action=("Exclude from the canonical load; keep as an archived original"
                           if elig == "YES" else
                           "Include as a contributing source in the canonical schema"),
            phase4_action=("Do not load. Verify the covering file first, then archive."
                           if elig == "YES" else
                           "Load every record; write file_id + source row into "
                           "provenance for each output row.")))
    return rows


# --------------------------------------------------------------- PHASE2_MERGE_PLAN.csv
PLAN_H = ["step_id", "execution_order", "target_canonical_dataset", "target_domain",
          "source_files", "source_file_count", "join_key", "join_key_status",
          "input_records", "expected_output_records_min", "expected_output_records_max",
          "records_added_beyond_largest_source", "duplicate_records_collapsed",
          "conflicts_to_carry", "different_entity_splits", "required_provenance_columns",
          "merge_rule", "conflict_rule", "null_rule", "blocking_precondition",
          "requires_human_approval", "notes"]

DATASET = {
    "01_KNOW_YOUR_STANDARD": "standards", "02_PRODUCTS": "products", "03_QCO": "qco",
    "04_SCHEME_I": "schemes", "05_SCHEME_II_CRS": "schemes",
    "06_SCHEME_IV_COC": "schemes", "07_SCHEME_X": "schemes",
    "08_PRODUCT_SPECIFIC": "products", "09_PRODUCT_MANUALS": "documents",
    "10_TESTING": "tests", "11_CERTIFICATION_PROCESS": "certification",
    "12_CERTIFICATION_FAQ": "faq", "13_LAB_SERVICES": "labs", "14_LIMS_LABS": "labs",
    "15_LIMS_IS_TEST": "tests", "16_ACT_RULES_REGULATIONS": "legal",
    "17_HALLMARKING_OVERVIEW": "hallmarking", "18_HALLMARKING_FAQ": "faq",
    "19_HALLMARKING_ORDERS": "hallmarking", "20_HALLMARKING_CENTRES": "hallmark_centres",
    "21_JEWELLER_REGISTRATION": "jewellers", "22_FMCS": "fmcs",
    "OTHER_RELEVANT": "unclassified", "UNKNOWN": "unclassified",
}
PROV = ("source_file_id; source_filename; source_sheet; source_row_number; "
        "source_url; retrieved_at; merge_step_id; record_provenance_count")


def build_plan(inv, facts, G, C):
    """One step per canonical target dataset. The plan states what Phase 4 must do; it
    performs nothing. Record counts are bounds, not promises: the minimum assumes every
    measured duplicate collapses, the maximum assumes none does."""
    by_name = {}
    for v in facts.values():
        by_name.setdefault(v["fname"], v)
    keep = {c["original_filename"]: c for c in C if c["archive_eligible"] == "NO"}
    tgt = collections.defaultdict(list)
    for r in inv:
        f = r["original_filename"]
        if f not in keep or f not in by_name:
            continue
        tgt[DATASET.get(r["candidate_topic"], "unclassified")].append(f)
    gi = collections.defaultdict(list)
    for g in G:
        gi[g["file_a"]].append(g)
        gi[g["file_b"]].append(g)
    rows = []
    for ds in sorted(tgt):
        fs = sorted(tgt[ds])
        dom = sorted({r["candidate_topic"] for r in inv
                      if r["original_filename"] in fs})
        inrec = sum(by_name[f]["rows"] for f in fs)
        rel = [g for f in fs for g in gi[f]
               if g["file_a"] in fs and g["file_b"] in fs]
        seen, rel = set(), [g for g in rel if not (g["pair_id"] in seen
                                                  or seen.add(g["pair_id"]))]
        collapse = sum(int(g["records_to_archive"]) for g in rel)
        collapse += sum(int(g["common_records_by_key"]) for g in rel
                        if g["decision"] in ("DUPLICATE_WITH_UNIQUE_DATA",
                                             "COMPLEMENTARY", "LIKELY_DUPLICATE"))
        keys = collections.Counter(g["record_key_column"] for g in rel
                                   if g["record_key_column"])
        jk = keys.most_common(1)[0][0] if keys else "NO_SHARED_KEY_IN_CLUSTER"
        rekey = [g for g in rel if g["entity_identity_verdict"]
                 == "SAME_ENTITIES_DIFFERENT_KEY_NAMESPACE"]
        splits = sorted({g["file_a"] + " | " + g["file_b"] for g in rel
                         if g["decision"] == "DIFFERENT_ENTITY"})
        cfn = sum(int(g["conflicts"]) for g in rel)
        largest = max(by_name[f]["rows"] for f in fs)
        lo = max(largest, inrec - collapse)
        rows.append(dict(
            step_id="MS-%02d" % (len(rows) + 1), execution_order=len(rows) + 1,
            target_canonical_dataset="canonical_%s" % ds, target_domain="; ".join(dom),
            source_files="; ".join(fs), source_file_count=len(fs),
            join_key=jk, input_records=inrec,
            join_key_status=("MEASURED_SHARED_KEY" if keys and not rekey else
                             "REKEY_REQUIRED_SURROGATE_NAMESPACES_DIFFER" if rekey else
                             "NO_SHARED_KEY_DERIVE_IN_PHASE_3"),
            expected_output_records_min=lo, expected_output_records_max=inrec,
            records_added_beyond_largest_source=lo - largest,
            duplicate_records_collapsed=min(collapse, inrec - largest),
            conflicts_to_carry=cfn, different_entity_splits="; ".join(splits) or "NONE",
            required_provenance_columns=PROV,
            merge_rule=("Full outer union on `%s`. Every source record appears in the "
                        "output exactly once per distinct entity; a record present in "
                        "several files yields ONE output row whose provenance lists all "
                        "contributing files and row numbers. No source record may be "
                        "dropped for being 'already present' without that provenance "
                        "entry." % jk),
            conflict_rule=("Where sources disagree on a shared field, write the value "
                           "from the file marked canonical for that pair, keep the "
                           "rejected value in CONFLICTS.csv, and set "
                           "status=REQUIRES_REVIEW on the output row. Never overwrite "
                           "silently and never average or concatenate disagreeing "
                           "values. %d conflicts in this cluster." % cfn),
            null_rule=("Absent values are written as NULL with missing_reason set to "
                       "NULL_UNKNOWN / ASSERTED_ABSENCE / AMBIGUOUS_REQUIRES_REVIEW as "
                       "carried from Phase 1. Never write 'N/A', 'Unknown', 'None' or "
                       "'-' as data, and never invent a value."),
            blocking_precondition=("Phase 3 approval of the canonical schema for "
                                   "canonical_%s%s" % (ds, "; plus an agreed re-keying "
                                   "rule, since identifier namespaces differ across "
                                   "these files" if rekey else "")),
            requires_human_approval="YES" if (rekey or splits or cfn) else "NO",
            notes=("%d relationships inside this cluster: %s"
                   % (len(rel), "; ".join("%s=%d" % kv for kv in sorted(
                       collections.Counter(g["decision"] for g in rel).items()))
                      or "none"))))
    return rows


# ----------------------------------------------------------------------------- driver
def main():
    inv = rd("FILE_INVENTORY.csv")
    deep = rd("DATASET_COMPARISON.csv")
    conf = rd("CONFLICTS.csv")
    P = pickle.load(open(os.path.join(OUT, "_cache", "phase2_pairs.pkl"), "rb"))
    facts = P["facts"]
    sh = shape(conf)
    for p in deep:                                   # pairs without conflicts
        sh.setdefault(p["pair_id"], dict(cols={}, by=collections.defaultdict(
            lambda: dict(n=0, a_blank=0, b_blank=0, both_real=0, fmt=0, jsum=0.0,
                         lensum=0)),
            a_blank=0, b_blank=0, a_artefact=0, b_artefact=0, both_real=0, fmt=0, n=0))
    G = build_groups(deep, sh)
    V = build_versions(deep, sh, G)
    C = build_canonical(inv, facts, G)
    M = build_plan(inv, facts, G, C)
    print(w("DUPLICATE_GROUPS.csv", GROUP_H, G))
    print(w("VERSION_ANALYSIS.csv", VER_H, V))
    print(w("CANONICAL_DECISIONS.csv", CAN_H, C))
    print(w("PHASE2_MERGE_PLAN.csv", PLAN_H, M))
    with open(os.path.join(OUT, "_cache", "phase2_decisions.pkl"), "wb") as f:
        pickle.dump({"G": G, "V": V, "C": C, "M": M}, f)

    d = collections.Counter(g["decision"] for g in G)
    # Two different notions, previously conflated. `undec` is the set of pairs the evidence
    # genuinely failed to settle; `rev` is the much larger set of pairs whose merge needs a
    # human to sign off (a re-key rule, a conflict call). Reporting the second as
    # "unresolved" overstates how much is unknown.
    undec = [g for g in G if g["decision"] == "REQUIRES_REVIEW"]
    rev = [g for g in G if g["requires_review"] == "YES"]
    multi = [g for g in G if int(g["records_to_merge"]) > 0]
    arch = [c for c in C if c["archive_eligible"] == "YES"]
    keep = [c for c in C if c["archive_eligible"] == "NO"]
    pres = sum(int(c["max_unique_records"]) for c in C
               if c["canonical_status"] == "KEEP_AND_MERGE_CONTRIBUTES_UNIQUE_RECORDS")
    cst = collections.Counter(c["canonical_status"] for c in C)
    hom = sorted({h for g in G for h in g["homonym_columns_do_not_union"].split("; ") if h})
    print("\n" + "=" * 78)
    print("PHASE 2 COMPLETE — DUPLICATE/OVERLAP/VERSION ANALYSIS COMPLETE")
    print("=" * 78)
    print("Total duplicate/overlap groups analysed : %d" % len(G))
    for k in sorted(ALLOWED):
        print("   %-28s %4d" % (k, d.get(k, 0)))
    print("Exact duplicates (identical bytes)      : %d" % d.get("EXACT_DUPLICATE", 0))
    print("Identical-content duplicates            : %d" % d.get("IDENTICAL_CONTENT", 0))
    print("Complementary datasets                  : %d" % d.get("COMPLEMENTARY", 0))
    print("Version pairs (direction from content)  : %d"
          % (d.get("VERSION_NEWER", 0) + d.get("VERSION_OLDER", 0)))
    print("Different-entity false candidates       : %d" % d.get("DIFFERENT_ENTITY", 0))
    print("Conflicts recorded (unresolved)         : %d across %d pairs"
          % (len(conf), sum(1 for g in G if int(g["conflicts"]) > 0)))
    print("Homonym columns (split, do not union)   : %d  %s"
          % (len(hom), cap(hom, 6) or "none"))
    print("Groups needing multi-file record merge  : %d" % len(multi))
    print("Records that must be preserved from     : %d (upper bound on records held by"
          % pres)
    print("  more than one file                      only one file in an overlapping pair)")
    print("Canonical-file decisions                : %d files" % len(C))
    for k, n in sorted(cst.items()):
        print("   %-38s %4d" % (k, n))
    print("Files redundant (archive AFTER Phase 6) : %d  %s"
          % (len(arch), cap(sorted(c["original_filename"] for c in arch), 4) or ""))
    print("Files that must be kept and merged      : %d of %d" % (len(keep), len(C)))
    print("Unresolved - evidence did not settle    : %d groups" % len(undec))
    print("Flagged for human approval at merge     : %d groups (resolved, but the merge "
          "rule needs sign-off)" % len(rev))
    print("Merge steps planned                     : %d" % len(M))
    print("\nSource files modified: 0    Files archived: 0    Folders restructured: 0")
    print("Canonical datasets created: 0  (Phase 2 produces evidence and a plan only)")


if __name__ == "__main__":
    main()

