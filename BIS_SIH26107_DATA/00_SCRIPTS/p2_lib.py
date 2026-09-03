"""Phase 2 helpers: IS-number canonicalisation, entity extraction, comparison
primitives. READ-ONLY on every source file.

Canonicalisation contract (spec section 17). Nothing is destroyed:
  display_is_number  - exactly as observed in the source
  canonical_is_number- identity WITHOUT the year, but WITH part/section/IEC
  year               - carried separately
  part, section      - carried separately
  amendment          - carried separately
  standard_id        - stable surrogate, e.g. STD-17631, STD-1489-P1, STD-IEC-62368-1
A plain `IS 302-1` and `IS 302 (Part 1)` collapse to the SAME canonical identity,
because in BIS practice the dash form is a part designation. For IS/IEC the dash is
part of the international designation itself and is kept inline.
"""
import hashlib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p1_lib import PLACEHOLDER, is_empty, is_placeholder, norm_cell, norm_header  # noqa: E402

IS_PARSE = re.compile(r"""
    (?<![A-Za-z0-9])(?P<prefix>IS)
    (?P<iec>\s*/\s*(?:IEC\s*/\s*ISO|ISO\s*/\s*IEC|IEC|ISO))?
    [\s:\-]{0,3}
    (?P<num>\d{1,5})
    (?P<dash>-\d{1,3}(?!\d))?
    (?:\s*\(?\s*(?:Part|Pt)\.?\s*(?P<part>\d+[A-Za-z]?)\s*\)?)?
    (?:\s*\(?\s*(?:Sec|Section)\.?\s*(?P<sec>\d+)\s*\)?)?
    (?:\s*[:\-/]\s*(?P<year>(?:19|20)\d{2}))?
    (?:\s*[,;]?\s*(?:Amd|Amdt|Amendment)\.?\s*(?:No\.?\s*)?(?P<amd>\d+))?
""", re.I | re.X)

SPLIT_MULTI = re.compile(r"[;,|/\n]+(?![Ii][Ee][Cc])|\band\b", re.I)


def h16(s):
    return hashlib.sha1(s.encode("utf-8", "replace")).hexdigest()[:16]


def parse_is(text):
    """Every IS reference in `text`, as dicts. Never returns a lossy result: the
    matched substring is preserved verbatim as display_is_number."""
    out = []
    if is_empty(text) or is_placeholder(text):
        return out
    s = str(text).replace(" ", " ")
    for m in IS_PARSE.finditer(s):
        num, dash = m.group("num"), m.group("dash")
        iec = (m.group("iec") or "").strip()
        part, sec = m.group("part"), m.group("sec")
        # Plain `IS 302-1` is a part designation; `IS/IEC 62368-1` is not.
        part_src = "explicit" if part else ""
        if dash and not iec and not part:
            part, part_src, dash = dash[1:], "dash_form", None
        base = "IS"
        if iec:
            base += "/" + re.sub(r"\s+", "", iec.lstrip("/").upper())
        base += " " + num.lstrip("0").rjust(1, "0")
        if dash:
            base += dash
        canon = base
        if part:
            canon += " (Part %s)" % part.upper()
        if sec:
            canon += " (Sec %s)" % sec
        sid = "STD-" + (re.sub(r"[^A-Z0-9]", "", iec.upper()) + "-" if iec else "")
        sid += num.lstrip("0") + (dash or "")
        if part:
            sid += "-P" + part.upper()
        if sec:
            sid += "-S" + sec
        out.append({"display_is_number": m.group(0).strip(), "canonical_is_number": canon,
                    "standard_id": sid, "year": m.group("year") or "",
                    "part": part or "", "part_source": part_src, "section": sec or "",
                    "amendment": m.group("amd") or "", "is_iec": "YES" if iec else "NO"})
    return out


def canon_is_set(text):
    return {d["canonical_is_number"] for d in parse_is(text)}


# --------------------------------------------------------------- entity columns
# Which normalised column names hold which entity. Matched by substring, longest
# rule first, so `qco_number` beats a bare `number`. Deliberately conservative:
# a column that is not clearly an entity column contributes no entities at all,
# because a false entity inflates "common" counts and corrupts every decision.
ENTITY_COLS = {
    "IS": ("canonical_is_number", "display_is_number", "raw_is_number", "is_number",
           "is_no", "indian_standard", "standard_number", "standard_no", "is_code",
           "related_is_numbers", "related_is", "is_numbers", "standard"),
    "PRODUCT": ("product_name", "product_title", "product", "item_name", "goods",
                "product_category", "commodity"),
    "QCO": ("qco_id", "qco_number", "qco_no", "qco_name", "qco_title", "qco_reference",
            "qco", "quality_control_order"),
    "SCHEME": ("scheme_name", "scheme_id", "scheme_code", "scheme"),
    "LAB": ("lab_id", "laboratory_id", "lab_name", "laboratory_name", "lab_code",
            "laboratory"),
    "DOC": ("document_id", "document_title", "doc_id", "document_name", "notification_no",
            "notification_number", "circular_no", "order_no", "gazette_no", "document"),
}
# An entity column must not be a free-text blob; these never carry an entity key.
# `record_id` is a per-row surrogate, not an entity identity (scheme_record_id);
# `status`, `required`, `testing` name a state or a requirement, not an entity
# (scheme_status, required_documents, laboratory_testing). Treating any of those as an
# entity would inflate the "common entity" counts and corrupt every downstream decision.
ENTITY_BLOCK = ("description", "scope", "remark", "note", "summary", "text", "content",
                "clause", "requirement", "answer", "question", "url", "link", "source_url",
                "record_id", "status", "required", "testing")


def entity_kind(norm_name):
    if any(b in norm_name for b in ENTITY_BLOCK):
        return ""
    best, blen = "", 0
    for kind, keys in ENTITY_COLS.items():
        for k in keys:
            if k in norm_name and len(k) > blen:
                best, blen = kind, len(k)
    return best


def norm_entity(kind, v):
    """Canonical comparable form of one entity value. Multi-value cells explode."""
    if is_empty(v) or is_placeholder(v):
        return set()
    s = str(v).strip()
    if kind == "IS":
        got = canon_is_set(s)
        return got if got else set()
    parts = [p.strip() for p in SPLIT_MULTI.split(s)] if kind != "DOC" else [s]
    out = set()
    for p in parts:
        t = re.sub(r"\s+", " ", re.sub(r"[^0-9a-zऀ-ॿ]+", " ", p.lower())).strip()
        if t and t not in PLACEHOLDER and len(t) > 1:
            out.add(t)
    return out


# ------------------------------------------------------- semantic entity matching
STOP = {"the", "a", "an", "of", "for", "and", "or", "in", "with", "type", "types",
        "other", "general", "all", "its", "to", "on", "by", "s"}


def stem(t):
    for suf in ("ies", "ses", "es", "s"):
        if len(t) > 4 and t.endswith(suf):
            return t[: -len(suf)] + ("y" if suf == "ies" else "")
    return t


def toks(s):
    return {stem(t) for t in re.split(r"[^0-9a-z]+", s.lower()) if t and t not in STOP}


def sem_class(a, b):
    """spec s10: EXACT_DUPLICATE / LIKELY_DUPLICATE / RELATED_RECORD / DIFFERENT_ENTITY.
    Only EXACT_DUPLICATE may ever be auto-merged."""
    if a == b:
        return "EXACT_DUPLICATE", 1.0
    ta, tb = toks(a), toks(b)
    if not ta or not tb:
        return "DIFFERENT_ENTITY", 0.0
    j = len(ta & tb) / float(len(ta | tb))
    if ta == tb:
        return "LIKELY_DUPLICATE", 0.99
    if j >= 0.60 or ta <= tb or tb <= ta:
        return "LIKELY_DUPLICATE", round(j, 4)
    if j >= 0.34:
        return "RELATED_RECORD", round(j, 4)
    return "DIFFERENT_ENTITY", round(j, 4)


# ------------------------------------------------------------ pair primitives
DATE_FIND = re.compile(r"(20[0-2]\d|19\d\d)[-/.](\d{1,2})[-/.](\d{1,2})"
                       r"|(\d{1,2})[-/.](\d{1,2})[-/.](20[0-2]\d|19\d\d)")


def jaccard(a, b):
    u = a | b
    return round(len(a & b) / float(len(u)), 4) if u else 0.0


def row_hash(cells, idxs):
    return h16("\x1f".join(cells[i] if i < len(cells) else "" for i in idxs))


def cap(seq, n=12):
    seq = sorted(seq)
    return "; ".join(seq[:n]) + (" …(+%d)" % (len(seq) - n) if len(seq) > n else "")
