#!/usr/bin/env python3
"""PHASE 3 BUILD (3B-3S) - canonical BIS data layer.

Reads the 49 immutable sources, projects every cell through the Phase 3A design
contract (p3_model.resolve + p3_lib.TRANSFORMS + SUBFIELD), resolves entities,
merges only semantically compatible fields, explodes multi-value cells into
relationship tables, preserves every conflict and every null class, and writes
the canonical layer plus POSTGRES_READY and QDRANT_READY.

Two projection passes over the sources (projection is pure, so both agree):
  pass A collects natural keys + field contributions  -> mints are sealed
  pass B streams attributes, relationships, provenance, PM sections, aux
Nothing in the source tree is modified. Archive copies are made by p3_verify.py,
after validation, per the specification's precondition.
"""
import csv, datetime, io, json, os, pickle, shutil, sys
import xlsxwriter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_lib as L
import p3_model as M
import p1_run as P1

SRC = "/sessions/optimistic-gallant-gauss/mnt/SIH-DATASETS-EXCEL-SHEET"
OUT = os.path.join(SRC, "BIS_SIH26107_DATA")
AN = os.path.join(OUT, "01_ANALYSIS")
TS = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
csv.field_size_limit(50_000_000)

# The sandbox caps a single run's wall clock, so pass B can be executed in slices:
#   P3FILES="F001-F030"  -> project only those source files in pass B
#   P3RESUME=1           -> append to the streams and restore every id sequence
#   P3FINAL=1            -> also run stages 5-13 (masters chunks .. Qdrant manifest)
# Stages 0-3 are deterministic and re-run in every slice, so the master tables are
# rewritten identically each time; nothing is carried in memory between slices except
# the counters and pass-B artifacts persisted in _cache/p3_passb.pkl.
SLICE = os.environ.get("P3FILES", "")
RESUME = os.environ.get("P3RESUME", "") == "1"
FINAL = os.environ.get("P3FINAL", "1" if not SLICE else "") == "1"
STATEP = os.path.join(AN, "_cache/p3_passb.pkl")
SEQIN, STATE = {}, {}
if RESUME:
    with open(STATEP, "rb") as _fh:
        STATE = pickle.load(_fh)
    SEQIN = STATE["seq"]


def in_slice(fid):
    if not SLICE:
        return True
    for part in SLICE.split(","):
        a, _, b = part.strip().partition("-")
        if a and (fid == a or (b and a <= fid <= b)):
            return True
    return False


# P3ROWS="F047:1-22000" projects only that 1-based row window of one source file, so a
# single very large file can span slices. Row order and content are untouched; the
# window only decides which rows this run writes.
ROWSLICE = {}
for _pt in os.environ.get("P3ROWS", "").split(","):
    if ":" in _pt:
        _f, _, _rr = _pt.strip().partition(":")
        _a, _, _b = _rr.partition("-")
        ROWSLICE[_f] = (int(_a), int(_b))
NORM_APPEND = False


T0 = __import__("time").time()


def p(*a):
    print("%6.1fs" % (__import__("time").time() - T0), *a, flush=True)


def opath(rel):
    f = os.path.join(OUT, rel)
    d = os.path.dirname(f)
    if d:
        os.makedirs(d, exist_ok=True)
    return f


def rollback(rel):
    """Cut a stream back to its last checkpointed byte length before reopening.

    The sandbox can kill a slice mid-write, leaving rows on disk that the checkpoint
    never recorded. Truncating to the recorded length makes every slice atomic: the
    rows a killed slice wrote are discarded and rewritten identically on retry, so no
    row is ever counted twice and no id is ever reused.
    """
    if not RESUME:
        return
    off = SEQIN.get("off:" + rel)
    f = opath(rel)
    if off is not None and os.path.exists(f) and os.path.getsize(f) != off:
        os.truncate(f, off)


class Stream(object):
    """Append-only CSV writer: keeps peak memory flat on the large tables."""

    def __init__(self, rel, cols):
        self.rel, self.cols = rel, list(cols)
        rollback(rel)
        self.fh = open(opath(rel), "a" if RESUME else "w", newline="",
                       encoding="utf-8-sig")
        self.w = csv.DictWriter(self.fh, fieldnames=self.cols,
                                extrasaction="ignore", quoting=csv.QUOTE_MINIMAL)
        if not RESUME:
            self.w.writeheader()
        self.n = SEQIN.get("stream:" + rel, 0)

    def add(self, row):
        self.w.writerow(row)
        self.n += 1

    def close(self):
        self.fh.close()


class Seq(object):
    def __init__(self, prefix, width=6):
        self.p, self.w = prefix, width
        self.n = SEQIN.get("seq:" + prefix, 0)

    def next(self):
        self.n += 1
        return "%s-%0*d" % (self.p, self.w, self.n)


# ---------------------------------------------------------------- stage 0
p("[0] loading Phase 1/2 analysis outputs")
INV = {r["file_id"]: r for r in L.rcsv(os.path.join(AN, "FILE_INVENTORY.csv"))}
DEC = {r["file_id"]: r for r in L.rcsv(os.path.join(AN, "CANONICAL_DECISIONS.csv"))}
CLS = {}
for r in L.rcsv(os.path.join(AN, "DATASET_CLASSIFICATION.csv")):
    CLS.setdefault(r["file_id"], r)
P2CONF = L.rcsv(os.path.join(AN, "CONFLICTS.csv"))
VERROWS = L.rcsv(os.path.join(AN, "VERSION_ANALYSIS.csv"))
NULLSEM = {}
for r in L.rcsv(os.path.join(AN, "PHASE1_NULL_SEMANTICS.csv")):
    NULLSEM[(r["file_id"], r["normalized_column_name"])] = r

BYNAME = {}
for fid, r in INV.items():
    BYNAME.setdefault(r["original_filename"], fid)

# Version direction evidence, measured - never inferred from the filename.
NEWER = {}
for r in VERROWS:
    if r["content_verdict"] not in ("VERSION_NEWER",):
        continue
    a, b = BYNAME.get(r["file_a"], ""), BYNAME.get(r["file_b"], "")
    w = BYNAME.get(r["newer_by_content"] or r["recommended_canonical_file"], "")
    if a and b and w:
        NEWER[(a, b)] = w
        NEWER[(b, a)] = w

POLICY = {r[0]: (r[2], r[4], r[3]) for r in M.CONFLICT_POLICY}   # name -> status, conf, reason
MCOL = {e: set(M.MASTER_COLS[e]) for e in M.ENT}
IDCOL = {e: M.MASTER_COLS[e][0] for e in M.ENT}
LABCOL = {"STANDARD": "canonical_is_number", "PRODUCT": "product_name",
          "QCO": "qco_number", "SCHEME": "scheme_name",
          "PRODUCT_MANUAL": "manual_title", "TEST": "test_name",
          "LABORATORY": "lab_name", "DOCUMENT": "title", "FAQ": "question",
          "NOTIFICATION": "notification_number", "LEGAL": "instrument_number",
          "HALLMARKING": "centre_name", "FMCS": "manufacturer_name"}

# Natural-key candidates, in precedence order. A row that satisfies none keeps a
# deterministic positional key and is flagged NO_NATURAL_KEY - never dropped.
KEYDEF = {
    "PRODUCT": [["product_name"]],
    "QCO": [["qco_number_normalized"], ["qco_number"], ["qco_name"]],
    "SCHEME": [["scheme_code"], ["scheme_name"], ["scheme_label"]],
    "PRODUCT_MANUAL": [["manual_title"], ["canonical_is_number"]],
    "TEST": [["test_name", "test_parameter"], ["test_name", "test_method"], ["test_name"]],
    "LABORATORY": [["lab_code"], ["lab_name", "city"], ["lab_name"]],
    "DOCUMENT": [["source_url"], ["download_url"], ["title"]],
    "FAQ": [["question"]],
    "NOTIFICATION": [["notification_number_normalized"], ["notification_number"], ["title"]],
    "LEGAL": [["instrument_number_normalized"], ["instrument_number"], ["title"]],
    "HALLMARKING": [["centre_code"], ["centre_name", "city"], ["centre_name"]],
    "FMCS": [["cml_licence_no"], ["manufacturer_name", "factory_address"],
             ["manufacturer_name"]],
}
# Where a canonical IS reference sits on a non-STANDARD row, the link becomes a
# relationship row (the spec forbids flattening a one-to-many into a cell).
IS_REL = {"QCO": ("IS_QCO_MAPPING", "MANDATES"),
          "SCHEME": ("IS_SCHEME_MAPPING", "CERTIFIABLE_UNDER"),
          "TEST": ("IS_TEST_MAPPING", "REQUIRED_BY"),
          "PRODUCT": ("IS_PRODUCT_MAPPING", "COVERED_BY"),
          "PRODUCT_MANUAL": ("IS_PRODUCT_MANUAL_MAPPING", "DOCUMENTED_BY"),
          "DOCUMENT": ("IS_DOCUMENT_MAPPING", "DOCUMENTS"),
          "FMCS": ("IS_FMCS_MAPPING", "LICENSED_FOR"),
          "LABORATORY": ("IS_LAB_TEST_MAPPING", "TESTABLE_AT"),
          "NOTIFICATION": ("NOTIFICATION_ENTITY_MAPPING", "ACTS_ON"),
          "FAQ": ("IS_ENTITY_MAPPING", "REFERENCED_BY"),
          "LEGAL": ("IS_ENTITY_MAPPING", "REFERENCED_BY"),
          "HALLMARKING": ("IS_ENTITY_MAPPING", "REFERENCED_BY")}
for _e, (_t, _r) in IS_REL.items():
    assert _t in M.REL_BY_NAME, "IS_REL table %s unknown" % _t
# Files whose rows are verbatim aux/telemetry records, not domain entities.
STREAM_ONLY = {"F047": "RECORD_PROVENANCE", "F043": "FMCS_IS_COVERAGE",
               "F042": "FMCS_COUNTRY_COVERAGE", "F007": "LAB_SCOPE",
               "F048": "REVIEW_QUEUE", "F041": "EXTRACTION_LOG",
               "F004": "CONFLICT_REGISTER"}
FIELD_MA = {"raw_is_number_variants": "UNION_APPEND_DISTINCT",
            "source_reference_label": "UNION_APPEND_DISTINCT",
            "display_is_number": "UNION_LONGEST", "parse_status": "UNION_COALESCE",
            "part_source": "UNION_COALESCE"}
for _e in M.ENT:
    for _agg in M.SURROGATE.values():
        if _agg in MCOL[_e]:
            FIELD_MA[_agg] = "UNION_APPEND_DISTINCT"
# ------------------------------------------------- comparison + conflict rules
_PUNCT = str.maketrans({c: " " for c in ".,;:/\\-_()[]{}'\"`|"})


def nrm(v):
    return " ".join(str(v).lower().translate(_PUNCT).split())


def eq(a, b):
    return nrm(a) == nrm(b)


def classify(a, b, st, fa, fb):
    """Return one of the 11 CONFLICT_POLICY rule names. Evidence only."""
    if eq(a, b):
        return "SAME_VALUE_DIFFERENT_FORMAT"
    if not a or not b:
        return "ONE_SIDE_NULL"
    ca, cb = L.nullclass(a), L.nullclass(b)
    if "ASSERTED_ABSENCE" in (ca, cb):
        return "ASSERTED_ABSENCE_VS_VALUE"
    if ca != "POPULATED" or cb != "POPULATED":
        return "ONE_SIDE_PLACEHOLDER"
    na, nb = nrm(a), nrm(b)
    if na and nb and (na in nb or nb in na):
        return "SUBSTRING_ENRICHMENT"
    if NEWER.get((fa, fb)):
        return "VERSION_EVIDENCE"
    s = (st or "").upper()
    if "STATUS" in s:
        return "STATUS_DISAGREEMENT"
    if "DATE" in s:
        return "DATE_DISAGREEMENT"
    if "NUM" in s or "COUNT" in s or "INT" in s:
        return "NUMERIC_DISAGREEMENT"
    return "FREE_TEXT_DIVERGENCE"


def winner(rule, a, b, fa, fb):
    """The evidence-supported value for a RESOLVED rule, else "" - never invented."""
    if rule in ("SAME_VALUE_DIFFERENT_FORMAT",):
        return a if len(a) >= len(b) else b
    if rule in ("ONE_SIDE_NULL", "ONE_SIDE_PLACEHOLDER"):
        return a if L.nullclass(a) == "POPULATED" and a else b
    if rule == "SUBSTRING_ENRICHMENT":
        return a if len(a) >= len(b) else b
    if rule == "VERSION_EVIDENCE":
        w = NEWER.get((fa, fb), "")
        return a if w == fa else b
    return ""


CONF = Stream("92_VALIDATION/CONFLICT_STATUS.csv", M.CONFLICT_COLS)
SUPPRESS_CONF = RESUME
CSEQ = Seq("CFL")
CONFLICT_FIELDS = {}          # (ent,key) -> [field, ...]
CONF_ROWS = {"RESOLVED": 0, "UNRESOLVED_PRESERVE_BOTH": 0, "REQUIRES_REVIEW": 0}
CONF_SRC_ROWS = set()         # (fid, sheet, row) that contributed a conflicting value


def emit_conflict(ent, eid, label, field, A, B, st, rule, chosen, force=""):
    status, conf, reason = POLICY[rule]
    if force:
        status, conf = force, "0.00"
        reason = reason + " Field is a KEY_IDENTITY field, so divergence cannot be auto-resolved."
    va, fa, sha, ra = A
    vb, fb, shb, rb = B
    if SUPPRESS_CONF:
        # A resumed slice re-derives stage 3 to rebuild the masters; the conflict rows
        # it already wrote in the first slice must not be duplicated. The decision and
        # every downstream counter below are still recomputed identically.
        CONF_ROWS[status] = CONF_ROWS.get(status, 0) + 1
        CONFLICT_FIELDS.setdefault((ent, "%s|%s" % (eid, label)), [])
        CONF_SRC_ROWS.add((fa, sha, ra))
        CONF_SRC_ROWS.add((fb, shb, rb))
        return status
    CONF.add({"conflict_id": CSEQ.next(), "entity_type": ent, "entity_id": eid,
              "entity_label": label, "field": field,
              "source_a": INV.get(fa, {}).get("original_filename", fa),
              "source_a_file_id": fa, "value_a": va, "source_row_a": ra, "date_a": "",
              "source_b": INV.get(fb, {}).get("original_filename", fb),
              "source_b_file_id": fb, "value_b": vb, "source_row_b": rb, "date_b": "",
              "resolution_status": status, "resolution_rule": rule,
              "resolution_reason": reason,
              "canonical_value": chosen if status == "RESOLVED" else "",
              "confidence": conf,
              "review_flag": "YES" if status != "RESOLVED" else ""})
    CONF_ROWS[status] = CONF_ROWS.get(status, 0) + 1
    CONFLICT_FIELDS.setdefault((ent, "%s|%s" % (eid, label)), [])
    CONF_SRC_ROWS.add((fa, sha, ra))
    CONF_SRC_ROWS.add((fb, shb, rb))
    return status


def merge_field(ent, eid, label, cc, contribs):
    """contribs: [(value, base, fid, sheet, row)] -> (value, conflicted, review)."""
    keep = []
    for v, base, fid, sh, rw in contribs:
        if not any(eq(v, k[0]) for k in keep):
            keep.append((v, base, fid, sh, rw))
    if len(keep) == 1:
        return keep[0][0], False, ""
    ma = FIELD_MA.get(cc) or contribs[0][1][2]
    st = contribs[0][1][4]
    vals = [k[0] for k in keep]
    if ma == "UNION_APPEND_DISTINCT":
        return " | ".join(vals), False, ""
    base_v, review = keep[0][0], ""
    if ma == "UNION_LONGEST":
        base_v = max(vals, key=len)
    conflicted = False
    for k in keep[1:]:
        rule = classify(keep[0][0], k[0], st, keep[0][2], k[2])
        force = ""
        if ma == "KEY_IDENTITY" and POLICY[rule][0] != "RESOLVED":
            force = "REQUIRES_REVIEW"
        w = winner(rule, keep[0][0], k[0], keep[0][2], k[2])
        chosen = w or base_v
        status = emit_conflict(ent, eid, label, cc,
                              (keep[0][0], keep[0][2], keep[0][3], keep[0][4]),
                              (k[0], k[2], k[3], k[4]), st, rule, chosen, force)
        if status != "RESOLVED":
            conflicted = True
            if status == "REQUIRES_REVIEW":
                review = "CONFLICT_" + rule
        if w and ma != "UNION_APPEND_DISTINCT":
            base_v = w
    return base_v, conflicted, review
# ------------------------------------------------------------- projection core
def expand(cc, tr, out):
    """A dict/tuple transform yields several canonical fields from one cell."""
    sf = M.SUBFIELD.get(tr)
    if not sf:
        return [(cc, L.nws(out) if isinstance(out, str) else str(out))], {}
    pairs, ex = [], {}
    items = list(out.items()) if isinstance(out, dict) else list(enumerate(out))
    for k, v in items:
        name = sf.get(k)
        v = L.nws(v) if isinstance(v, str) else ("" if v is None else str(v))
        if name is None:
            if v:
                pairs.append(("%s_%s" % (cc, k), v))
            continue
        if not v or name == "@drop":
            continue
        if name == "@review":
            ex["review"] = v
        elif name == "@original":
            ex["orig"] = v
        elif name == "@label":
            ex["label"] = v
        else:
            pairs.append((name.replace("{}", cc), v))
    return pairs, ex


def project(fid, ent, headers, row):
    """Pure: one source row -> canonical parts. Same output in pass A and pass B."""
    P = {"f": {}, "a": [], "e": [], "l": [], "nul": [], "rev": [], "prov": [],
         "raw": {}, "norm": {}, "stdkey": "", "seed": {}, "label": ""}
    for i, col in enumerate(headers):
        raw = row[i] if i < len(row) else ""
        cc, st, ma, tr, tg, rs = M.resolve(fid, col, ent)
        P["raw"][col] = raw
        base = (col, tr, ma, rs, st)
        cls = L.nullclass(raw)
        if cls != "POPULATED":
            P["nul"].append((cc, L.nws(raw), cls, base))
            if cls == "ASSERTED_ABSENCE":
                P["a"].append((cc, "", base, cls, L.nws(raw)))
            elif cls == "AMBIGUOUS_REQUIRES_REVIEW":
                P["rev"].append(("AMBIGUOUS_PLACEHOLDER", cc, L.nws(raw)))
            continue
        fn = L.TRANSFORMS.get(tr)
        out = fn(raw) if fn else L.nws(raw)
        if isinstance(out, list):
            for frag in out:
                P["e"].append((cc, frag, base))
            P["norm"][col] = " | ".join(
                (f.get("display_is_number") or f.get("canonical_is_number", ""))
                if isinstance(f, dict) else str(f) for f in out)
            continue
        pairs, ex = expand(cc, tr, out)
        if ex.get("review"):
            P["rev"].append(("TRANSFORM_FLAG_" + ex["review"], cc, L.nws(raw)))
        if ex.get("orig"):
            P["a"].append((cc + "_original_value", ex["orig"], base, "POPULATED", ""))
        if ex.get("label"):
            lab = "source_reference_label"
            (P["f"].setdefault(lab, []).append((ex["label"], base))
             if lab in MCOL.get(ent, ()) else
             P["a"].append((lab, ex["label"], base, "POPULATED", "")))
        P["norm"][col] = pairs[0][1] if pairs else ""
        if tr == "nis":
            d = dict(pairs)
            skey = out.get("is_id", "")
            P["stdkey"] = P["stdkey"] or skey
            if skey:
                sd = P["seed"].setdefault(skey, {})
                for nm, v in pairs:
                    if v and nm in MCOL["STANDARD"]:
                        sd.setdefault(nm, v)
                if d.get("canonical_is_number"):
                    sd.setdefault("canonical_is_number", d["canonical_is_number"])
            if ent == "STANDARD":
                for nm, v in pairs:
                    (P["f"].setdefault(nm, []).append((v, base))
                     if nm in MCOL["STANDARD"] else
                     P["a"].append((nm, v, base, "POPULATED", "")))
            else:
                P["a"].append(("is_semantic_key", skey, base, "POPULATED", ""))
                for nm in ("canonical_is_number", "display_is_number"):
                    if nm in MCOL.get(ent, ()) and d.get(nm):
                        P["f"].setdefault(nm, []).append((d[nm], base))
                if skey:
                    P["l"].append(("__IS__", skey, base))
            continue
        for nm, v in pairs:
            if not v:
                continue
            nm = M.MASTER_ALIAS.get((ent, nm), nm)
            if ma == "PROVENANCE_ONLY":
                P["prov"].append((nm, v, base))
                continue
            if (ent, nm) in M.EXPLODE_ROUTE or ma == "EXPLODE_TO_RELATIONSHIP":
                P["e"].append((nm, v, base))
                continue
            if (ent, nm) in M.LINK_FIELD:
                P["l"].append((nm, v, base))
                also = M.LINK_FIELD[(ent, nm)][4]
                if nm not in MCOL.get(ent, ()) and not also:
                    continue
            if nm in MCOL.get(ent, ()) and ma != "PRESERVE_AS_ATTRIBUTE":
                P["f"].setdefault(nm, []).append((v, base))
            else:
                P["a"].append((nm, v, base, "POPULATED", ""))
    lab = LABCOL.get(ent, "")
    if lab and lab in P["f"]:
        P["label"] = P["f"][lab][0][0]
    return P


def rows_of(fid):
    """Yield (sheet, row_number, headers, row) for one source file.

    Parsing is cached verbatim under 01_ANALYSIS/_cache/rows/ so that pass A and pass B
    read identical bytes and neither re-parses the workbook. The cache is a faithful copy
    of what Phase 1's loaders returned - no cleaning, no coercion.
    """
    cp = os.path.join(SRC, "BIS_SIH26107_DATA/01_ANALYSIS/_cache/rows/%s.pkl" % fid)
    if os.path.exists(cp):
        with open(cp, "rb") as fh:
            for t in pickle.load(fh):
                yield t
        return
    out = []
    for t in _rows_raw(fid):
        out.append(t)
        yield t
    os.makedirs(os.path.dirname(cp), exist_ok=True)
    with open(cp + ".tmp", "wb") as fh:
        pickle.dump(out, fh, protocol=4)
    os.replace(cp + ".tmp", cp)


def _rows_raw(fid):
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
    # else: non-tabular (F049 PDF). Phase 1 measured 0 data rows, so the record is
    # created from inventory metadata - nothing lost, nothing invented.
# ------------------------------------------------- entity keys and STANDARD seed
IS_FRAG = {"display_is_number": "display_is_number",
           "canonical_is_number": "canonical_is_number", "year": "standard_year",
           "part": "part_number", "part_source": "part_source",
           "section": "section_number", "amendment": "amendment_reference",
           "is_iec": "is_iec_flag"}
STREAM_DS = {f: M.ROUTE[f][0] for f in M.ROUTE if M.ROUTE[f][0] not in M.ENT}
assert set(STREAM_DS) == set(STREAM_ONLY), "stream-only set drifted from ROUTE"
AUXPATH = {a[0]: a[1] for a in M.AUX_DATASETS}
MINT = {e: L.Mint(M.PREFIX[e]) for e in M.ENT}
CONTRIB = {}          # (ent, key) -> {canonical_column: [(v, base, fid, sheet, row)]}
KEYSRC = {}           # (ent, key) -> [(fid, sheet, row, keyrule)]
LABEL = {}            # (ent, key) -> best human label seen
ROWKEY = {}           # (fid, sheet, row) -> (ent, key)  for pass B
ROWCNT = {}           # fid -> rows read
NOKEY = set()         # (ent, key) minted from a positional fallback


def frag_key(cent, frag):
    """Natural key + seed fields for one exploded counterpart fragment."""
    if isinstance(frag, dict):
        if cent == "STANDARD":
            k = frag.get("standard_id", "")
            sd = {}
            for a, b in IS_FRAG.items():
                if frag.get(a):
                    sd[b] = frag[a]
            return k, frag.get("display_is_number") or k, sd
        v = frag.get("value") or " ".join(str(x) for x in frag.values() if x)
        return v, v, {}
    v = L.nws(frag)
    return v, v, {}


def frag_disp(frag):
    if isinstance(frag, dict):
        return (frag.get("display_is_number") or frag.get("canonical_is_number") or
                " ".join(str(x) for x in frag.values() if x))
    return L.nws(frag)


def natkey(ent, P, fid, sheet, row):
    if ent == "STANDARD":
        return (P["stdkey"], "IS_SEMANTIC_KEY") if P["stdkey"] else \
               ("%s|%s|%s" % (fid, sheet, row), "NO_NATURAL_KEY")
    for cand in KEYDEF.get(ent, []):
        parts = [P["f"][c][0][0] for c in cand if P["f"].get(c)]
        if len(parts) == len(cand) and all(parts):
            return nrm(" ".join(parts)), "+".join(cand)
    return "%s|%s|%s" % (fid, sheet, row), "NO_NATURAL_KEY"


def contribute(ent, key, cc, v, base, fid, sheet, row):
    CONTRIB.setdefault((ent, key), {}).setdefault(cc, []).append(
        (v, base, fid, sheet, row))


def seed_std(key, sd, base, fid, sheet, row):
    MINT["STANDARD"].add(key)
    for cc, v in sd.items():
        if v and cc in MCOL["STANDARD"]:
            contribute("STANDARD", key, cc, v, base, fid, sheet, row)
    LABEL.setdefault(("STANDARD", key), sd.get("canonical_is_number", ""))
SEEDBASE = ("(IS parse)", "nis", "UNION_COALESCE", "IS_PARSE_SEED", "IS_NUMBER")
REFBASE = ("(reference)", "nws", "UNION_COALESCE", "COUNTERPART_REFERENCE", "TEXT")
DIRECT = set()        # (ent, key) that came from a real entity row


def ckey(cent, v):
    """Counterpart natural key + normalized label, using the same transform the
    owning entity's own key would have passed through."""
    v = L.nws(v)
    if not v:
        return "", ""
    if cent == "STANDARD":
        d = L.TRANSFORMS["nis"](v)
        return d.get("is_id", ""), d.get("canonical_is_number", "") or v
    if cent == "QCO":
        n = L.TRANSFORMS["nqco"](v)
        return nrm(n), n
    if cent == "NOTIFICATION":
        n = L.TRANSFORMS["nnotif"](v)
        return nrm(n), n
    n = L.TRANSFORMS["nname"](v)
    return nrm(n), n


def mint_ref(cent, val_or_frag, fid, sheet, row):
    """Mint a counterpart referenced from another row and give it a labelled
    master row, so no relationship can be orphaned. Returns the mint key."""
    if cent == "STANDARD":
        if isinstance(val_or_frag, dict):
            k, lab, sd = frag_key("STANDARD", val_or_frag)
        else:
            k, lab = ckey("STANDARD", val_or_frag)
            sd = {"canonical_is_number": lab} if k else {}
        if not k:
            return ""
        seed_std(k, sd, SEEDBASE, fid, sheet, row)
        return k
    k, lab = ckey(cent, frag_disp(val_or_frag))
    if not k:
        return ""
    MINT[cent].add(k)
    lc = LABCOL.get(cent, "")
    if lc and lc in MCOL.get(cent, ()):
        contribute(cent, k, lc, lab, REFBASE, fid, sheet, row)
    if len(lab) > len(LABEL.get((cent, k), "")):
        LABEL[(cent, k)] = lab
    return k
PSEUDO_ENT = {"LAB_SCOPE": ("LABORATORY", "TEST"), "FMCS_IS_COVERAGE": ("FMCS",),
              "FMCS_COUNTRY_COVERAGE": ("FMCS",)}
# The id column each entity is referenced by, in masters and relationship tables.
FKMAP = {"STANDARD": "is_id", "PRODUCT": "product_id", "QCO": "qco_id",
         "SCHEME": "scheme_id", "DOCUMENT": "document_id", "TEST": "test_id",
         "LABORATORY": "lab_id", "PRODUCT_MANUAL": "manual_id", "FMCS": "fmcs_id",
         "NOTIFICATION": "notification_id", "HALLMARKING": "centre_id",
         "LEGAL": "legal_id", "FAQ": "faq_id"}
FKCONTRIB = {}        # (ent, key) -> {fk_column: (counterpart_entity, counterpart_key)}


def rowvals(P):
    v = {}
    for cc, lst in P["f"].items():
        if lst:
            v.setdefault(cc, lst[0][0])
    for nm, val, base, cls, orig in P["a"]:
        if val:
            v.setdefault(nm, val)
    return v


def pseudo_keys(ent, P):
    """A stream-only row still identifies real entities. Resolve them with the very
    same natural-key candidates those entities' own rows use."""
    got, vals = {}, rowvals(P)
    for target in PSEUDO_ENT.get(ent, ()):
        for cand in KEYDEF.get(target, []):
            parts = [vals[c] for c in cand if vals.get(c)]
            if len(parts) == len(cand) and all(parts):
                got[target] = (nrm(" ".join(parts)), vals[cand[0]])
                break
    return got


def counterparts(ent, P, fid, sheet, row):
    """Mint every counterpart this row references and return [(entity, key)].
    The relationship rows themselves are written in pass B from the same routes,
    so pass A only has to guarantee that every referenced id exists."""
    refs = []
    for cc, frag, base in P["e"]:
        r = M.EXPLODE_ROUTE.get((ent, cc))
        if r and r[0] == "REL" and r[4] and r[3]:
            k = mint_ref(r[3], frag, fid, sheet, row)
            if k:
                refs.append((r[3], k))
        elif not r and isinstance(frag, dict) and frag.get("standard_id"):
            k = mint_ref("STANDARD", frag, fid, sheet, row)
            if k:
                refs.append(("STANDARD", k))
    for nm, v, base in P["l"]:
        if nm == "__IS__":
            refs.append(("STANDARD", v))       # already minted from P["seed"]
            continue
        lf = M.LINK_FIELD.get((ent, nm))
        if lf and lf[3] and lf[2]:
            k = mint_ref(lf[2], v, fid, sheet, row)
            if k:
                refs.append((lf[2], k))
    for target, (k, lab) in pseudo_keys(ent, P).items():
        MINT[target].add(k)
        lc = LABCOL.get(target, "")
        if lc:
            contribute(target, k, lc, lab, REFBASE, fid, sheet, row)
        if len(lab) > len(LABEL.get((target, k), "")):
            LABEL[(target, k)] = lab
        refs.append((target, k))
    return refs


# ---------------------------------------------------------------- stage 1 pass A
p("[1] pass A - reading 49 sources, collecting keys and field contributions")
for fid in sorted(INV):
    ent = M.ROUTE[fid][0]
    n = 0
    for sheet, rno, headers, row in rows_of(fid):
        n += 1
        P = project(fid, ent, headers, row)
        for skey, sd in P["seed"].items():
            seed_std(skey, sd, SEEDBASE, fid, sheet, rno)
        refs = counterparts(ent, P, fid, sheet, rno)
        if ent not in M.ENT:
            continue
        key, rule = natkey(ent, P, fid, sheet, rno)
        for _ce, _ck in refs:
            _fk = FKMAP.get(_ce, "")
            if _fk and _fk in MCOL[ent] and _fk != IDCOL[ent]:
                FKCONTRIB.setdefault((ent, key), {}).setdefault(_fk, (_ce, _ck))
        MINT[ent].add(key)
        DIRECT.add((ent, key))
        ROWKEY[(fid, sheet, rno)] = (ent, key)
        KEYSRC.setdefault((ent, key), []).append((fid, sheet, rno, rule))
        if rule == "NO_NATURAL_KEY":
            NOKEY.add((ent, key))
        for cc, lst in P["f"].items():
            for v, base in lst:
                contribute(ent, key, cc, v, base, fid, sheet, rno)
        if P["label"] and len(P["label"]) > len(LABEL.get((ent, key), "")):
            LABEL[(ent, key)] = P["label"]
    ROWCNT[fid] = n
    p("    A %s %-52s rows %6d  keys %7d" % (fid, M.ROUTE[fid][0][:52], n,
                                             len(ROWKEY)))
p("    rows read %d | entity rows %d | contributions %d"
  % (sum(ROWCNT.values()), len(ROWKEY),
     sum(len(v) for d in CONTRIB.values() for v in d.values())))

# ---------------------------------------------------------------- stage 2 mints
p("[2] sealing surrogate identifiers")
EID = {}
for e in M.ENT:
    MINT[e].seal()
    p("    %-15s %s-xxxxx  %6d" % (e, M.PREFIX[e], len(MINT[e])))
for (e, k) in list(CONTRIB) + list(KEYSRC):
    EID[(e, k)] = MINT[e].get(k)
# ------------------------------------------------------------- stage 3 masters
p("[3] building 13 master tables (merge + conflict capture)")
MASTERS = {}          # ent -> [row dict]
ROWDISP = {}          # (fid, sheet, row) -> (disposition, reason)
ENT_KEYS = {}         # ent -> sorted keys
MASTER_BY_ID = {}     # (ent, entity_id) -> row  (for the IS_COMPLETE view)
for ent in M.ENT:
    cols = M.MASTER_COLS[ent]
    body = [c for c in cols if c not in M.TAIL and c != IDCOL[ent]]
    keys = sorted(set([k for (e, k) in CONTRIB if e == ent] +
                      [k for (e, k) in KEYSRC if e == ent]),
                  key=lambda k: MINT[ent].get(k) or k)
    ENT_KEYS[ent] = keys
    out = []
    for k in keys:
        eid = MINT[ent].get(k)
        lab = LABEL.get((ent, k), "")
        cb = CONTRIB.get((ent, k), {})
        row = {IDCOL[ent]: eid}
        cflds, ccount, review, rr = [], 0, "", []
        for cc in body:
            lst = cb.get(cc)
            if not lst:
                continue
            v, conflicted, rv = merge_field(ent, eid, lab, cc, lst)
            row[cc] = v
            if conflicted:
                cflds.append(cc)
            if rv:
                review = review or rv
                rr.append(rv)
        for _fk, (_ce, _ck) in FKCONTRIB.get((ent, k), {}).items():
            _v = MINT[_ce].get(_ck)
            if _v and not row.get(_fk):
                row[_fk] = _v
        srcs = list(KEYSRC.get((ent, k), []))
        seen = set((s[0], s[1], s[2]) for s in srcs)
        for cc, lst in cb.items():
            for _v, _b, f, s, r in lst:
                if (f, s, r) not in seen:
                    seen.add((f, s, r))
                    srcs.append((f, s, r, "REFERENCE"))
        fids = sorted(set(s[0] for s in srcs))
        row["source_file_count"] = len(fids)
        row["source_file_ids"] = ";".join(fids)
        row["source_files"] = ";".join(
            sorted(set(INV.get(f, {}).get("original_filename", f) for f in fids)))
        row["source_sheets"] = ";".join(sorted(set(s[1] for s in srcs if s[1])))
        row["source_rows"] = ";".join(
            "%s:%s:%s" % (s[0], s[1] or "-", s[2]) for s in srcs[:200])
        ccount = len(cflds)
        row["conflict_count"] = ccount
        row["conflict_fields"] = ";".join(sorted(set(cflds)))
        if (ent, k) in NOKEY:
            review = review or "NO_NATURAL_KEY"
            rr.append("Row carried no value in any natural-key column; keyed positionally.")
        if (ent, k) not in DIRECT:
            rr.append("Record exists because another record referenced it.")
        disp = "CANONICAL"
        if len([1 for s in srcs if s[3] != "REFERENCE"]) > 1:
            disp = "MERGED"
        if ccount:
            disp = "CONFLICT_PRESERVED"
        if review:
            disp = "REQUIRES_REVIEW"
        row["record_disposition"] = disp
        row["review_flag"] = "YES" if review else ""
        row["review_reason"] = " ".join(rr)[:900]
        pf = len([1 for c in body if row.get(c)])
        row["populated_field_count"] = pf
        row["completeness_pct"] = "%.2f" % (100.0 * pf / max(1, len(body)))
        for s in srcs:
            if s[3] != "REFERENCE":
                ROWDISP[(s[0], s[1], s[2])] = (disp, review or "")
        out.append(row)
        MASTER_BY_ID[(ent, eid)] = row
    MASTERS[ent] = out
    L.wcsv(opath("00_MASTER/%s" % dict(M.MASTER)[ent]), out, cols)
    p("    %-15s %-28s %6d rows x %d cols"
      % (ent, dict(M.MASTER)[ent], len(out), len(cols)))
# -------------------------------------------------------------- stage 4 streams
p("[4] pass B - attributes, relationships, provenance, PM sections, aux")
RELID = {e: (FKMAP[e], LABCOL[e]) for e in M.ENT}
ACTX = {f: M.ATTR_CONTEXT.get(f, M.ROUTE[f][2]) for f in M.ROUTE}
ATTR = Stream("00_MASTER/ENTITY_ATTRIBUTES.csv", M.AUX_COLS["ENTITY_ATTRIBUTES"])
PROV = Stream("91_PROVENANCE/RECORD_PROVENANCE.csv", M.AUX_COLS["RECORD_PROVENANCE"])
RQ = Stream("92_VALIDATION/REQUIRES_REVIEW.csv", M.AUX_COLS["REVIEW_QUEUE"])
DLA_COLS = ["source_file_id", "source_file", "source_sheet", "source_row",
            "route_target", "entity_type", "entity_id", "entity_label",
            "record_disposition", "disposition_reason", "fields_projected",
            "fields_populated", "attributes_written", "relationships_written",
            "provenance_rows"]
DLA = Stream("92_VALIDATION/DATA_LOSS_AUDIT.csv", DLA_COLS)
RELS = {n: Stream("90_RELATIONSHIPS/%s" % M.REL_BY_NAME[n][1], M.REL_COLS[n])
        for n in M.REL_BY_NAME}
RSEQ = {n: Seq("REL-" + n[:6], 7) for n in M.REL_BY_NAME}
PMCAT = sorted(set(M.PM_SECTION_ROUTE.values()))
PMS = {c: Stream("00_MASTER/PRODUCT_MANUAL_%s.csv" % c, M.PM_SECTION_COLS)
       for c in PMCAT}
PMSEQ = Seq("PMS", 6)
ASEQ, PSEQ, RVSEQ = Seq("ATT", 7), Seq("PRV", 7), Seq("RVW")
AUXBUF = {}           # stream-only dataset name -> (cols, rows)
ORPHAN = []
UNMATCHED = 0


def put(r, cols, ent, eid, lab):
    idc, labc = RELID.get(ent, ("", ""))
    if idc and idc in cols and not r.get(idc):
        r[idc] = eid
        if labc in cols:
            r[labc] = lab
        return True
    if ent == "STANDARD" and "related_is_id" in cols and not r.get("related_is_id"):
        r["related_is_id"], r["related_canonical_is_number"] = eid, lab
        return True
    for a, b, c in (("entity_type", "entity_id", "entity_label"),
                    ("target_entity", "target_entity_id", "target_entity_label")):
        if a in cols and not r.get(b):
            r[a], r[b], r[c] = ent, eid, lab
            return True
    if "scope_item" in cols and not r.get("scope_item"):
        r["scope_item"] = lab
        return True
    return False
def fname(fid):
    return INV.get(fid, {}).get("original_filename", fid)


def cp_id(cent, frag):
    """Pass-B counterpart resolution - the identical derivation mint_ref used."""
    if cent == "STANDARD" and isinstance(frag, dict) and frag.get("standard_id"):
        k = frag["standard_id"]
    else:
        k, _l = ckey(cent, frag_disp(frag))
    if not k:
        return "", frag_disp(frag)
    return MINT[cent].get(k), (LABEL.get((cent, k), "") or frag_disp(frag))


def emit_attr(ent, eid, lab, fid, sheet, row, name, value, base, cls, orig, url=""):
    ATTR.add({"attribute_id": ASEQ.next(), "entity_type": ent, "entity_id": eid,
              "entity_label": lab, "attribute_name": name, "attribute_value": value,
              "value_length": len(value or ""), "semantic_type": base[4],
              "attribute_context": ACTX.get(fid, ""), "null_class": cls,
              "original_value": orig, "missing_reason": L.missing_reason(cls),
              "source_file_id": fid, "source_file": fname(fid), "source_sheet": sheet,
              "source_row": row, "source_column": base[0],
              "transformation_rule": base[1], "merge_action": base[2],
              "rule_source": base[3], "source_url": url,
              "review_flag": "YES" if cls == "AMBIGUOUS_REQUIRES_REVIEW" else ""})


def emit_prov(origin, ent, eid, lab, cc, cv, fid, sheet, row, base, sv, cls, disp,
              url="", extra=None):
    r = {"provenance_id": PSEQ.next(), "provenance_origin": origin,
         "entity_type": ent, "entity_id": eid, "entity_label": lab,
         "canonical_column": cc, "canonical_value": cv, "source_file_id": fid,
         "source_file": fname(fid), "source_sheet": sheet, "source_row": row,
         "source_column": base[0], "source_value": sv, "null_class": cls,
         "missing_reason": L.missing_reason(cls), "transformation_rule": base[1],
         "merge_action": base[2], "rule_source": base[3],
         "record_disposition": disp, "source_url": url, "source_title": fname(fid),
         "source_type": M.ROUTE.get(fid, ("", "", ""))[2],
         "verification_status": "SOURCE_TRACED", "confidence": "1.00"}
    if extra:
        for k2, v2 in extra.items():
            if k2 in M.AUX_COLS["RECORD_PROVENANCE"] and v2 not in (None, ""):
                r[k2] = v2
    PROV.add(r)


def emit_review(ent, eid, lab, field, fv, rclass, reason, action, fid, sheet, row,
                url="", verdict=""):
    RQ.add({"review_id": RVSEQ.next(), "entity_type": ent, "entity_id": eid,
            "entity_label": lab, "field": field, "field_value": fv,
            "review_class": rclass, "review_reason": reason,
            "required_action": action, "source_file_id": fid,
            "source_file": fname(fid), "source_sheet": sheet, "source_row": row,
            "attempted_source_url": url, "phase2_verdict": verdict,
            "resolution_status": "OPEN"})
def emit_rel(name, sides, rtype, ctx, ecol, ev, fid, sheet, row, extra=None):
    """One relationship row. `sides` fill the table's id columns in order, so a
    3-way table (IS_LAB_TEST_MAPPING) is served by the same routine as a 2-way one."""
    cols = M.REL_COLS[name]
    r = {"relationship_id": RSEQ[name].next(), "relationship_type": rtype,
         "relation_context": ctx, "evidence_column": ecol, "evidence_value": ev,
         "source_file_ids": fid, "source_files": fname(fid), "source_sheets": sheet,
         "source_rows": row, "confidence": "1.00"}
    if extra:                       # written first: put() must not claim the slot
        for k2, v2 in extra.items():
            if k2 in cols and v2 not in (None, ""):
                r[k2] = v2
    unres = []
    for ent, eid, lab in sides:
        if eid:
            put(r, cols, ent, eid, lab)
        else:
            unres.append("%s:%s" % (ent, lab or "?"))
    if unres:
        r["unmatched_reference"] = ";".join(unres)
        r["confidence"], r["review_flag"] = "0.60", "YES"
        ORPHAN.append({"relationship_table": name, "relationship_type": rtype,
                       "unmatched_reference": ";".join(unres),
                       "evidence_column": ecol, "evidence_value": ev,
                       "resolved_sides": ";".join("%s=%s" % (e, i)
                                                  for e, i, _l in sides if i),
                       "source_file_id": fid, "source_file": fname(fid),
                       "source_sheet": sheet, "source_row": row,
                       "reason": "Referenced counterpart could not be resolved to a "
                                 "canonical id from the uploaded data."})
    RELS[name].add(r)
    return 1


def emit_rels(ent, P, fid, sheet, row, sides0):
    """Explode every multi-value cell and every link into relationship rows.
    `sides0` are this row's own entities (>1 for a pseudo-entity stream row)."""
    nr = na = 0
    e0 = sides0[0] if sides0 else (ent, "", "")
    for cc, frag, base in P["e"]:
        rt = M.EXPLODE_ROUTE.get((ent, cc))
        disp = frag_disp(frag)
        if not disp:
            continue
        if rt and rt[0] == "ATTR":
            emit_attr(e0[0], e0[1], e0[2], fid, sheet, row, rt[1], disp, base,
                      "POPULATED", "")
            na += 1
            continue
        if rt and rt[0] == "REL":
            tbl, rty, cpe = rt[1], rt[2], rt[3]
            if cpe:
                cid, clab = cp_id(cpe, frag)
                nr += emit_rel(tbl, sides0 + [(cpe, cid, clab)], rty, cc, cc, disp,
                               fid, sheet, row)
            else:
                nr += emit_rel(tbl, sides0, rty, cc, cc, disp, fid, sheet, row,
                               {"scope_item": disp})
            continue
        if isinstance(frag, dict) and frag.get("standard_id"):
            tbl, rty = IS_REL.get(ent, ("IS_RELATED_IS", "RELATED_TO"))
            cid, clab = cp_id("STANDARD", frag)
            nr += emit_rel(tbl, sides0 + [("STANDARD", cid, clab)], rty, cc, cc,
                           disp, fid, sheet, row)
            continue
        emit_attr(e0[0], e0[1], e0[2], fid, sheet, row, cc, disp, base,
                  "POPULATED", "")
        na += 1
    for nm, v, base in P["l"]:
        if nm == "__IS__":
            tbl, rty = IS_REL.get(ent, ("IS_RELATED_IS", "RELATED_TO"))
            cid = MINT["STANDARD"].get(v)
            clab = LABEL.get(("STANDARD", v), "")
            nr += emit_rel(tbl, sides0 + [("STANDARD", cid, clab)], rty,
                           "canonical_is_number", base[0], clab or v,
                           fid, sheet, row)
            continue
        lf = M.LINK_FIELD.get((ent, nm))
        if not lf or not lf[2]:
            continue
        cid, clab = cp_id(lf[2], v)
        nr += emit_rel(lf[0], sides0 + [(lf[2], cid, clab)], lf[1], nm, base[0],
                       L.nws(v), fid, sheet, row)
    return nr, na
FOLDER_OF = {}
for _fold, _ids in M.FOLDER_PLAN:
    for _f in [x.strip() for x in _ids.split(",") if x.strip()]:
        FOLDER_OF[_f] = _fold
for _fold, _ids in M.FOLDER_PLAN:
    os.makedirs(opath("01_SOURCE_DATA/%s" % _fold), exist_ok=True)


class Jsonl(object):
    def __init__(self, rel):
        rollback(rel)
        self.fh = open(opath(rel), "a" if RESUME else "w", encoding="utf-8")
        self.n = SEQIN.get("stream:" + rel, 0)

    def add(self, o):
        self.fh.write(json.dumps(o, ensure_ascii=False) + "\n")
        self.n += 1

    def close(self):
        self.fh.close()


QD = Jsonl("QDRANT_READY/qdrant_chunks.jsonl")
QSEQ = Seq("CHK", 7)


def chunk(content, **kw):
    """One retrieval-ready chunk. Text only - no embeddings are generated (3S)."""
    c = L.nws(content)
    if len(c) < 40:
        return 0
    o = dict((f, "") for f in M.QDRANT_FIELDS)
    for k2, v2 in kw.items():
        if k2 in o and v2 not in (None, ""):
            o[k2] = v2
    o["chunk_id"], o["content"] = QSEQ.next(), c
    QD.add(o)
    return 1


def safe(s):
    return "".join(c if (c.isalnum() or c in "-_") else "_" for c in str(s))[:60]


NORMW = {}            # (fid, sheet) -> (DictWriter, filehandle, canonical names)


def normw(fid, sheet, headers, ent):
    """Per-source normalized copy for 01_SOURCE_DATA/ - source order preserved,
    headers renamed to their canonical column, values normalized (3E/3Q)."""
    k = (fid, sheet)
    if k in NORMW:
        return NORMW[k]
    names, seen = [], {}
    for col in headers:
        cc = M.resolve(fid, col, ent)[0] or L.TRANSFORMS["norm_header"](col)
        if cc in seen:
            seen[cc] += 1
            cc = "%s__%d" % (cc, seen[cc])
        else:
            seen[cc] = 1
        names.append(cc)
    cols = ["canonical_entity", "canonical_entity_id", "source_sheet",
            "source_row"] + names
    stem = os.path.splitext(INV[fid]["original_filename"])[0]
    nm = "%s%s.csv" % (safe(stem), ("__" + safe(sheet)) if sheet else "")
    fh = open(opath("01_SOURCE_DATA/%s/%s"
                    % (FOLDER_OF.get(fid, "OTHER_RELEVANT"), nm)),
              "a" if NORM_APPEND else "w", newline="", encoding="utf-8-sig")
    w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore",
                       quoting=csv.QUOTE_MINIMAL)
    if not NORM_APPEND:
        w.writeheader()
    NORMW[k] = (w, fh, names)
    return NORMW[k]
REVTXT = {"AMBIGUOUS_PLACEHOLDER": ("Cell holds an ambiguous placeholder; it is "
                                   "neither a value nor a clear absence.",
                                   "Inspect the source cell and decide value vs "
                                   "asserted absence."),
          "TRANSFORM_FLAG": ("Normalization flagged this value as unparseable in "
                             "its declared format.", "Confirm the source value; "
                             "the raw form is preserved verbatim.")}
AUXKEYS = {"LAB_SCOPE": ["lab_id", "test_id", "is_id"],
           "FMCS_IS_COVERAGE": ["is_id"], "FMCS_COUNTRY_COVERAGE": [],
           "EXTRACTION_LOG": []}
P2VERDICT = dict((f, DEC.get(f, {}).get("canonical_status", "")) for f in INV)
SUPPRESS_CONF = False
FILESTAT = dict(STATE.get("filestat", {}))
ORPHAN.extend(STATE.get("orphan", []))
AUXBUF.update(STATE.get("auxbuf", {}))
DISPS = ("CANONICAL", "MERGED", "CONFLICT_PRESERVED", "REQUIRES_REVIEW",
         "DUPLICATE_ARCHIVED", "NOT_APPLICABLE")
for fid in sorted(INV):
    if not in_slice(fid):
        continue
    ent = M.ROUTE[fid][0]
    ds = STREAM_ONLY.get(fid, "")
    RLO, RHI = ROWSLICE.get(fid, (0, 0))
    NORM_APPEND = RLO > 1
    ridx = 0
    st = dict((d, 0) for d in DISPS)
    st.update({"rows": 0, "cells": 0, "attr": 0, "rel": 0, "prov": 0, "chunks": 0})
    if RLO > 1:
        st.update(FILESTAT.get(fid, st))
    for sheet, rno, headers, row in rows_of(fid):
        ridx += 1
        if RLO and not (RLO <= ridx <= RHI):
            continue
        st["rows"] += 1
        P = project(fid, ent, headers, row)
        st["cells"] += len(headers)
        npop = len(P["f"]) + len([1 for a in P["a"] if a[1]])
        na = nr = np_ = 0
        if ent in M.ENT:
            ek = ROWKEY.get((fid, sheet, rno))
            key = ek[1] if ek else ""
            eid = MINT[ent].get(key) if key else ""
            lab = LABEL.get((ent, key), "")
            mrow = MASTER_BY_ID.get((ent, eid), {})
            disp, dreason = ROWDISP.get((fid, sheet, rno), ("CANONICAL", ""))
            sides0 = [(ent, eid, lab)]
            for nm, val, base, cls, orig in P["a"]:
                emit_attr(ent, eid, lab, fid, sheet, rno, nm, val, base, cls, orig,
                          mrow.get("source_url", ""))
                na += 1
            for cc, lst in P["f"].items():
                for v, base in lst:
                    emit_prov("FIELD", ent, eid, lab, cc, mrow.get(cc, ""), fid,
                              sheet, rno, base, v, "POPULATED", disp,
                              mrow.get("source_url", ""))
                    np_ += 1
            for cc, raw, cls, base in P["nul"]:
                emit_prov("NULL_SEMANTICS", ent, eid, lab, cc, "", fid, sheet, rno,
                          base, raw, cls, disp)
                np_ += 1
            for nm, v, base in P["prov"]:
                emit_prov("PROVENANCE_ONLY", ent, eid, lab, nm, "", fid, sheet, rno,
                          base, v, "POPULATED", disp)
                np_ += 1
            for rcl, fld, fv in P["rev"]:
                t = (REVTXT["TRANSFORM_FLAG"] if rcl.startswith("TRANSFORM_FLAG")
                     else REVTXT["AMBIGUOUS_PLACEHOLDER"])
                emit_review(ent, eid, lab, fld, fv, rcl, t[0], t[1], fid, sheet, rno,
                            "", P2VERDICT.get(fid, ""))
            r1, a1 = emit_rels(ent, P, fid, sheet, rno, sides0)
            nr += r1
            na += a1
            if ent == "PRODUCT_MANUAL":
                cand = list(P["f"].items()) + [(a[0], [(a[1], a[2])]) for a in P["a"]]
                for nm, lst in cand:
                    cat = M.PM_SECTION_ROUTE.get(nm)
                    if not cat or not lst or not lst[0][0]:
                        continue
                    tv, tb = lst[0][0], lst[0][1]
                    PMS[cat].add({"pm_section_id": PMSEQ.next(), "pm_id": eid,
                                  "manual_title": mrow.get("manual_title", ""),
                                  "manual_version": mrow.get("manual_version", ""),
                                  "is_id": mrow.get("is_id", ""),
                                  "canonical_is_number":
                                      mrow.get("canonical_is_number", ""),
                                  "product_id": mrow.get("product_id", ""),
                                  "product_name": mrow.get("product_name", ""),
                                  "section_category": cat, "source_column": tb[0],
                                  "requirement_text": tv, "text_length": len(tv),
                                  "clause": "", "source_file_id": fid,
                                  "source_file": fname(fid), "source_sheet": sheet,
                                  "source_row": rno,
                                  "source_url": mrow.get("source_url", ""),
                                  "review_flag": ""})
                    st["chunks"] += chunk(
                        tv, document_id=mrow.get("document_id", ""),
                        is_id=mrow.get("is_id", ""),
                        canonical_is_number=mrow.get("canonical_is_number", ""),
                        document_type="PRODUCT_MANUAL",
                        title=mrow.get("manual_title", ""), section=cat,
                        breadcrumb=" > ".join(x for x in
                                              [mrow.get("canonical_is_number", ""),
                                               mrow.get("manual_title", ""), cat,
                                               nm] if x),
                        source_url=mrow.get("source_url", "") or
                        mrow.get("document_url", ""),
                        version=mrow.get("manual_version", ""))
            st[disp] = st.get(disp, 0) + 1
            ceid, dsp = eid, disp
        else:
            pk = pseudo_keys(ent, P)
            sides0 = []
            for t in PSEUDO_ENT.get(ent, ()):
                if t in pk:
                    sides0.append((t, MINT[t].get(pk[t][0]),
                                   LABEL.get((t, pk[t][0]), "")))
            isk = [v for nm, v, b in P["l"] if nm == "__IS__"]
            isid = MINT["STANDARD"].get(isk[0]) if isk else ""
            vals, bases = {}, {}
            for col in headers:
                cc = M.resolve(fid, col, ent)[0]
                v = P["norm"].get(col)
                if v in (None, ""):
                    v = L.nws(P["raw"].get(col, ""))
                if cc and cc not in vals:
                    vals[cc], bases[cc] = v, col
            ceid, dsp = (sides0[0][1] if sides0 else ""), "CANONICAL"
            raw = dict((c, L.nws(P["raw"].get(c, ""))) for c in headers)
            if ds == "RECORD_PROVENANCE":
                sv = raw.get("field_value", "")
                emit_prov("SOURCE_DECLARED", raw.get("entity_type", ""), "",
                          raw.get("record_id", ""), raw.get("field_name", ""), "",
                          fid, sheet, rno, ("field_value", "verbatim",
                                            "PROVENANCE_ONLY", "SOURCE_DECLARED",
                                            "TEXT"), sv, L.nullclass(sv),
                          "CANONICAL", raw.get("source_URL", ""),
                          {"source_title": raw.get("source_title", ""),
                           "source_type": raw.get("source_type", ""),
                           "document_id": raw.get("document_id", ""),
                           "document_title": raw.get("document_title", ""),
                           "page": raw.get("page", ""),
                           "section": raw.get("section", ""),
                           "clause": raw.get("clause", ""),
                           "version": raw.get("version", ""),
                           "effective_date": raw.get("effective_date", ""),
                           "document_hash": raw.get("document_hash", ""),
                           "retrieved_at": raw.get("retrieval_timestamp", ""),
                           "evidence_text": raw.get("evidence_text", ""),
                           "verification_status":
                               raw.get("verification_status", ""),
                           "confidence": raw.get("confidence", "")})
                np_ += 1
                st["chunks"] += chunk(
                    raw.get("evidence_text", ""),
                    document_id=raw.get("document_id", ""),
                    document_type=raw.get("source_type", ""),
                    title=raw.get("document_title", "") or
                    raw.get("source_title", ""), section=raw.get("section", ""),
                    clause=raw.get("clause", ""), page_start=raw.get("page", ""),
                    page_end=raw.get("page", ""),
                    breadcrumb=" > ".join(x for x in [
                        raw.get("source_title", ""), raw.get("section", ""),
                        raw.get("clause", ""), raw.get("field_name", "")] if x),
                    source_url=raw.get("source_URL", ""),
                    version=raw.get("version", ""),
                    effective_date=raw.get("effective_date", ""),
                    sha256=raw.get("document_hash", ""))
            elif ds == "REVIEW_QUEUE":
                emit_review(raw.get("entity_type", ""), "",
                            raw.get("record_id", ""), raw.get("field_name", ""), "",
                            "UNRESOLVED_SOURCE_RECORD", raw.get("reason", ""),
                            raw.get("resolution_needed", ""), fid, sheet, rno,
                            raw.get("attempted_source_URL", ""),
                            P2VERDICT.get(fid, ""))
            elif ds == "CONFLICT_REGISTER":
                va, vb = raw.get("value_a", ""), raw.get("value_b", "")
                rule = classify(va, vb, "TEXT", "", "")
                status, conf, reason = POLICY[rule]
                rv, cv = raw.get("resolved_value", ""), ""
                if rv and (eq(rv, va) or eq(rv, vb)):
                    status, conf, cv = "RESOLVED", "0.90", rv
                    reason = ("Source conflict log declares this resolution and it "
                              "matches one recorded side. Declared rule: %s"
                              % (raw.get("resolution_rule", "") or "n/a"))
                CONF.add({"conflict_id": CSEQ.next(),
                          "entity_type": raw.get("entity_type", ""),
                          "entity_id": "", "entity_label": raw.get("entity_key", ""),
                          "field": raw.get("field_name", ""),
                          "source_a": raw.get("source_a_id", ""),
                          "source_a_file_id": fid, "value_a": va,
                          "source_row_a": rno, "date_a": raw.get("detected_at", ""),
                          "source_b": raw.get("source_b_id", ""),
                          "source_b_file_id": fid, "value_b": vb,
                          "source_row_b": rno, "date_b": raw.get("detected_at", ""),
                          "resolution_status": status,
                          "resolution_rule": "SOURCE_DECLARED+%s" % rule,
                          "resolution_reason": reason, "canonical_value": cv,
                          "confidence": conf,
                          "review_flag": "" if status == "RESOLVED" else "YES"})
                if status != "RESOLVED":
                    emit_review(raw.get("entity_type", ""), "",
                                raw.get("entity_key", ""),
                                raw.get("field_name", ""), "%s | %s" % (va, vb),
                                "SOURCE_DECLARED_CONFLICT",
                                raw.get("notes", "") or reason,
                                "Adjudicate the two source values; both are "
                                "preserved with their source URLs.", fid, sheet,
                                rno, raw.get("source_a_URL", ""),
                                P2VERDICT.get(fid, ""))
                dsp = "CONFLICT_PRESERVED" if status != "RESOLVED" else "CANONICAL"
            else:
                cols, rows = AUXBUF.setdefault(ds, ([], []))
                if not cols:
                    cols.extend(AUXKEYS.get(ds, []))
                r2 = {}
                sd = dict((t, (i, l)) for t, i, l in sides0)
                for t, (i, l) in sd.items():
                    if FKMAP[t] in AUXKEYS.get(ds, []):
                        r2[FKMAP[t]] = i
                    lc = LABCOL.get(t, "")
                    if lc and lc not in vals:
                        r2[lc] = l
                if "is_id" in AUXKEYS.get(ds, []):
                    r2["is_id"] = isid
                for cc, v in vals.items():
                    if cc not in r2:
                        r2[cc] = v
                r2.update({"source_file_id": fid, "source_file": fname(fid),
                           "source_sheet": sheet, "source_row": rno,
                           "record_disposition": "CANONICAL"})
                for k2 in list(r2):
                    if k2 not in cols:
                        cols.append(k2)
                rows.append(r2)
                if sides0:
                    r1, a1 = emit_rels(ent, P, fid, sheet, rno, sides0)
                    nr += r1
                    na += a1
                if "TEST" in sd and "LABORATORY" in sd:
                    nr += emit_rel("TEST_LAB_MAPPING",
                                   [("TEST",) + sd["TEST"],
                                    ("LABORATORY",) + sd["LABORATORY"]],
                                   "TESTED_AT", ds, "lab_scope_row",
                                   vals.get("test_name", "") or "", fid, sheet, rno,
                                   {"capability": vals.get("capability", ""),
                                    "testing_charge": vals.get("testing_charge", "")})
                for cc, raw2, cls, base in P["nul"]:
                    emit_prov("NULL_SEMANTICS", ent, ceid, "", cc, "", fid, sheet,
                              rno, base, raw2, cls, dsp)
                    np_ += 1
        elab = sides0[0][2] if sides0 else ""
        st[dsp] = st.get(dsp, 0) + 1
        st["attr"] += na
        st["rel"] += nr
        st["prov"] += np_
        w, _fh, names = normw(fid, sheet, headers, ent)
        nrow = {"canonical_entity": ent, "canonical_entity_id": ceid,
                "source_sheet": sheet, "source_row": rno}
        for i, col in enumerate(headers):
            v = P["norm"].get(col)
            if v in (None, ""):
                v = L.nws(P["raw"].get(col, ""))
            nrow[names[i]] = v
        w.writerow(nrow)
        DLA.add({"source_file_id": fid, "source_file": fname(fid),
                 "source_sheet": sheet, "source_row": rno, "route_target": ent,
                 "entity_type": ent if ent in M.ENT else
                 (sides0[0][0] if sides0 else ""), "entity_id": ceid,
                 "entity_label": elab, "record_disposition": dsp,
                 "disposition_reason": ROWDISP.get((fid, sheet, rno), ("", ""))[1]
                 or ("Stream-only source record materialized verbatim into %s."
                     % ds if ds else ""),
                 "fields_projected": len(headers), "fields_populated": npop,
                 "attributes_written": na, "relationships_written": nr,
                 "provenance_rows": np_})
    FILESTAT[fid] = st
    p("    B %s rows %6d  attr %7d  rel %6d  prov %8d  chunks %5d"
      % (fid, st["rows"], ASEQ.n, sum(RELS[x].n for x in RELS), PSEQ.n, QD.n))
for _k in NORMW:
    NORMW[_k][1].close()
p("stage 4  pass B: attributes %d  relationships %d  provenance %d  chunks %d  "
  "reviews %d  orphans %d"
  % (ASEQ.n, sum(RELS[n].n for n in RELS), PSEQ.n, QD.n, RVSEQ.n, len(ORPHAN)))
SEQOUT = {"seq:ATT": ASEQ.n, "seq:PRV": PSEQ.n, "seq:RVW": RVSEQ.n, "seq:CFL": CSEQ.n,
          "seq:CHK": QSEQ.n,
          "stream:QDRANT_READY/qdrant_chunks.jsonl": QD.n}
for _n, _q in RSEQ.items():
    SEQOUT["seq:" + _q.p] = _q.n
for _s in [ATTR, PROV, RQ, CONF, DLA] + list(RELS.values()) + list(PMS.values()):
    SEQOUT["stream:" + _s.rel] = _s.n
if not FINAL:
    for _s in [ATTR, PROV, RQ, CONF, DLA] + list(RELS.values()) + list(PMS.values()):
        _s.close()
    QD.close()
    for _r in list(SEQOUT):
        if _r.startswith("stream:"):
            SEQOUT["off:" + _r[7:]] = os.path.getsize(opath(_r[7:]))
    with open(STATEP + ".tmp", "wb") as _fh:
        pickle.dump({"seq": SEQOUT, "filestat": FILESTAT, "orphan": ORPHAN,
                     "auxbuf": AUXBUF}, _fh, protocol=4)
    os.replace(STATEP + ".tmp", STATEP)
    p("SLICE %s DONE - state checkpointed, stages 5-13 deferred" % SLICE)
    sys.exit(0)
# ------------------------------------- stage 5 master-derived chunks + reviews
p("[5] master-derived retrieval chunks + master review queue")
CHUNKSRC = {
    "STANDARD": ("IS_STANDARD", "title", "official_url",
                 ["title", "title_vernacular", "standard_scope", "part_section_label",
                  "product_category", "technical_committee", "standard_status",
                  "mandatory_voluntary", "certification_type", "superseded_standard",
                  "superseding_standard", "degree_of_equivalence"]),
    "QCO": ("QCO", "qco_name", "official_document_url",
            ["qco_name", "qco_number", "qco_product_text", "qco_scope",
             "qco_exclusions", "qco_exemptions", "qco_amendments", "qco_extensions",
             "qco_deferments", "qco_supersession", "mandatory_status", "qco_status",
             "ministry", "qco_schemes_text"]),
    "SCHEME": ("SCHEME", "scheme_name", "document_url",
               ["scheme_name", "scheme_code", "scheme_type", "certification_scope",
                "certification_requirements", "applicability",
                "application_procedure", "fee_structure", "inspection_testing_norm",
                "fmcs_requirements", "mandatory_voluntary"]),
    "PRODUCT": ("PRODUCT", "product_name", "source_url",
                ["product_name", "alternate_names", "product_description",
                 "product_category", "product_subcategory", "keywords",
                 "certification_scheme_to_store"]),
    "FAQ": ("FAQ", "question", "source_url",
            ["question", "answer", "faq_category", "related_is_text",
             "related_scheme_text", "document_reference"]),
    "LEGAL": ("LEGAL", "title", "document_url",
              ["title", "legal_instrument_type", "instrument_number", "subject",
               "implementation_instructions", "mandatory_status", "metal", "fineness",
               "geographical_applicability", "district_phase", "amendment",
               "exemption", "supersession", "issuing_authority"]),
    "NOTIFICATION": ("NOTIFICATION", "title", "document_url",
                     ["title", "notification_number", "notification_type", "subject",
                      "notification_category", "related_is_text", "related_qco_text",
                      "related_amendment_text", "ministry"]),
    "TEST": ("TEST_METHOD", "test_name", "source_url",
             ["test_name", "test_parameter", "test_method", "test_method_standard",
              "clause", "acceptance_criteria", "sample_size", "sampling_frequency",
              "test_frequency", "required_equipment", "laboratory_requirement",
              "rejection_handling", "remarks"]),
    "LABORATORY": ("LABORATORY", "lab_name", "scope_url",
                   ["lab_name", "lab_code", "lab_type", "address", "city", "state",
                    "recognition_status", "validity", "accreditation_validity",
                    "contact_details"]),
    "HALLMARKING": ("HALLMARKING_CENTRE", "centre_name", "source_url",
                    ["centre_name", "centre_code", "hallmarking_entity_type",
                     "address", "city", "state", "region", "centre_type",
                     "recognition_status", "validity", "hallmarking_scope",
                     "services"]),
    "FMCS": ("FMCS_LICENCE", "manufacturer_name", "source_url",
             ["manufacturer_name", "country", "factory", "cml_licence_no",
              "licence_status", "validity_date", "fmcs_product", "variety_brand",
              "fmcs_eligibility", "machinery_requirements", "testing_facilities",
              "competent_personnel", "air_requirements", "application_requirements",
              "fees", "fmcs_documents"]),
    "DOCUMENT": ("DOCUMENT", "title", "source_url",
                 ["title", "document_type", "version", "license_access_restriction",
                  "access_type", "parser_status"])}
MCHUNK = 0
for ent in M.ENT:
    spec = CHUNKSRC.get(ent)
    idc = IDCOL[ent]
    for row in MASTERS[ent]:
        if row.get("review_flag") == "YES":
            emit_review(ent, row.get(idc, ""), row.get(LABCOL.get(ent, ""), ""),
                        row.get("conflict_fields", ""), "",
                        "MERGE_CONFLICT_PRESERVED",
                        row.get("review_reason", "") or
                        "Sources disagree on one or more fields; both values are "
                        "preserved in CONFLICT_STATUS.csv.",
                        "Adjudicate the preserved values and set the canonical one.",
                        (row.get("source_file_ids", "") or "").split(";")[0],
                        (row.get("source_sheets", "") or "").split(";")[0],
                        (row.get("source_rows", "") or "").split(";")[0],
                        row.get("source_url", ""),
                        P2VERDICT.get((row.get("source_file_ids", "") or
                                       "").split(";")[0], ""))
        if not spec:
            continue
        dt, tf, uf, flds = spec
        body = "; ".join("%s: %s" % (f.replace("_", " "), row[f])
                         for f in flds if row.get(f))
        MCHUNK += chunk(body, document_id=row.get("document_id", ""),
                        is_id=row.get("is_id", "") or
                        (row.get(idc, "") if ent == "STANDARD" else ""),
                        canonical_is_number=row.get("canonical_is_number", ""),
                        document_type=dt, title=row.get(tf, ""),
                        section=row.get("faq_category", "") or
                        row.get("product_category", ""),
                        clause=row.get("clause", ""),
                        breadcrumb=" > ".join(x for x in [
                            dt, row.get("canonical_is_number", ""),
                            row.get(tf, "")] if x),
                        source_url=row.get(uf, "") or row.get("source_url", ""),
                        version=row.get("version", "") or
                        row.get("revision", ""),
                        effective_date=row.get("effective_date", "") or
                        row.get("publication_date", ""),
                        sha256=row.get("sha256", ""))
p("    master chunks %d   total chunks %d   review rows %d" % (MCHUNK, QD.n, RVSEQ.n))
# --------------------------------------------- stage 6 aux / operational tables
p("[6] aux + operational datasets")
for ds in sorted(AUXBUF):
    cols, rows = AUXBUF[ds]
    rel = AUXPATH.get(ds, "00_MASTER/%s.csv" % ds)
    L.wcsv(opath(rel), rows, cols)
    p("    %-24s %-44s %6d rows x %d cols" % (ds, rel, len(rows), len(cols)))
# --------------------------- stage 7 non-tabular sources -> DOCUMENT registry
p("[7] non-tabular sources -> DOCUMENT registry")
DCOLS = M.MASTER_COLS["DOCUMENT"]
NT = 0
for fid in sorted(INV):
    if FILESTAT.get(fid, {}).get("rows"):
        continue
    iv = INV[fid]
    did = "DOC-%05d" % (len(MINT["DOCUMENT"]) + 1 + NT)
    NT += 1
    row = dict((c, "") for c in DCOLS)
    row.update({"document_id": did,
                "document_type": (iv.get("extension", "") or "").upper(),
                "title": os.path.splitext(iv["original_filename"])[0],
                "local_path": iv.get("exact_path", ""),
                "sha256": iv.get("sha256", ""),
                "bytes": iv.get("file_size_bytes", ""),
                "content_type": iv.get("mime_type", ""),
                "last_modified": iv.get("modified_time_utc", ""),
                "retrieved_at": iv.get("created_time_utc", ""),
                "access_type": "LOCAL_UPLOAD",
                "parser_status": iv.get("analysis_status", ""),
                "dedup_status": DEC.get(fid, {}).get("canonical_status", ""),
                "source_reference_label": iv["original_filename"],
                "source_file_count": "1", "source_file_ids": fid,
                "source_files": iv["original_filename"], "source_sheets": "",
                "source_rows": "", "record_disposition": "CANONICAL",
                "conflict_count": "0", "conflict_fields": "", "review_flag": "",
                "review_reason": ""})
    np2 = len([1 for c in DCOLS if row.get(c) not in (None, "")])
    row["populated_field_count"] = np2
    row["completeness_pct"] = "%.1f" % (100.0 * np2 / len(DCOLS))
    MASTERS["DOCUMENT"].append(row)
    MASTER_BY_ID[("DOCUMENT", did)] = row
    DLA.add({"source_file_id": fid, "source_file": iv["original_filename"],
             "source_sheet": "", "source_row": "", "route_target": "DOCUMENT",
             "entity_type": "DOCUMENT", "entity_id": did,
             "entity_label": row["title"], "record_disposition": "CANONICAL",
             "disposition_reason": "Non-tabular source registered as a DOCUMENT "
                                   "record from file metadata; no rows to project.",
             "fields_projected": 0, "fields_populated": np2,
             "attributes_written": 0, "relationships_written": 0,
             "provenance_rows": 1})
    FILESTAT[fid] = {"rows": 0, "cells": 0, "attr": 0, "rel": 0, "prov": 1,
                     "chunks": 0, "CANONICAL": 1}
if NT:
    L.wcsv(opath("00_MASTER/DOCUMENT_MASTER.csv"), MASTERS["DOCUMENT"], DCOLS)
p("    non-tabular sources registered %d   DOCUMENT rows now %d"
  % (NT, len(MASTERS["DOCUMENT"])))
# ------------------------------- stage 8 import the 3,305 Phase-2 conflict rows
p("[8] importing PHASE 2 CONFLICTS.csv into the canonical conflict register")
FIDBY = {}
for _f, _iv in INV.items():
    FIDBY.setdefault(_iv["original_filename"], _f)
KEYENT = {"is_number": "STANDARD", "is_numbers": "STANDARD",
          "related_is_numbers": "STANDARD", "product": "PRODUCT",
          "product_name": "PRODUCT", "centre_id": "HALLMARKING",
          "lab_name": "LABORATORY"}
P2STAT = {}
for cr in L.rcsv(os.path.join(SRC, "BIS_SIH26107_DATA/01_ANALYSIS/CONFLICTS.csv")):
    fa, fb = FIDBY.get(cr["file_a"], ""), FIDBY.get(cr["file_b"], "")
    col, va, vb = cr["conflicting_column"], cr["value_a"], cr["value_b"]
    kent = KEYENT.get(cr["record_key_column"], "")
    eid, elab = "", cr["record_key_value"]
    if kent:
        kk, kl = ckey(kent, cr["record_key_value"])
        eid = MINT[kent].get(kk) if kk else ""
        elab = LABEL.get((kent, kk), "") or kl or elab
    ca = M.resolve(fa, col, M.ROUTE[fa][0])[0] if fa else ""
    cb = M.resolve(fb, col, M.ROUTE[fb][0])[0] if fb else ""
    if ca and cb and ca != cb:
        rule = "HOMONYM_NOT_A_CONFLICT"
    else:
        rule = classify(va, vb, "TEXT", fa, fb)
    status, conf, reason = POLICY[rule]
    cv = winner(rule, va, vb, fa, fb) if status == "RESOLVED" else ""
    if rule == "HOMONYM_NOT_A_CONFLICT":
        cv = ""
        reason = ("%s Source column '%s' maps to '%s' in %s and to '%s' in %s, so "
                  "the two values describe different canonical fields."
                  % (reason, col, ca, cr["file_a"], cb, cr["file_b"]))
    reason = ("%s [PHASE2: %s / %s / similarity %s / status %s]"
              % (reason, cr["conflict_type"], cr["value_relationship"],
                 cr["value_similarity"], cr["resolution_status"]))
    P2STAT[status] = P2STAT.get(status, 0) + 1
    CONF.add({"conflict_id": CSEQ.next(), "entity_type": kent, "entity_id": eid,
              "entity_label": elab, "field": ca or col,
              "source_a": cr["file_a"], "source_a_file_id": fa, "value_a": va,
              "source_row_a": cr["source_row_a"], "date_a": "",
              "source_b": cr["file_b"], "source_b_file_id": fb, "value_b": vb,
              "source_row_b": cr["source_row_b"], "date_b": "",
              "resolution_status": status,
              "resolution_rule": "%s (phase2 %s)" % (rule, cr["conflict_id"]),
              "resolution_reason": reason, "canonical_value": cv,
              "confidence": conf,
              "review_flag": "" if status == "RESOLVED" else "YES"})
    if status == "REQUIRES_REVIEW":
        emit_review(kent, eid, elab, ca or col, "%s | %s" % (va, vb),
                    "PHASE2_CONFLICT_REQUIRES_REVIEW", reason,
                    "Adjudicate both preserved values; neither may be discarded.",
                    fa, cr["sheet_a"], cr["source_row_a"], "",
                    P2VERDICT.get(fa, ""))
p("    imported %d phase-2 conflicts -> %s" % (sum(P2STAT.values()), P2STAT))
# ------------------------------------------------- stage 9 provenance registers
p("[9] source-file + document provenance")
SFP = []
for fid in sorted(INV):
    iv, st = INV[fid], FILESTAT.get(fid, {})
    d = DEC.get(fid, {})
    acc = sum(st.get(k, 0) for k in DISPS)
    SFP.append({"source_file_id": fid, "original_filename": iv["original_filename"],
                "extension": iv.get("extension", ""),
                "exact_path": iv.get("exact_path", ""),
                "source_location": iv.get("source_location", ""),
                "sha256": iv.get("sha256", ""),
                "file_size_bytes": iv.get("file_size_bytes", ""),
                "encoding": iv.get("encoding", ""),
                "sheet_name": iv.get("candidate_topic", ""),
                "sheet_count": iv.get("sheet_count", ""),
                "total_data_rows": iv.get("total_data_rows", ""),
                "total_columns": iv.get("total_columns", ""),
                "canonical_target": M.ROUTE[fid][0],
                "canonical_dataset": M.ROUTE[fid][1],
                "candidate_topic": M.ROUTE[fid][2],
                "rows_read": st.get("rows", 0), "cells_projected": st.get("cells", 0),
                "records_canonical": st.get("CANONICAL", 0),
                "records_merged": st.get("MERGED", 0),
                "records_conflict_preserved": st.get("CONFLICT_PRESERVED", 0),
                "records_requires_review": st.get("REQUIRES_REVIEW", 0),
                "records_not_applicable": st.get("NOT_APPLICABLE", 0),
                "records_accounted": acc,
                "retention_decision": d.get("canonical_status", ""),
                "archive_path": ("99_RAW/ARCHIVE_DUPLICATES/%s"
                                 % iv["original_filename"]
                                 if fid in M.ARCHIVE_AFTER_VALIDATION else ""),
                "structural_issue": iv.get("structural_issue", ""),
                "analysis_status": iv.get("analysis_status", ""),
                "modified_time_utc": iv.get("modified_time_utc", ""),
                "notes": "%s | attributes %d, relationships %d, provenance %d, "
                         "chunks %d" % (d.get("decision_reason", ""),
                                        st.get("attr", 0), st.get("rel", 0),
                                        st.get("prov", 0), st.get("chunks", 0))})
L.wcsv(opath("91_PROVENANCE/SOURCE_FILE_PROVENANCE.csv"), SFP,
       M.AUX_COLS["SOURCE_FILE_PROVENANCE"])
DOCP = []
for row in MASTERS["DOCUMENT"]:
    DOCP.append({"document_provenance_id": "DPR-%05d" % (len(DOCP) + 1),
                 "document_id": row.get("document_id", ""),
                 "document_type": row.get("document_type", ""),
                 "title": row.get("title", ""), "is_id": row.get("is_id", ""),
                 "canonical_is_number": row.get("canonical_is_number", ""),
                 "source_url": row.get("source_url", ""),
                 "download_url": row.get("download_url", ""),
                 "local_path": row.get("local_path", ""),
                 "sha256": row.get("sha256", ""),
                 "page_count": row.get("page_count", ""),
                 "http_status": row.get("http_status", ""),
                 "content_type": row.get("content_type", ""),
                 "bytes": row.get("bytes", ""),
                 "last_modified": row.get("last_modified", ""),
                 "access_type": row.get("access_type", ""),
                 "parser_status": row.get("parser_status", ""),
                 "dedup_status": row.get("dedup_status", ""),
                 "retrieved_at": row.get("retrieved_at", ""),
                 "chunk_count": "", "evidence_row_count": "",
                 "source_file_id": (row.get("source_file_ids", "") or
                                    "").split(";")[0],
                 "source_file": (row.get("source_files", "") or "").split(";")[0],
                 "source_sheet": (row.get("source_sheets", "") or "").split(";")[0],
                 "source_row": (row.get("source_rows", "") or "").split(";")[0],
                 "notes": row.get("license_access_restriction", "")})
L.wcsv(opath("91_PROVENANCE/DOCUMENT_PROVENANCE.csv"), DOCP,
       M.AUX_COLS["DOCUMENT_PROVENANCE"])
p("    SOURCE_FILE_PROVENANCE %d rows   DOCUMENT_PROVENANCE %d rows"
  % (len(SFP), len(DOCP)))
# ------------------------------------- stage 10 close streams + orphan register
ORPHAN_COLS = ["relationship_table", "relationship_type", "unmatched_reference",
               "evidence_column", "evidence_value", "resolved_sides",
               "source_file_id", "source_file", "source_sheet", "source_row",
               "reason"]
L.wcsv(opath("92_VALIDATION/ORPHAN_RECORDS.csv"), ORPHAN, ORPHAN_COLS)
UNMATCHED = len(ORPHAN)
RELCOUNT = dict((n, RELS[n].n) for n in RELS)
PMCOUNT = dict((c, PMS[c].n) for c in PMS)
NCONF, NATTR, NPROV, NRQ, NDLA, NCHUNK = (CONF.n, ATTR.n, PROV.n, RQ.n, DLA.n, QD.n)
for _s in [ATTR, PROV, RQ, CONF, DLA] + list(RELS.values()) + list(PMS.values()):
    _s.close()
QD.close()
p("[10] streams closed: relationships %d rows in %d tables, PM sections %d, "
  "conflicts %d, orphans %d"
  % (sum(RELCOUNT.values()), len(RELCOUNT), sum(PMCOUNT.values()), NCONF, UNMATCHED))
# ------------------------------------------- stage 11 IS_COMPLETE_MASTER.xlsx
p("[11] 00_MASTER/IS_COMPLETE_MASTER.xlsx  (one logical row per canonical IS)")
ISAGG = {}            # is_id -> {aspect: [labels]}
ASPECT = [("products", "IS_PRODUCT_MAPPING", "product_name"),
          ("qcos", "IS_QCO_MAPPING", "qco_number"),
          ("schemes", "IS_SCHEME_MAPPING", "scheme_name"),
          ("documents", "IS_DOCUMENT_MAPPING", "title"),
          ("tests", "IS_TEST_MAPPING", "test_name"),
          ("laboratories", "IS_LAB_TEST_MAPPING", "lab_name"),
          ("lab_tests", "IS_LAB_TEST_MAPPING", "test_name"),
          ("related_standards", "IS_RELATED_IS", "related_canonical_is_number"),
          ("amendments", "IS_AMENDMENTS", "amendment_reference"),
          ("product_manuals", "IS_PRODUCT_MANUAL_MAPPING", "manual_title"),
          ("fmcs_licences", "IS_FMCS_MAPPING", "manufacturer_name"),
          ("other_entities", "IS_ENTITY_MAPPING", "entity_label")]
for asp, tbl, lc in ASPECT:
    pth = opath("90_RELATIONSHIPS/%s" % M.REL_BY_NAME[tbl][1])
    if not os.path.exists(pth):
        continue
    for rr in L.rcsv(pth):
        k = rr.get("is_id", "")
        if not k:
            continue
        v = L.nws(rr.get(lc, ""))
        if v:
            ISAGG.setdefault(k, {}).setdefault(asp, []).append(v)
ISCORE = ["is_id", "canonical_is_number", "display_is_number",
          "raw_is_number_variants", "standard_number", "standard_year",
          "part_number", "section_number", "amendment_reference", "iec_reference",
          "is_iec_flag", "title", "standard_scope", "revision", "publication_date",
          "standard_status", "mandatory_voluntary", "certification_type",
          "product_category", "technical_committee", "superseded_standard",
          "superseding_standard", "official_url", "source_url",
          "source_file_count", "source_files", "record_disposition",
          "conflict_count", "conflict_fields", "review_flag",
          "populated_field_count", "completeness_pct"]
ISCOLS = list(ISCORE)
for asp, _t, _c in ASPECT:
    if asp + "_count" not in ISCOLS:
        ISCOLS += [asp + "_count", asp + "_list"]


def joinlist(vals, cap=8000):
    seen, out = set(), []
    for v in vals:
        k = v.lower()
        if k not in seen:
            seen.add(k)
            out.append(v)
    s = "; ".join(out)
    if len(s) > cap:
        keep, n = [], 0
        for v in out:
            if n + len(v) + 2 > cap:
                break
            keep.append(v)
            n += len(v) + 2
        s = "; ".join(keep) + " ... (+%d more, see 90_RELATIONSHIPS)" % (
            len(out) - len(keep))
    return s, len(out)


wb = xlsxwriter.Workbook(opath("00_MASTER/IS_COMPLETE_MASTER.xlsx"),
                         {"constant_memory": True})
fh_ = wb.add_format({"font_name": "Arial", "font_size": 10, "bold": True,
                     "bg_color": "#1F3864", "font_color": "#FFFFFF",
                     "align": "left", "valign": "vcenter", "text_wrap": True,
                     "border": 1, "border_color": "#BFBFBF"})
fb_ = wb.add_format({"font_name": "Arial", "font_size": 10, "valign": "top",
                     "text_wrap": False})
fn_ = wb.add_format({"font_name": "Arial", "font_size": 10, "valign": "top",
                     "align": "center"})
ws = wb.add_worksheet("IS_COMPLETE_MASTER")
ws.freeze_panes(1, 2)
ws.set_row(0, 30)
for j, c in enumerate(ISCOLS):
    ws.write(0, j, c, fh_)
    ws.set_column(j, j, 34 if c.endswith("_list") else
                  (10 if c.endswith(("_count", "_pct", "_flag")) else 20))
ws.autofilter(0, 0, max(len(MASTERS["STANDARD"]), 1), len(ISCOLS) - 1)
for i, row in enumerate(sorted(MASTERS["STANDARD"],
                              key=lambda r: r.get("is_id", "")), start=1):
    agg = ISAGG.get(row.get("is_id", ""), {})
    for j, c in enumerate(ISCOLS):
        if c.endswith("_list"):
            s, _n = joinlist(agg.get(c[:-5], []))
            ws.write_string(i, j, s, fb_)
        elif c.endswith("_count") and c[:-6] in dict((a[0], 1) for a in ASPECT):
            _s, n = joinlist(agg.get(c[:-6], []))
            ws.write_number(i, j, n, fn_)
        else:
            v = row.get(c, "")
            ws.write_string(i, j, "" if v is None else str(v),
                            fn_ if c.endswith(("_count", "_pct")) else fb_)
wl = wb.add_worksheet("LEGEND")
wl.set_column(0, 0, 34)
wl.set_column(1, 1, 112)
wl.write(0, 0, "column", fh_)
wl.write(0, 1, "meaning", fh_)
LEG = [("is_id", "Stable canonical identifier for one Indian Standard. IS 1489 "
                 "(Part 1) and (Part 2) are separate standards with separate ids."),
       ("canonical_is_number", "Normalized comparison key. display_is_number is the "
                               "human form; raw_is_number_variants keeps every "
                               "spelling found in the sources."),
       ("<aspect>_count", "Number of DISTINCT related records in the matching "
                          "90_RELATIONSHIPS table. This is the authoritative "
                          "cardinality."),
       ("<aspect>_list", "Human-readable labels of those related records, "
                         "semicolon separated, truncated with an explicit '(+N "
                         "more)' marker. It is a convenience view only - the "
                         "relationship tables in 90_RELATIONSHIPS are normalized "
                         "and are the join surface for SQL."),
       ("record_disposition", "CANONICAL / MERGED / CONFLICT_PRESERVED / "
                              "REQUIRES_REVIEW - see 92_VALIDATION/"
                              "DATA_LOSS_AUDIT.csv for every source row."),
       ("conflict_count", "Fields where sources disagreed. Both values are kept in "
                          "92_VALIDATION/CONFLICT_STATUS.csv; nothing was "
                          "overwritten."),
       ("empty cell", "No value was established by the uploaded data. Nothing was "
                      "invented. The reason is recorded per field in "
                      "91_PROVENANCE/RECORD_PROVENANCE.csv (null_class, "
                      "missing_reason).")]
for i, (a, b) in enumerate(LEG, start=1):
    wl.write_string(i, 0, a, fb_)
    wl.write_string(i, 1, b, wb.add_format({"font_name": "Arial", "font_size": 10,
                                            "text_wrap": True, "valign": "top"}))
wb.close()
p("    IS_COMPLETE_MASTER.xlsx  %d IS rows x %d columns  (%d aspects aggregated)"
  % (len(MASTERS["STANDARD"]), len(ISCOLS), len(ASPECT)))
# ------------------------------------------------- stage 12 POSTGRES_READY/
p("[12] POSTGRES_READY/  (DDL + loader over the canonical CSVs, no duplication)")
INTCOL = set(["value_length", "text_length", "source_row", "source_row_a",
              "source_row_b", "page", "page_start", "page_end", "sheet_count",
              "total_data_rows", "total_columns", "rows_read", "cells_projected",
              "records_canonical", "records_merged", "records_conflict_preserved",
              "records_requires_review", "records_not_applicable",
              "records_accounted", "source_file_count", "conflict_count",
              "populated_field_count", "fields_projected", "fields_populated",
              "attributes_written", "relationships_written", "provenance_rows",
              "file_size_bytes", "bytes", "page_count", "chunk_count",
              "evidence_row_count", "standard_year"])
NUMCOL = set(["confidence", "completeness_pct", "value_similarity"])
TABLES = []                     # (table, rel_path, cols, pk, [(fkcol, reftable)])
for ent in M.ENT:
    TABLES.append((dict(M.MASTER)[ent].replace(".csv", "").lower(),
                   "../00_MASTER/%s" % dict(M.MASTER)[ent],
                   M.MASTER_COLS[ent], IDCOL[ent], []))
MASTERTAB = dict((IDCOL[e], dict(M.MASTER)[e].replace(".csv", "").lower())
                 for e in M.ENT)
REFPK = dict((v, k) for k, v in MASTERTAB.items())
MASTERTAB["manual_id"] = MASTERTAB["pm_id"]
MASTERTAB["centre_id"] = MASTERTAB["hm_id"]
MASTERTAB["related_is_id"] = MASTERTAB["is_id"]
for n in M.REL_BY_NAME:
    fks = [(c, MASTERTAB[c]) for c in M.REL_BY_NAME[n][4] if c in MASTERTAB]
    TABLES.append((n.lower(), "../90_RELATIONSHIPS/%s" % M.REL_BY_NAME[n][1],
                   M.REL_COLS[n], "relationship_id", fks))
for c in PMCAT:
    TABLES.append(("product_manual_%s" % c.lower(),
                   "../00_MASTER/PRODUCT_MANUAL_%s.csv" % c, M.PM_SECTION_COLS,
                   "pm_section_id", [("pm_id", MASTERTAB["pm_id"])]))
for nm, cols, pk, rel in (
        ("entity_attributes", M.AUX_COLS["ENTITY_ATTRIBUTES"], "attribute_id",
         "../00_MASTER/ENTITY_ATTRIBUTES.csv"),
        ("record_provenance", M.AUX_COLS["RECORD_PROVENANCE"], "provenance_id",
         "../91_PROVENANCE/RECORD_PROVENANCE.csv"),
        ("source_file_provenance", M.AUX_COLS["SOURCE_FILE_PROVENANCE"],
         "source_file_id", "../91_PROVENANCE/SOURCE_FILE_PROVENANCE.csv"),
        ("document_provenance", M.AUX_COLS["DOCUMENT_PROVENANCE"],
         "document_provenance_id", "../91_PROVENANCE/DOCUMENT_PROVENANCE.csv"),
        ("conflict_status", M.CONFLICT_COLS, "conflict_id",
         "../92_VALIDATION/CONFLICT_STATUS.csv"),
        ("requires_review", M.AUX_COLS["REVIEW_QUEUE"], "review_id",
         "../92_VALIDATION/REQUIRES_REVIEW.csv"),
        ("data_loss_audit", DLA_COLS, "", "../92_VALIDATION/DATA_LOSS_AUDIT.csv"),
        ("orphan_records", ORPHAN_COLS, "",
         "../92_VALIDATION/ORPHAN_RECORDS.csv")):
    TABLES.append((nm, rel, cols, pk, []))
for ds in sorted(AUXBUF):
    TABLES.append((ds.lower(), "../%s" % AUXPATH.get(ds, "00_MASTER/%s.csv" % ds),
                   AUXBUF[ds][0], "", []))
def sqlt(c):
    if c in INTCOL:
        return "integer"
    if c in NUMCOL:
        return "numeric"
    return "text"


ddl = ["-- BIS SIH26107 - PHASE 3 canonical layer, PostgreSQL DDL",
       "-- Generated by p3_build.py. Every table maps 1:1 to a canonical CSV that",
       "-- stays in place under BIS_SIH26107_DATA/; nothing is duplicated here, so",
       "-- there is exactly one source of truth per table.",
       "-- Empty CSV fields load as NULL. A NULL means 'not established by the",
       "-- uploaded data' - the reason is in record_provenance.missing_reason.",
       "CREATE SCHEMA IF NOT EXISTS bis;", "SET search_path TO bis, public;", ""]
load = ["-- BIS SIH26107 - PHASE 3 loader. Run with psql from POSTGRES_READY/:",
        "--   psql -v ON_ERROR_STOP=1 -f DDL.sql -f LOAD.sql",
        "SET search_path TO bis, public;", ""]
alters = ["", "-- Referential integrity is asserted only after the data is loaded,",
          "-- so a failure here means a real orphan, not a load-order problem.",
          "-- 92_VALIDATION/ORPHAN_RECORDS.csv lists every reference that could not",
          "-- be resolved; those columns are NULL and therefore FK-legal.", ""]
MAN = []
for tab, rel, cols, pk, fks in TABLES:
    ddl.append("DROP TABLE IF EXISTS %s CASCADE;" % tab)
    body = ["    %-34s %s" % (c, sqlt(c)) for c in cols]
    if pk and pk in cols:
        body[cols.index(pk)] = "    %-34s %s PRIMARY KEY" % (pk, sqlt(pk))
    ddl.append("CREATE TABLE %s (\n%s\n);" % (tab, ",\n".join(body)))
    ddl.append("")
    load.append("\\copy %s (%s) FROM '%s' WITH (FORMAT csv, HEADER true, NULL '', "
                "ENCODING 'UTF8');" % (tab, ", ".join(cols), rel))
    for c, ref in fks:
        alters.append("ALTER TABLE %s ADD CONSTRAINT fk_%s_%s FOREIGN KEY (%s) "
                      "REFERENCES %s (%s);"
                      % (tab, tab, c, c, ref, REFPK[ref]))
    MAN.append({"table_name": tab, "csv_path": rel.replace("../", ""),
                "column_count": len(cols), "primary_key": pk,
                "foreign_keys": ";".join("%s->%s" % (c, r) for c, r in fks),
                "integer_columns": ";".join(c for c in cols if c in INTCOL),
                "numeric_columns": ";".join(c for c in cols if c in NUMCOL)})
for idx in ("CREATE INDEX ix_attr_entity ON entity_attributes (entity_type, entity_id);",
            "CREATE INDEX ix_prov_entity ON record_provenance (entity_type, entity_id);",
            "CREATE INDEX ix_prov_file ON record_provenance (source_file_id);",
            "CREATE INDEX ix_conf_entity ON conflict_status (entity_type, entity_id);",
            "CREATE INDEX ix_dla_file ON data_loss_audit (source_file_id);",
            "CREATE INDEX ix_std_num ON is_master (canonical_is_number);"):
    alters.append(idx)
open(opath("POSTGRES_READY/DDL.sql"), "w", encoding="utf-8").write("\n".join(ddl))
open(opath("POSTGRES_READY/LOAD.sql"), "w",
     encoding="utf-8").write("\n".join(load + alters) + "\n")
L.wcsv(opath("POSTGRES_READY/TABLE_MANIFEST.csv"), MAN,
       ["table_name", "csv_path", "column_count", "primary_key", "foreign_keys",
        "integer_columns", "numeric_columns"])
p("    %d tables, DDL.sql + LOAD.sql + TABLE_MANIFEST.csv written" % len(TABLES))
# ------------------------------------- stage 13 QDRANT_READY notes + build stats
p("[13] QDRANT_READY/ payload schema + build statistics")
QMEAN = {"chunk_id": "Stable chunk identifier (CHK-nnnnnnn).",
         "document_id": "FK to document_master.document_id when the chunk came from "
                        "a registered document.",
         "is_id": "FK to is_master.is_id - the standard the chunk is about.",
         "canonical_is_number": "Normalized IS number, for filtered retrieval.",
         "document_type": "IS_STANDARD / QCO / SCHEME / PRODUCT_MANUAL / FAQ / LEGAL "
                          "/ NOTIFICATION / TEST_METHOD / LABORATORY / "
                          "HALLMARKING_CENTRE / FMCS_LICENCE / PRODUCT / DOCUMENT "
                          "or the source-declared type for evidence chunks.",
         "title": "Human title of the parent record.",
         "section": "Section or category label (PM section category, FAQ category, "
                    "product category, or the source-declared section).",
         "clause": "Clause reference when the source stated one.",
         "page_start": "First page, when the source stated one.",
         "page_end": "Last page, when the source stated one.",
         "breadcrumb": "Hierarchical path for display and re-ranking.",
         "content": "The retrievable text. Minimum 40 characters; assembled only "
                    "from populated source fields - no text was invented.",
         "source_url": "Citable URL as recorded in the sources.",
         "version": "Version/revision as recorded.",
         "effective_date": "Effective or publication date as recorded.",
         "sha256": "Hash of the parent document when known."}
L.wcsv(opath("QDRANT_READY/PAYLOAD_SCHEMA.csv"),
       [{"field": f, "type": "integer" if f.startswith("page_") else "string",
         "required": "YES" if f in ("chunk_id", "content") else "NO",
         "meaning": QMEAN.get(f, "")} for f in M.QDRANT_FIELDS],
       ["field", "type", "required", "meaning"])
open(opath("QDRANT_READY/README.md"), "w", encoding="utf-8").write(
    "# QDRANT_READY\n\n"
    "`qdrant_chunks.jsonl` - one JSON object per line, %d chunks, %d payload "
    "fields each (see `PAYLOAD_SCHEMA.csv`).\n\n"
    "**No embeddings are generated in Phase 3.** Every object carries text in "
    "`content` plus the payload needed for filtered hybrid retrieval; the dense "
    "and sparse vectors are produced in a later phase, after Phase 3 is "
    "approved.\n\nChunk text is assembled only from populated canonical fields "
    "and source-declared evidence text. Empty payload fields mean the uploaded "
    "data did not establish a value - nothing was inferred or filled in.\n"
    % (NCHUNK, len(M.QDRANT_FIELDS)))
STATS = {"is": len(MASTERS["STANDARD"]), "product": len(MASTERS["PRODUCT"]),
         "qco": len(MASTERS["QCO"]), "scheme": len(MASTERS["SCHEME"]),
         "document": len(MASTERS["DOCUMENT"]), "pm": len(MASTERS["PRODUCT_MANUAL"]),
         "test": len(MASTERS["TEST"]), "lab": len(MASTERS["LABORATORY"]),
         "faq": len(MASTERS["FAQ"]), "notification": len(MASTERS["NOTIFICATION"]),
         "legal": len(MASTERS["LEGAL"]), "hallmarking": len(MASTERS["HALLMARKING"]),
         "fmcs": len(MASTERS["FMCS"]), "rel_tables": len(RELCOUNT),
         "rel_rows": sum(RELCOUNT.values()), "rel_by_table": RELCOUNT,
         "pm_sections": PMCOUNT, "attributes": NATTR, "provenance": NPROV,
         "conflicts": NCONF, "reviews": NRQ, "dla_rows": NDLA, "chunks": NCHUNK,
         "orphans": UNMATCHED, "tables_pg": len(TABLES),
         "aux": dict((k, len(v[1])) for k, v in AUXBUF.items()),
         "filestat": FILESTAT}
open(opath("93_OPERATIONAL/PHASE3_BUILD_STATS.json"), "w",
     encoding="utf-8").write(json.dumps(STATS, indent=1, sort_keys=True))
p("PHASE 3 BUILD OK  masters %d  rel_rows %d  attrs %d  prov %d  conflicts %d  "
  "chunks %d  dla %d"
  % (sum(len(MASTERS[e]) for e in M.ENT), sum(RELCOUNT.values()), NATTR, NPROV,
     NCONF, NCHUNK, NDLA))
