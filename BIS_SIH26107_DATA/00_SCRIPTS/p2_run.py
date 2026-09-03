"""PHASE 2 ENGINE - duplicate / overlap / version / conflict analysis.

READ-ONLY on every source file. Writes only into 01_ANALYSIS/. Nothing is archived,
nothing is merged, no folder is restructured: this phase produces evidence and a plan.

Four detection levels, run in the spec's order:
  L1 identical bytes (sha256)          L3 schema equivalence (normalised column sets)
  L2 identical tabular content         L4 row-level duplicates (normalised rows)
plus semantic entity matching, version comparison and cross-file conflict capture.
"""
import collections
import csv
import json
import os
import pickle
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p1_lib import norm_cell, norm_header  # noqa: E402
from p1_run import load_csv, load_xlsx  # noqa: E402
from p2_lib import (DATE_FIND, cap, entity_kind, h16, jaccard, norm_entity,  # noqa: E402
                    parse_is, row_hash, sem_class)

SRC = "/sessions/optimistic-gallant-gauss/mnt/SIH-DATASETS-EXCEL-SHEET"
OUT = os.path.join(SRC, "BIS_SIH26107_DATA", "01_ANALYSIS")
csv.field_size_limit(50_000_000)

DATE_COL = ("date", "retrieved", "scraped", "updated", "modified", "published",
            "notified", "effective", "issued", "timestamp", "crawl")
KINDS = ("IS", "PRODUCT", "QCO", "SCHEME", "LAB", "DOC")


def rd(name):
    with open(os.path.join(OUT, name), encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def w(name, header, rows):
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8-sig") as f:
        wr = csv.DictWriter(f, header, extrasaction="ignore")
        wr.writeheader()
        wr.writerows(rows)
    return "%-30s %6d rows" % (name, len(rows))


def load_all(inv):
    """Every worksheet, normalised. Sources are opened read-only and never written."""
    S = {}
    for r in inv:
        if not r["analysis_status"].startswith("ANALYZED"):
            continue
        p = r["exact_path"]
        if p.lower().endswith((".xlsx", ".xlsm", ".xltx")):
            loaded = [(s, h, b) for s, h, b, _ in load_xlsx(p)]
        else:
            h, b, _ = load_csv(p)
            loaded = [(os.path.splitext(os.path.basename(p))[0], h, b)]
        for sname, hdr, body in loaded:
            nh = [norm_header(x) or "__col%d" % i for i, x in enumerate(hdr)]
            n = len(hdr)
            M = []
            for row in body:
                cells = [norm_cell(v) for v in row[:n]]
                M.append(cells + [""] * (n - len(cells)))
            S[(r["file_id"], sname)] = build(r, sname, hdr, nh, M)
    return S


def build(r, sname, hdr, nh, M):
    n = len(hdr)
    idx = {c: i for i, c in enumerate(nh)}
    ent = {k: set() for k in KINDS}
    ecols = {}
    for i, c in enumerate(nh):
        k = entity_kind(c)
        if not k:
            continue
        ecols.setdefault(k, []).append(c)
        for row in M:
            ent[k] |= norm_entity(k, row[i])
    order = sorted(range(n), key=lambda i: nh[i])          # column-order-insensitive
    sig = [row_hash(row, order) for row in M]
    dates, urls = set(), set()
    for i, c in enumerate(nh):
        if any(d in c for d in DATE_COL):
            for row in M:
                m = DATE_FIND.search(row[i])
                if m:
                    dates.add(m.group(1) or m.group(6))
        if "url" in c or "link" in c:
            urls |= {row[i] for row in M if row[i].startswith("http")}
    pop = {c: sum(1 for row in M if row[idx[c]]) for c in nh}
    return dict(file_id=r["file_id"], fname=r["original_filename"], sheet=sname,
                headers=hdr, nh=nh, hset={c for c in nh if not c.startswith("__col")},
                M=M, rows=len(M), ncols=n, idx=idx, ent=ent, ecols=ecols, sig=sig,
                rowset=h16("|".join(sorted(sig))), ordered=h16("|".join(sig)),
                informative=sum(1 for row in M for v in row if v), pop=pop,
                dates=dates, urls=urls, sha=r["sha256"],
                domain=r["candidate_topic"], group=r["candidate_duplicate_group"],
                size=int(r["file_size_bytes"]), mtime=r["modified_time_utc"])


# ------------------------------------------------------------------ LEVEL 4 rows
def level4(S):
    """Repeated rows WITHIN one dataset, by normalised whole-row comparison."""
    out, tot = [], collections.Counter()
    for key in sorted(S):
        s = S[key]
        g = collections.defaultdict(list)
        for i, hh in enumerate(s["sig"]):
            g[hh].append(i)
        for hh, ix in g.items():
            if len(ix) < 2:
                continue
            tot[key] += len(ix) - 1
            samp = {c: s["M"][ix[0]][s["idx"][c]] for c in s["nh"][:6]}
            out.append(dict(
                duplicate_row_group=hh, file_id=s["file_id"], original_filename=s["fname"],
                sheet_name=s["sheet"], occurrences=len(ix),
                source_rows_1based="; ".join(str(i + 2) for i in ix[:20]),
                redundant_copies=len(ix) - 1, normalized_key_preview=json.dumps(samp)[:400],
                duplicate_type="ROW_LEVEL_EXACT_DUPLICATE_NORMALIZED",
                phase4_action="Keep the first occurrence as canonical; the other %d are "
                              "byte-equal after normalisation and carry no unique data. "
                              "Record all source rows in provenance." % (len(ix) - 1)))
    return out, tot


# ---------------------------------------------------------------- LEVEL 3 schema
def level3(S):
    ks = sorted(S)
    out = []
    for a in range(len(ks)):
        for b in range(a + 1, len(ks)):
            x, y = S[ks[a]], S[ks[b]]
            ca, cb = x["hset"], y["hset"]
            com, ua, ub = ca & cb, ca - cb, cb - ca
            j = jaccard(ca, cb)
            if not com:
                v = "SCHEMA_DISJOINT"
            elif not ua and not ub:
                v = "SCHEMA_IDENTICAL"
            elif not ua or not ub:
                v = "SCHEMA_SUBSET"
            elif j >= 0.60:
                v = "SCHEMA_SUBSTANTIALLY_IDENTICAL"
            elif j >= 0.25:
                v = "SCHEMA_OVERLAP"
            else:
                v = "SCHEMA_WEAK_OVERLAP"
            out.append(dict(
                pair_id="SC-%04d" % len(out), file_a=x["fname"], sheet_a=x["sheet"],
                file_b=y["fname"], sheet_b=y["sheet"], columns_a=len(ca), columns_b=len(cb),
                common_columns=len(com), unique_columns_a=len(ua), unique_columns_b=len(ub),
                column_jaccard=j, schema_verdict=v,
                common_column_list=cap(com, 20), unique_a_list=cap(ua, 12),
                unique_b_list=cap(ub, 12), **gate(x, y, j)))
    return out


def gate(x, y, j):
    """Which pairs earn a full content comparison. Schema similarity alone is not
    enough: two datasets can describe the same standards through different columns,
    which is exactly what a complementary pair looks like. So entity overlap and a
    shared domain also open the gate. The reason is recorded for auditability."""
    why = []
    if j >= 0.25:
        why.append("SCHEMA_JACCARD>=0.25")
    if x["group"] == y["group"] != "SINGLETON":
        why.append("PHASE1_CANDIDATE_GROUP=" + x["group"])
    if x["rowset"] == y["rowset"]:
        why.append("IDENTICAL_ROW_MULTISET")
    ej = {}
    for k in ("IS", "PRODUCT", "QCO", "SCHEME", "LAB", "DOC"):
        ej[k] = jaccard(x["ent"][k], y["ent"][k])
        if ej[k] >= 0.30:
            why.append("%s_JACCARD=%.2f" % (k, ej[k]))
    if x["domain"] == y["domain"] and x["domain"] not in ("UNKNOWN", "OTHER_RELEVANT"):
        why.append("SAME_DOMAIN=" + x["domain"])
    return dict(entity_jaccard_max=round(max(ej.values()), 4),
                deep_compared="YES" if why else "NO",
                deep_compare_reason="; ".join(why) if why else "NO_CONTENT_LINK_DETECTED")


# ------------------------------------------------------- LEVELS 1 & 2 file/content
def level12(inv, S):
    """L1 = identical bytes. L2 = identical tabular content (order-sensitive and
    order-insensitive are reported separately; neither is inferred from a filename)."""
    by_sha, l1 = collections.defaultdict(list), []
    for r in inv:
        by_sha[r["sha256"]].append(r)
    for sha, rs in sorted(by_sha.items()):
        if len(rs) > 1:
            l1.append((sha, sorted(x["original_filename"] for x in rs)))
    fp = collections.defaultdict(list)          # file-level content fingerprints
    for (fid, sname), s in S.items():
        fp[fid].append((sname, s["ordered"], s["rowset"], s["rows"], tuple(s["nh"])))
    sigo, sigu = collections.defaultdict(list), collections.defaultdict(list)
    for fid, sheets in fp.items():
        sheets.sort()
        sigo["|".join("%s:%s:%s" % (a, b, e) for a, b, _, _, e in sheets)].append(fid)
        sigu["|".join(sorted(c for _, _, c, _, _ in sheets))].append(fid)
    l2o = [v for v in sigo.values() if len(v) > 1]
    l2u = [v for v in sigu.values() if len(v) > 1]
    return l1, l2o, l2u


# ------------------------------------------------------------- deep pair analysis
def proj(s, cols):
    """Row multiset of one sheet restricted to `cols` (sorted, so column order in the
    source is irrelevant). Empty projected rows are dropped: an all-blank projection
    is not evidence of a shared record."""
    ix = [s["idx"][c] for c in cols]
    c = collections.Counter()
    keep = collections.defaultdict(list)
    for ri, row in enumerate(s["M"]):
        vals = [row[i] for i in ix]
        if not any(vals):
            continue
        hh = row_hash(vals, range(len(vals)))
        c[hh] += 1
        keep[hh].append(ri)
    return c, keep


def key_cols(x, y, cols):
    """Common columns usable as a record key: near-unique and well populated in BOTH.

    Uniqueness alone is NOT sufficient. `product_id` is unique inside every products
    file, yet the files use three different namespaces for the same 40 products
    (`PROD_IS17631_CHAIRS` / `IS 17631:2022` / `27280 (from standard record endpoint)`).
    Keyed on that column the same product counts as two distinct records, which would
    make Phase 4 emit 80 rows for 40 products - the exact loss of identity this analysis
    exists to prevent. So a candidate that is unique per file but shares NO value with
    the other file is a per-file surrogate and is demoted, and the demotion is reported.
    """
    cand, rejected = [], []
    for c in cols:
        ra, rb = x["rows"], y["rows"]
        if ra < 2 or rb < 2:
            continue
        va = {row[x["idx"][c]] for row in x["M"] if row[x["idx"][c]]}
        vb = {row[y["idx"][c]] for row in y["M"] if row[y["idx"][c]]}
        pa, pb = x["pop"][c] / float(ra), y["pop"][c] / float(rb)
        if pa < 0.90 or pb < 0.90 or not va or not vb:
            continue
        if len(va) / float(x["pop"][c]) < 0.95 or len(vb) / float(y["pop"][c]) < 0.95:
            continue
        ov = jaccard(va, vb)
        if not (va & vb):
            rejected.append(c)
        cand.append((0 if va & vb else 1, 0 if entity_kind(c) else 1, -ov, len(c), c))
    cand.sort()
    note = ("SURROGATE_KEY_DEMOTED_ZERO_VALUE_OVERLAP: " + cap(rejected, 6)
            if rejected else "")
    if rejected and all(r[0] == 1 for r in cand):
        note = ("NO_SHARED_KEY_VALUES; candidates unique per file but disjoint (%s) - "
                "identity must be re-derived in Phase 3 from entity columns, NOT from "
                "these surrogates" % cap(rejected, 6))
    return [c for _, _, _, _, c in cand], note


def conflicts_for(x, y, cols, kc, pair_id):
    """Same record key in both sheets, but a shared column disagrees. Nothing is
    resolved here and nothing is overwritten - both values are carried forward."""
    out = []
    if not kc:
        return out
    k = kc[0]
    ka, kb = x["idx"][k], y["idx"][k]
    ma = {}
    for ri, row in enumerate(x["M"]):
        if row[ka]:
            ma.setdefault(row[ka], ri)
    other = [c for c in cols if c != k]
    for ri, row in enumerate(y["M"]):
        kv = row[kb]
        if not kv or kv not in ma:
            continue
        ai = ma[kv]
        for c in other:
            av = x["M"][ai][x["idx"][c]]
            bv = row[y["idx"][c]]
            if not av or not bv or av == bv:
                continue
            cls, sc = sem_class(av, bv)
            out.append(dict(
                conflict_id="", pair_id=pair_id, record_key_column=k, record_key_value=kv[:180],
                conflicting_column=c, file_a=x["fname"], sheet_a=x["sheet"],
                source_row_a=ai + 2, value_a=av[:300],
                file_b=y["fname"], sheet_b=y["sheet"], source_row_b=ri + 2, value_b=bv[:300],
                value_similarity=sc, value_relationship=cls,
                conflict_type=("VALUE_FORMAT_VARIANT" if cls in ("EXACT_DUPLICATE",
                               "LIKELY_DUPLICATE") else "VALUE_DISAGREEMENT"),
                resolution_status="UNRESOLVED_PRESERVE_BOTH",
                phase4_action="Do NOT overwrite. Keep both values with provenance; set "
                              "status=REQUIRES_REVIEW on the merged record unless a "
                              "documented precedence rule is agreed in Phase 3."))
    return out


def deep_pair(x, y, pair_id, sc_verdict, cj):
    """Content-level comparison of two worksheets. Filenames are never consulted."""
    ca, cb = x["hset"], y["hset"]
    com = sorted(ca & cb)
    ua, ub = ca - cb, cb - ca
    if com:
        pa, ka = proj(x, com)
        pb, kb = proj(y, com)
        inter = sum(min(pa[h], pb[h]) for h in set(pa) & set(pb))
        only_a = sum(pa.values()) - inter
        only_b = sum(pb.values()) - inter
        uni = sum(pa.values()) + sum(pb.values()) - inter
        rj = round(inter / float(uni), 4) if uni else 0.0
        arows = sorted(ri + 2 for h in set(pa) - set(pb) for ri in ka[h])
        brows = sorted(ri + 2 for h in set(pb) - set(pa) for ri in kb[h])
    else:
        inter = only_a = only_b = 0
        rj = 0.0
        arows = [i + 2 for i in range(x["rows"])]
        brows = [i + 2 for i in range(y["rows"])]
    ents = {}
    for k in KINDS:
        A, B = x["ent"][k], y["ent"][k]
        ents[k] = (len(A & B), len(A - B), len(B - A), jaccard(A, B), A, B)
    kc, knote = key_cols(x, y, com)
    cf = conflicts_for(x, y, com, kc, pair_id)
    # A row overlap measured on a 1-2 column projection is not row evidence: two
    # unrelated files that both carry `is_number` would score 1.0. Row metrics only
    # count toward similarity when the projection covers a real part of both schemas.
    reliable = len(com) >= 3 and len(com) >= 0.5 * min(len(ca), len(cb))
    sim = round(0.65 * (rj if reliable else 0.0) + 0.35 * cj, 4)
    # Record-level overlap on the shared key. This, not whole-row equality, is what
    # decides whether B carries records A does not have (spec rule 7).
    if kc:
        A = {row[x["idx"][kc[0]]] for row in x["M"] if row[x["idx"][kc[0]]]}
        B = {row[y["idx"][kc[0]]] for row in y["M"] if row[y["idx"][kc[0]]]}
        kcom, kua, kub, kj = len(A & B), len(A - B), len(B - A), jaccard(A, B)
        ksamp_a, ksamp_b = cap(A - B, 6), cap(B - A, 6)
    else:
        kcom = kua = kub = -1
        kj = 0.0
        ksamp_a = ksamp_b = "NO_SHARED_RECORD_KEY"
    # Do the two sheets describe the same entities even when the record key says no?
    # A disjoint key plus strong entity overlap means the key is a surrogate, not that
    # the records are different. Phase 3 must re-key such a pair before merging.
    ej = max(ents[k][3] for k in KINDS)
    if kcom > 0:
        ident = "KEY_LINKED"
    elif ej >= 0.30:
        ident = "SAME_ENTITIES_DIFFERENT_KEY_NAMESPACE"
    elif kcom == 0:
        ident = "KEY_DISJOINT_NO_ENTITY_EVIDENCE"
    else:
        ident = "NO_KEY_AVAILABLE"
    return dict(
        pair_id=pair_id, file_a=x["fname"], sheet_a=x["sheet"], file_id_a=x["file_id"],
        file_b=y["fname"], sheet_b=y["sheet"], file_id_b=y["file_id"],
        domain_a=x["domain"], domain_b=y["domain"],
        phase1_candidate_group=x["group"] if x["group"] == y["group"] else
        "%s / %s" % (x["group"], y["group"]),
        rows_a=x["rows"], rows_b=y["rows"], columns_a=len(ca), columns_b=len(cb),
        common_columns=len(com), unique_columns_a=len(ua), unique_columns_b=len(ub),
        column_jaccard=cj, schema_verdict=sc_verdict,
        common_rows=inter, unique_rows_a=only_a, unique_rows_b=only_b,
        row_jaccard=rj, similarity_score=sim,
        projection_width=len(com),
        row_metric_reliability="RELIABLE" if reliable else "LOW_PROJECTION_WIDTH",
        identical_bytes="YES" if x["sha"] == y["sha"] else "NO",
        identical_row_multiset="YES" if x["rowset"] == y["rowset"] else "NO",
        identical_row_order="YES" if x["ordered"] == y["ordered"] else "NO",
        common_IS_numbers=ents["IS"][0], unique_IS_numbers_a=ents["IS"][1],
        unique_IS_numbers_b=ents["IS"][2], IS_jaccard=ents["IS"][3],
        common_products=ents["PRODUCT"][0], unique_products_a=ents["PRODUCT"][1],
        unique_products_b=ents["PRODUCT"][2], product_jaccard=ents["PRODUCT"][3],
        common_qcos=ents["QCO"][0], unique_qcos_a=ents["QCO"][1], unique_qcos_b=ents["QCO"][2],
        common_schemes=ents["SCHEME"][0], unique_schemes_a=ents["SCHEME"][1],
        unique_schemes_b=ents["SCHEME"][2], scheme_jaccard=ents["SCHEME"][3],
        common_labs=ents["LAB"][0], common_documents=ents["DOC"][0],
        entity_jaccard_max=round(ej, 4),
        common_urls=len(x["urls"] & y["urls"]), unique_urls_a=len(x["urls"] - y["urls"]),
        unique_urls_b=len(y["urls"] - x["urls"]),
        years_a=cap(x["dates"], 8), years_b=cap(y["dates"], 8),
        populated_cells_a=x["informative"], populated_cells_b=y["informative"],
        record_key_column=kc[0] if kc else "", key_candidates=cap(kc, 6),
        key_selection_note=knote, entity_identity_verdict=ident,
        common_records_by_key=kcom, unique_records_a_by_key=kua,
        unique_records_b_by_key=kub, record_key_jaccard=kj,
        sample_records_only_in_a=ksamp_a, sample_records_only_in_b=ksamp_b,
        is_columns_a=cap(x["ecols"].get("IS", []), 6),
        is_columns_b=cap(y["ecols"].get("IS", []), 6),
        conflicts=len(cf), conflicting_columns=cap({c["conflicting_column"] for c in cf}, 10),
        unique_rows_a_1based=cap([str(i) for i in arows], 25),
        unique_rows_b_1based=cap([str(i) for i in brows], 25),
        common_column_list=cap(com, 25), unique_a_list=cap(ua, 15), unique_b_list=cap(ub, 15),
        sample_unique_is_a=cap(ents["IS"][4] - ents["IS"][5], 8),
        sample_unique_is_b=cap(ents["IS"][5] - ents["IS"][4], 8),
        sample_unique_scheme_a=cap(ents["SCHEME"][4] - ents["SCHEME"][5], 6),
        sample_unique_scheme_b=cap(ents["SCHEME"][5] - ents["SCHEME"][4], 6),
    ), cf


# ------------------------------------------------------------------------- driver
def main():
    inv = rd("FILE_INVENTORY.csv")
    S = load_all(inv)
    print("sheets loaded: %d   rows: %d" % (len(S), sum(s["rows"] for s in S.values())))

    l1, l2o, l2u = level12(inv, S)
    print("L1 identical-byte groups: %d   L2 ordered: %d   L2 rowset: %d"
          % (len(l1), len(l2o), len(l2u)))

    rowdups, rowtot = level4(S)
    sc = level3(S)
    print(w("ROW_LEVEL_DUPLICATES.csv", list(rowdups[0]), rowdups) if rowdups
          else "ROW_LEVEL_DUPLICATES.csv     0 rows")
    print(w("SCHEMA_COMPARISON.csv", list(sc[0]), sc))

    ks = sorted(S)
    pos = {k: i for i, k in enumerate(ks)}
    deep, allcf = [], []
    for r in sc:
        if r["deep_compared"] != "YES":
            continue
        a = pos[[k for k in ks if S[k]["fname"] == r["file_a"] and S[k]["sheet"] == r["sheet_a"]][0]]
        b = pos[[k for k in ks if S[k]["fname"] == r["file_b"] and S[k]["sheet"] == r["sheet_b"]][0]]
        d, cf = deep_pair(S[ks[a]], S[ks[b]], "DC-%04d" % len(deep),
                          r["schema_verdict"], r["column_jaccard"])
        deep.append(d)
        allcf.extend(cf)
    for i, c in enumerate(allcf):
        c["conflict_id"] = "CF-%05d" % i
    print(w("DATASET_COMPARISON.csv", list(deep[0]), deep))
    CF_H = ["conflict_id", "pair_id", "record_key_column", "record_key_value",
            "conflicting_column", "file_a", "sheet_a", "source_row_a", "value_a",
            "file_b", "sheet_b", "source_row_b", "value_b", "value_similarity",
            "value_relationship", "conflict_type", "resolution_status", "phase4_action"]
    print(w("CONFLICTS.csv", CF_H, allcf))

    facts = {k: {a: v for a, v in S[k].items() if a not in ("M", "sig")} for k in S}
    with open(os.path.join(OUT, "_cache", "phase2_pairs.pkl"), "wb") as f:
        pickle.dump({"deep": deep, "sc": sc, "l1": l1, "l2o": l2o, "l2u": l2u,
                     "rowtot": dict(rowtot), "rowdups": len(rowdups), "facts": facts,
                     "conflicts": allcf}, f)
    print("cached %d pair records for the decision stage" % len(deep))


if __name__ == "__main__":
    main()
