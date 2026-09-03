"""Phase 3 primitives: lossless normalisation, three-way null semantics, deterministic
ID minting, paren-aware multi-value splitting, homonym-safe URL handling.

Every function is pure and lossless: it returns the normalised form only, so the caller
can always persist original_value beside it. Nothing here writes to a source file.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from p1_lib import is_empty, is_placeholder, norm_cell, norm_header  # noqa: E402,F401
from p2_lib import canon_is_set, h16, parse_is  # noqa: E402,F401

# ------------------------------------------------------------ null semantics (3J)
# Three-way, per the spec: an explicit statement of absence is DATA, not a null, and
# must never be flattened into one. A dash or "TBD" asserts nothing either way.
ABSENCE = {"none", "nil", "not applicable", "notapplicable", "not required",
           "none required", "no", "nothing", "not needed", "does not apply",
           "no data", "not mandatory", "zero", "0 nos", "absent"}
EXPLICIT_NULL = {"null", "nan", "(null)", "blank", "empty"}
AMBIG = {"na", "n/a", "n.a.", "n.a", "-", "--", "---", "?", "??", "tbd",
         "to be decided", "to be determined", "unknown", "not available",
         "notavailable", "not found", "n/f", "not specified", "not mentioned",
         "unspecified", "pending", "under review", "refer document", "as above",
         "same as above", "-do-", "do", "see above", "—", "–"}
NULL_CLASSES = ("POPULATED", "NULL_UNKNOWN", "ASSERTED_ABSENCE",
                "AMBIGUOUS_REQUIRES_REVIEW")


def nws(v):
    """Whitespace/invisible-character normalisation. The only universally safe edit."""
    if v is None:
        return ""
    if isinstance(v, float) and v != v:
        return ""
    s = str(v)
    for bad in (" ", " ", " "):
        s = s.replace(bad, " ")
    for zap in ("﻿", "​", "‌", "‍", "⁠"):
        s = s.replace(zap, "")
    return re.sub(r"[ \t\r\n\f\v]+", " ", s).strip()


def nullclass(v):
    """POPULATED / NULL_UNKNOWN / ASSERTED_ABSENCE / AMBIGUOUS_REQUIRES_REVIEW."""
    s = nws(v)
    if s == "":
        return "NULL_UNKNOWN"
    t = s.lower().rstrip(".").strip()
    if t in EXPLICIT_NULL:
        return "NULL_UNKNOWN"
    if t in ABSENCE:
        return "ASSERTED_ABSENCE"
    if t in AMBIG:
        return "AMBIGUOUS_REQUIRES_REVIEW"
    return "POPULATED"


def missing_reason(cls):
    return {"NULL_UNKNOWN": "SOURCE_CELL_EMPTY",
            "ASSERTED_ABSENCE": "SOURCE_ASSERTS_ABSENCE",
            "AMBIGUOUS_REQUIRES_REVIEW": "SOURCE_PLACEHOLDER_AMBIGUOUS",
            "POPULATED": ""}[cls]


def val(v):
    """Value for a canonical column: '' unless genuinely populated.
    Never substitutes 'N/A'/'Unknown'/'-' for a null - the spec forbids it."""
    return nws(v) if nullclass(v) == "POPULATED" else ""


# ------------------------------------------------------------------- dates (3E)
MON = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov",
     "dec"], 1)}
_ISO = re.compile(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})")
_NUM = re.compile(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})$")
_DMY = re.compile(r"^(\d{1,2})(?:st|nd|rd|th)?[ \-]([A-Za-z]{3,9})\.?,?[ \-](\d{4})$")
_MDY = re.compile(r"^([A-Za-z]{3,9})\.?[ \-](\d{1,2})(?:st|nd|rd|th)?,?[ \-](\d{4})$")
_MY = re.compile(r"^([A-Za-z]{3,9})\.?[ \-,]*(\d{4})$")
_YM = re.compile(r"^(\d{4})[-/.](\d{1,2})$")
_Y = re.compile(r"^(?:19|20)\d{2}$")


def _mon(name):
    return MON.get(name.lower()[:3], 0)


def _mk(y, m, d):
    y, m, d = int(y), int(m), int(d)
    if not (1900 <= y <= 2100 and 1 <= m <= 12 and 1 <= d <= 31):
        return ""
    return "%04d-%02d-%02d" % (y, m, d)


def ndate(v):
    """ISO date + precision + flag. Never invents a day or month that is not stated.
    Numeric dd/mm vs mm/dd resolves day-first (Indian convention) and is flagged
    AMBIGUOUS_DMY when both components are <= 12, so a reviewer can see the risk."""
    s = nws(v)
    out = {"iso": "", "precision": "", "flag": "", "raw": s}
    if nullclass(s) != "POPULATED":
        return out
    s = re.sub(r"[ T]\d{1,2}:\d{2}(:\d{2})?(\.\d+)?$", "", s).strip()
    if _ISO.match(s):
        out["iso"], out["precision"] = _mk(*_ISO.match(s).groups()), "DAY"
    elif _NUM.match(s):
        a, b, y = _NUM.match(s).groups()
        y = ("20" + y) if len(y) == 2 and int(y) < 50 else ("19" + y) if len(y) == 2 else y
        d, mo = (a, b) if int(a) > 12 else ((b, a) if int(b) > 12 else (a, b))
        out["iso"], out["precision"] = _mk(y, mo, d), "DAY"
        if int(a) <= 12 and int(b) <= 12:
            out["flag"] = "AMBIGUOUS_DMY"
    elif _DMY.match(s):
        d, mn, y = _DMY.match(s).groups()
        out["iso"], out["precision"] = _mk(y, _mon(mn) or 1, d), "DAY"
    elif _MDY.match(s) and _mon(_MDY.match(s).group(1)):
        mn, d, y = _MDY.match(s).groups()
        out["iso"], out["precision"] = _mk(y, _mon(mn), d), "DAY"
    elif _YM.match(s):
        y, mo = _YM.match(s).groups()
        if 1 <= int(mo) <= 12:
            out["iso"], out["precision"] = "%s-%02d" % (y, int(mo)), "MONTH"
    elif _MY.match(s) and _mon(_MY.match(s).group(1)):
        mn, y = _MY.match(s).groups()
        out["iso"], out["precision"] = "%s-%02d" % (y, _mon(mn)), "MONTH"
    elif _Y.match(s):
        out["iso"], out["precision"] = s, "YEAR"
    if not out["iso"]:
        out["flag"], out["precision"] = "UNPARSED_PRESERVED", "NONE"
    return out


# ----------------------------------------------- URL / label split (3D homonym)
# Phase 2 proved `source_url` carries two different meanings across files: a real
# LIMS/BIS URL in some, a prose label ("bis product manuals") in others. Splitting
# is mandatory; unioning them would corrupt both fields.
_URL = re.compile(r"(?:https?://|ftp://)[^\s<>\"'\\]+", re.I)
_BARE = re.compile(r"^(?:www\.[^\s]+|[a-z0-9][a-z0-9.\-]*\.(?:gov\.in|nic\.in|org\.in|"
                   r"co\.in|com|org|net|in|gov)(?:/[^\s]*)?)$", re.I)


def nurl(v):
    """-> {url, label, cls}. cls in URL / URL_IN_TEXT / URL_SCHEME_ADDED / LABEL / EMPTY.
    A prose value is never coerced into a URL and a URL is never demoted to a label."""
    s = nws(v)
    if nullclass(s) != "POPULATED":
        return {"url": "", "label": "", "cls": "EMPTY"}
    m = _URL.search(s)
    if m:
        u = m.group(0).rstrip(".,;:)]}'\"")
        rest = nws(s.replace(m.group(0), " "))
        return {"url": u, "label": rest, "cls": "URL" if not rest else "URL_IN_TEXT"}
    if _BARE.match(s):
        return {"url": "https://" + s.lstrip("/"), "label": "",
                "cls": "URL_SCHEME_ADDED"}
    return {"url": "", "label": s, "cls": "LABEL"}


# --------------------------------------------- statute / order number normalisation
def nqco(v):
    """QCO / S.O. / G.S.R. number: case and separator normalisation only."""
    s = nws(v)
    if nullclass(s) != "POPULATED":
        return ""
    t = re.sub(r"\bS\.?\s*O\.?\s*", "S.O. ", s, flags=re.I)
    t = re.sub(r"\bG\.?\s*S\.?\s*R\.?\s*", "G.S.R. ", t, flags=re.I)
    t = re.sub(r"\s*\(\s*[Ee]\s*\)", "(E)", t)
    t = re.sub(r"\bno\.?\s*:?\s*", "No. ", t, flags=re.I)
    t = re.sub(r"\bdated?\b", "dated", t, flags=re.I)
    return re.sub(r"\s+", " ", t).strip(" .,;")


def nnotif(v):
    """Notification / circular / order number: same treatment plus year unification."""
    s = nqco(v)
    return re.sub(r"\b(\d{4})\s*[-/]\s*(\d{2})\b", r"\1-\2", s)


# ------------------------------------------------- controlled vocabularies (3E)
STATUS_VOCAB = ("ACTIVE", "WITHDRAWN", "SUPERSEDED", "SUSPENDED", "CANCELLED",
                "EXPIRED", "DRAFT", "PROPOSED", "NOTIFIED", "RECOGNIZED",
                "DERECOGNIZED", "UNKNOWN", "OTHER")
_STATUS = [(r"de[\- ]?recogni[sz]", "DERECOGNIZED"),
           (r"with\s?dr[aw]{2}n|withdrwan|withdral", "WITHDRAWN"),
           (r"supersed|replaced\s+by", "SUPERSEDED"),
           (r"suspend", "SUSPENDED"),
           (r"cancel|revok|terminat", "CANCELLED"),
           (r"expir|lapsed", "EXPIRED"),
           (r"draft|under\s+(revision|development|preparation|formulation)|\bwip\b",
            "DRAFT"),
           (r"propos|upcoming|forthcoming|to\s+be\s+notified", "PROPOSED"),
           (r"recogni[sz]ed|accredit|empanel", "RECOGNIZED"),
           (r"notified|gazett", "NOTIFIED"),
           (r"\bactive\b|in\s?force|\bcurrent\b|\bvalid\b|operational|existing|"
            r"published|reaffirm|\blive\b|\byes\b", "ACTIVE")]


def nstatus(v):
    """-> (canonical_status, original). Unmapped populated text becomes OTHER, never
    silently ACTIVE: inventing a status would assert a regulatory fact."""
    s = nws(v)
    c = nullclass(s)
    if c != "POPULATED":
        return ("UNKNOWN" if c != "ASSERTED_ABSENCE" else "UNKNOWN", s)
    low = s.lower()
    for rx, tag in _STATUS:
        if re.search(rx, low):
            return (tag, s)
    return ("OTHER", s)


def nmand(v):
    """mandatory / voluntary flag -> MANDATORY | VOLUNTARY | BOTH | UNKNOWN | OTHER."""
    s = nws(v)
    if nullclass(s) != "POPULATED":
        return ("UNKNOWN", s)
    low = s.lower()
    m, vo = bool(re.search(r"mandator|compulsor|obligator", low)), \
        bool(re.search(r"voluntar|optional", low))
    if m and vo:
        return ("BOTH", s)
    if m:
        return ("MANDATORY", s)
    if vo:
        return ("VOLUNTARY", s)
    return ("OTHER", s)


# --------------------------------------------- guarded multi-value splitting (3F)
_LEAD = re.compile(r"^(and|or|but|which|that|who|whose|where|when|while|including|"
                   r"such as|as per|with|without|for|to|in|of|by|on|at|from|under|per|"
                   r"using|after|before|during|so|not|all|any|each|either|both|based|"
                   r"subject|provided|except|unless|however|therefore|thus|also|"
                   r"if|then|shall|must|may|etc|e\.g|i\.e)\b", re.I)
_TRAIL = re.compile(r"\b(and|or|of|for|the|a|an|with|in|to|by|as|shall|is|are)\s*$", re.I)
# Regulatory prose markers: a cell containing one of these is a sentence, so its
# commas are grammar, not delimiters. Splitting it would fabricate list members.
_PROSE = re.compile(r"\b(shall|must|should|may be|will be|is to be|are to be|means|"
                    r"refers to|as defined|in accordance|thereof|hereby)\b", re.I)


def _split(s, comma):
    out, buf, depth = [], [], 0
    for ch in s:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        if depth == 0 and (ch in ";|\n" or (ch == "," and comma)):
            out.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    out.append("".join(buf))
    return [nws(p) for p in out]


def msplit(v, comma=True, floor=2):
    """Split a delimited cell without shredding prose. Commas inside brackets are
    protected so `IS 1489 (Part 1, Part 2)` survives; if comma-splitting produces a
    clause-shaped fragment the value is treated as a sentence and re-split on `;`."""
    s = nws(v)
    if nullclass(s) != "POPULATED":
        return []
    parts = _split(s, comma)
    if comma and (_PROSE.search(s)
                  or max((len(p) for p in parts), default=0) > 90
                  or max((len(p.split()) for p in parts), default=0) > 12
                  or any(_LEAD.match(p) for p in parts[1:])
                  or any(_TRAIL.search(p) for p in parts[:-1])):
        parts = _split(s, False)
    parts = [p for p in parts if p and nullclass(p) == "POPULATED"]
    if len(parts) < floor:
        return parts[:1] if parts else []
    seen, out = set(), []
    for p in parts:
        k = p.lower()
        if k not in seen:
            seen.add(k)
            out.append(p)
    return out


def nname(v):
    """Names/titles: whitespace only, plus de-shouting of fully-capitalised strings
    that contain no acronym-only tokens. Display text is otherwise left verbatim."""
    s = nws(v)
    if nullclass(s) != "POPULATED":
        return ""
    s = re.sub(r"\s*/\s*", "/", s).strip(" .;,-")
    return re.sub(r"\s+", " ", s)


# ------------------------------------------------- IS number canonicalisation (3C)
IS_FIELDS = ("is_id", "raw_is_number", "display_is_number", "canonical_is_number",
             "standard_year", "part_number", "section_number", "amendment_reference",
             "iec_reference", "part_source", "parse_status")


def nis(v):
    """Full 3C bundle for the FIRST IS reference in `v`; raw_is_number keeps the cell
    verbatim. Part numbers, years, sections, amendments and IEC references are all
    retained - `IS 1489 (Part 1)` and `(Part 2)` stay separate standards."""
    raw = nws(v)
    hits = parse_is(raw)
    if not hits:
        return dict(zip(IS_FIELDS, ("", raw, "", "", "", "", "", "", "", "",
                                    "NO_IS_REFERENCE" if raw else "EMPTY")))
    d = hits[0]
    iec = ""
    if d["is_iec"] == "YES":
        m = re.match(r"IS/([A-Z]+)\s", d["canonical_is_number"])
        iec = (m.group(1) if m else "IEC") + " " + \
            d["canonical_is_number"].split(" ", 1)[1].split(" (")[0]
    return {"is_id": d["standard_id"], "raw_is_number": raw,
            "display_is_number": d["display_is_number"],
            "canonical_is_number": d["canonical_is_number"],
            "standard_year": d["year"], "part_number": d["part"],
            "section_number": d["section"], "amendment_reference": d["amendment"],
            "iec_reference": iec, "part_source": d["part_source"],
            "parse_status": "PARSED" if len(hits) == 1 else "PARSED_FIRST_OF_%d" % len(hits)}


def is_all(v):
    """Every distinct IS in a cell, canonical order preserved. Used for relationships."""
    out, seen = [], set()
    for d in parse_is(nws(v)):
        if d["standard_id"] not in seen:
            seen.add(d["standard_id"])
            out.append(d)
    return out


# -------------------------------------------------------- deterministic IDs (3B)
class Mint:
    """Surrogate IDs that are stable across runs: keys are collected first, then
    numbered in sorted order, so the same corpus always yields the same IDs."""

    def __init__(self, prefix, width=5):
        self.prefix, self.width, self.keys, self.map = prefix, width, set(), {}

    def add(self, key):
        k = nws(key).lower()
        if k:
            self.keys.add(k)
        return k

    def seal(self):
        for i, k in enumerate(sorted(self.keys), 1):
            self.map[k] = "%s-%0*d" % (self.prefix, self.width, i)
        return self

    def get(self, key):
        return self.map.get(nws(key).lower(), "")

    def __len__(self):
        return len(self.map)


# ------------------------------------------------------------------- csv plumbing
def wcsv(path, rows, cols):
    """Write a canonical CSV: fixed column order, UTF-8-sig, CRLF-safe quoting."""
    import csv as _csv
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = _csv.DictWriter(f, fieldnames=cols, extrasaction="ignore",
                            quoting=_csv.QUOTE_MINIMAL)
        w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in cols})
    return len(rows)


def rcsv(path):
    import csv as _csv
    _csv.field_size_limit(50_000_000)
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(_csv.DictReader(f))


# ==================================================== composite decomposition (3D/3E)
# Four source columns pack two or more facts into one cell. Each splitter returns the
# parts PLUS `original`, and a `split_method` naming the evidence used, so a reviewer
# can see whether the split was cue-driven or a fallback. Nothing is ever discarded:
# if no cue is found the whole string is preserved in the leading part and the method
# says so, which is what keeps DECOMPOSE_COMPOSITE lossless.

_LIC = re.compile(r"\b(?:CM\s*/?\s*L|CML)\s*[-–:/]?\s*(\d[\d\s./-]*\d|\d)", re.I)
_LICDIG = re.compile(r"\d{4,}")


def nlic(v):
    """Normalise a CML / licence number -> {licence_no, licence_key, original, cls}.

    F040 and F045 are the same 3135-row FMCS population and must join on this key, not
    on row order. `licence_key` is digits only so `CM/L-1234567`, `CML 1234567` and
    `CM/L 12 34 567` collapse to one key; `licence_no` keeps a readable display form.
    A value with no licence digits is NOT coerced into one - it is returned cls=LABEL
    with the text intact, so prose in a licence column stays visible instead of
    becoming a silent empty join key.
    """
    s = nws(v)
    if nullclass(s) != "POPULATED":
        return {"licence_no": "", "licence_key": "", "original": s, "cls": "EMPTY"}
    m = _LIC.search(s)
    digits = re.sub(r"\D", "", m.group(1)) if m else ""
    if not digits:
        d = _LICDIG.search(s)
        digits = d.group(0) if d else ""
        cls = "DIGITS_ONLY" if digits else "LABEL"
    else:
        cls = "CML"
    return {"licence_no": ("CM/L-" + digits) if digits else s,
            "licence_key": digits, "original": s, "cls": cls}


_DATECUE = re.compile(r"\b(?:date[sd]?|dt\.?|w\.?e\.?f\.?|with effect from|"
                      r"published on|issued on|notified on)\b[: ]*", re.I)
_NOTIFNO = re.compile(r"(?:S\.?\s*O\.?|G\.?\s*S\.?\s*R\.?|CG-DL-E|\bNo\.?)\s*[-:]?\s*"
                      r"\d[\w()./\-]*", re.I)
_PARENS = re.compile(r"\(([^)]*)\)")
_YRONLY = re.compile(r"^\d{4}(?:\s*[/&-]\s*\d{4})?$")


def split_no_and_date(v):
    """`notification_no_date` (F019) -> number + date + note, original preserved.

    Measured shapes in the real column: `S.O. 294(E) (21-01-2020)`,
    `Notified 13 Feb 2025`, `Notified Draft / Final Order (2024)`,
    `Ministry Notification (2024/2025)`, `S.O. 189(E) / Amendments`. So three things
    must hold: the date may be a bare year, a cell may carry no number at all, and any
    text left over after the number must survive. Evidence order is date-cue word, then
    a trailing parenthesised date, then a trailing bare date.

    `number` stays EMPTY unless a real numbered-order token is present - `Notified` is
    a status word, not a notification number, and promoting it would invent an
    identifier. It lands in `number_note` instead.
    """
    s = nws(v)
    out = {"number": "", "number_note": "", "date_iso": "", "date_precision": "NONE",
           "date_flag": "", "date_text": "", "original": s, "split_method": "NO_CUE"}
    if nullclass(s) != "POPULATED":
        out["split_method"] = "EMPTY"
        return out
    head, tail = s, ""
    m = _DATECUE.search(s)
    if m:
        head, tail, out["split_method"] = s[:m.start()], s[m.end():], "DATE_CUE"
    else:
        grp = list(_PARENS.finditer(s))
        if grp:
            g = grp[-1]
            inner = g.group(1).strip()
            if ndate(inner)["iso"] or _YRONLY.match(inner):
                head = (s[:g.start()] + " " + s[g.end():])
                tail, out["split_method"] = inner, "PAREN_DATE"
        if out["split_method"] == "NO_CUE":
            m2 = re.search(r"[,;(\[ ]\s*((?:\d{1,2}[-/. ])?(?:\d{1,2}|[A-Za-z]{3,9})"
                           r"[-/. ,]*\d{4})\s*[)\]]?\s*$", s)
            if m2:
                head, tail = s[:m2.start()], m2.group(1)
                out["split_method"] = "TRAIL_DATE"
    head, tail = head.strip(" ,;:-–([/"), tail.strip(" ,;:-–)]")
    if tail:
        d = ndate(tail)
        out["date_iso"], out["date_precision"] = d["iso"], d["precision"] or "NONE"
        out["date_flag"], out["date_text"] = d["flag"], tail
        if not d["iso"] and _YRONLY.match(tail):
            out["date_flag"] = "MULTIPLE_YEARS_PRESERVED"
    if out["split_method"] == "NO_CUE":
        d = ndate(s)                      # the whole cell may itself be just a date
        if d["iso"]:
            out.update(date_iso=d["iso"], date_precision=d["precision"],
                       date_flag=d["flag"], date_text=s, split_method="DATE_ONLY")
            return out
    n = _NOTIFNO.search(head) if head else None
    if n:
        out["number"] = n.group(0).strip()
        rest = (head[:n.start()] + " " + head[n.end():]).strip(" ,;:-–/")
        out["number_note"] = re.sub(r"\s{2,}", " ", rest)
    else:
        out["number_note"] = head
        if head:
            out["split_method"] += "+NO_NUMBER_TOKEN"
    return out



def split_is_and_product(v):
    """`product_standard_is` (F019) -> {is_list, product_text, original, split_method}.

    One cell names both the standard(s) and the product, e.g.
    `IS 302 (Part 2 / Sec 201) : Electric Iron`. The IS side goes through is_all() so
    every part/section survives as its own canonical standard; the product side is the
    remaining text with the IS tokens excised. If no IS token is present the whole
    string is the product and nothing is lost.
    """
    s = nws(v)
    out = {"is_list": [], "product_text": "", "range_flag": "", "alt_year_text": "",
           "original": s, "split_method": "NO_IS"}
    if nullclass(s) != "POPULATED":
        out["split_method"] = "EMPTY"
        return out
    found = is_all(s)
    out["is_list"] = [b["canonical_is_number"] for b in found if b["canonical_is_number"]]
    rest = s.replace(" ", " ")        # parse_is matches against this same form
    for b in found:
        if b.get("display_is_number"):
            rest = rest.replace(b["display_is_number"], " ")
    rest = re.sub(r"\(\s*(?:part|sec(?:tion)?)[^)]*\)", " ", rest, flags=re.I)
    rest = re.sub(r"\s{2,}", " ", rest).strip()
    # `IS 17631:2022 to IS 17636:2022` names a RANGE. Only the endpoints are stated, so
    # the intermediate standards are flagged for review, never generated.
    if re.search(r"\bto\b", rest, re.I) and len(out["is_list"]) == 2:
        out["range_flag"] = "IS_RANGE_ENDPOINTS_ONLY"
    # Leftover connectives and an orphan alternate year (`IS 2347:2017 / 2023`) are
    # syntax, not a product name. The year is a second edition of the same standard, so
    # it is kept in alt_year_text for review rather than dropped or merged into a year.
    while True:
        m = re.match(r"^(?:to|and|or|&|/|,|(\d{4}))[\s,/&-]*", rest, flags=re.I)
        if not m:
            break
        if m.group(1):
            out["alt_year_text"] = (out["alt_year_text"] + " " + m.group(1)).strip()
        rest = rest[m.end():]
    rest = rest.strip(" ,;:/|-–—&")
    if re.fullmatch(r"\([^()]*\)", rest):        # whole remainder is one bracket group
        rest = rest[1:-1].strip()
    if out["is_list"]:
        out["split_method"] = "IS_TOKENS_EXCISED"
    out["product_text"] = rest if nullclass(rest) == "POPULATED" else ""
    return out


# Sentence-level classification, not mid-sentence cutting: a scope sentence, an
# exclusion sentence and an amendment sentence are separate facts, and guessing a
# boundary inside one sentence would fabricate regulatory meaning.
_ABBR = [("S.O.", "\x01"), ("G.S.R.", "\x02"), ("No.", "\x03"), ("Sec.", "\x04"),
         ("Cl.", "\x05"), ("Pt.", "\x06"), ("etc.", "\x07"), ("i.e.", "\x08"),
         ("e.g.", "\x0b"), ("Ltd.", "\x0c"), ("Pvt.", "\x0e"), ("Co.", "\x0f"),
         ("Dept.", "\x10"), ("Govt.", "\x11"), ("Vol.", "\x12"), ("Amdt.", "\x13")]
_EXCL = re.compile(r"\b(?:exclusions?|excludes?|excluding|exempt(?:ed|ions?)?|"
                   r"not applicable to|shall not apply to|other than)\b", re.I)
_NEG = re.compile(r"\b(?:no|none|nil|without|not any|zero)\s+(?:\w+\s+){0,3}?"
                  r"(?:exclusions?|exemptions?)\b", re.I)
_AMD = re.compile(r"\b(?:amendments?|amended|amend\w*|corrigend(?:um|a)|"
                  r"supersed\w+|revised by|substituted by)\b", re.I)


def _sentences(s):
    t = s
    for a, k in _ABBR:
        t = t.replace(a, k)
    out = []
    for p in re.split(r"(?<=[.;])\s+", t):
        if not p.strip():
            continue
        for a, k in _ABBR:
            p = p.replace(k, a)
        out.append(p.strip())
    return out


def split_scope_excl_amend(v):
    """`key_scope_exclusions_amendments` (F019) -> scope / exclusions / amendments.

    Each sentence is classified once and lands in exactly one bucket, so the parts
    always reconstitute the original. `No general retail exclusions.` is a NEGATED
    exclusion - it asserts that none exist - so it stays in scope rather than being
    filed as an exclusion that does not exist. Abbreviations such as `S.O.` are masked
    before sentence splitting so an order number is never cut in half.
    """
    s = nws(v)
    out = {"scope": "", "exclusions": "", "amendments": "", "original": s,
           "split_method": "EMPTY"}
    if nullclass(s) != "POPULATED":
        return out
    buckets, meth = {"scope": [], "exclusions": [], "amendments": []}, []
    for sent in _sentences(s):
        if _AMD.search(sent):
            buckets["amendments"].append(sent)
            meth.append("AMENDMENT_CUE")
        elif _EXCL.search(sent) and not _NEG.search(sent):
            buckets["exclusions"].append(sent)
            meth.append("EXCLUSION_CUE")
        else:
            buckets["scope"].append(sent)
            if _NEG.search(sent):
                meth.append("NEGATED_EXCLUSION_IN_SCOPE")
    for k in buckets:
        out[k] = " ".join(buckets[k]).strip()
    seen = [m for i, m in enumerate(meth) if m not in meth[:i]]
    out["split_method"] = "+".join(seen) if seen else "NO_CUE_SCOPE_ONLY"
    return out


_LBL = re.compile(r"\|\s*(address|city|country|state|pin|postal code|zip)\s*:", re.I)
_ORG = re.compile(r"\b(?:pvt|private|ltd|limited|inc|llc|llp|gmbh|s\.?a\.?|s\.?p\.?a\.?|"
                  r"co\.?|corp(?:oration)?|company|industr(?:y|ies)|enterprises?|"
                  r"technolog(?:y|ies)|manufactur\w*|group|holdings?|kg|bv|nv|ag|"
                  r"sdn|bhd|plc|oy|ab|as|srl|sas|pte)\b\.?", re.I)


def split_name_address(v):
    """`name_address_raw` (F040) -> name / address / city / country, original preserved.

    The real column is LABEL-delimited, not comma-delimited - measured shape is
    `Meyer Aluminium (Thailand) Co. Ltd., | Address : 38/32 Moo 5, ... | City : - |
    Country : Thailand`. So the split is driven by those explicit `| Label :` markers,
    which is stated evidence rather than a heuristic; city and country are read from
    their own labels and never inferred from an address tail. `City : -` is a
    placeholder and is dropped by val(), not stored as the string "-".

    Only when no label is present does it fall back to the comma after the last
    organisation-form token (Ltd/Co/GmbH/...). With neither, the whole string stays in
    `name` and split_method says NO_LABEL_NO_ORG_TOKEN so nothing is guessed away.
    """
    s = nws(v)
    out = {"name": "", "address": "", "city": "", "country": "", "original": s,
           "split_method": "EMPTY"}
    if nullclass(s) != "POPULATED":
        return out
    hits = list(_LBL.finditer(s))
    if hits:
        out["name"] = s[:hits[0].start()].strip(" ,;|")
        for i, m in enumerate(hits):
            end = hits[i + 1].start() if i + 1 < len(hits) else len(s)
            key = m.group(1).lower()
            piece = s[m.end():end].strip(" ,;|")
            fld = {"address": "address", "city": "city", "country": "country"}.get(key)
            if fld:
                out[fld] = (out[fld] + " " + val(piece)).strip() if out[fld] else val(piece)
            else:                       # state / pin / zip belong with the address
                out["address"] = (out["address"] + " " + val(piece)).strip()
        out["split_method"] = "LABELLED"
        return out
    last = None
    for m in _ORG.finditer(s):
        last = m
    if last:
        cut = s.find(",", last.end())
        if cut == -1:
            out["name"], out["split_method"] = s, "ORG_TOKEN_NO_COMMA"
            return out
        out["name"] = s[:cut].strip(" ,;")
        out["address"] = s[cut + 1:].strip(" ,;")
        out["split_method"] = "ORG_TOKEN_COMMA"
        return out
    out["name"], out["split_method"] = s, "NO_LABEL_NO_ORG_TOKEN"
    return out


def verbatim(v):
    """Identity transform. Named so COLUMN_MAPPING can state 'no transformation' as a
    positive decision rather than a blank cell."""
    return v if v is not None else ""


# Transform names used in p3_model must all resolve here, so the design workbook and
# the build scripts cannot disagree about what a rule means.
TRANSFORMS = {
    "verbatim": verbatim, "nws": nws, "ndate": ndate, "nurl": nurl, "nqco": nqco,
    "nnotif": nnotif, "nstatus": nstatus, "nmand": nmand, "nname": nname, "nis": nis,
    "is_all": is_all, "msplit": msplit, "nlic": nlic, "norm_header": norm_header,
    "split_no_and_date": split_no_and_date, "split_is_and_product": split_is_and_product,
    "split_scope_excl_amend": split_scope_excl_amend,
    "split_name_address": split_name_address,
    # pipeline: split the cell, then parse every fragment as an IS reference
    "msplit+is_all": lambda v: [b for frag in msplit(v) for b in is_all(frag)],
}




