"""Phase 1 helpers: normalisation, type inference, semantic typing, domain scoring.
READ-ONLY. Never writes to or mutates any source file."""
import re

# Values that LOOK populated but carry no information. Counted separately from
# true nulls because the spec forbids using them as substitutes for NULL.
PLACEHOLDER = {
    "na", "n/a", "n.a.", "n.a", "none", "null", "nil", "-", "--", "---", "nan",
    "not available", "notavailable", "not applicable", "notapplicable", "unknown",
    "tbd", "to be decided", "?", "n/f", "not found", "not specified", "blank",
}

IS_RE = re.compile(r"\bIS[\s:/\-]*(?:IEC[\s:/\-]*)?(\d{2,5})", re.I)
IS_FULL_RE = re.compile(r"\bIS(?:/IEC)?\s*\d{2,5}(?:\s*\(?\s*Part\s*\d+[A-Za-z]?\)?)?"
                        r"(?:\s*[:\-]\s*(?:19|20)\d{2})?", re.I)
QCO_RE = re.compile(r"\bQCO\b|quality\s+control\s+order", re.I)
URL_RE = re.compile(r"https?://", re.I)
DATE_RE = re.compile(r"^\s*(\d{1,4}[/\-.]\d{1,2}[/\-.]\d{1,4})"
                     r"|^\s*\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}\s*$")
INT_RE = re.compile(r"^[+-]?\d+$")
FLOAT_RE = re.compile(r"^[+-]?(\d+\.\d*|\.\d+|\d+)([eE][+-]?\d+)?$")
BOOL_VALS = {"true", "false", "yes", "no", "y", "n", "0", "1"}
MULTI_SEP = re.compile(r"[;,|]|\band\b")


def norm_header(h):
    if h is None:
        return ""
    s = str(h).replace("\u00a0", " ").replace("\ufeff", "").strip().lower()
    s = re.sub(r"[^0-9a-z]+", "_", s)
    return re.sub(r"_+", "_", s).strip("_")


def is_empty(v):
    """True null / genuinely absent."""
    if v is None:
        return True
    if isinstance(v, float) and v != v:
        return True
    return str(v).strip() == ""


def is_placeholder(v):
    if is_empty(v):
        return False
    return str(v).strip().lower() in PLACEHOLDER


def norm_cell(v):
    """Canonical form for row-hash comparison (used again in Phase 2)."""
    if is_empty(v):
        return ""
    s = str(v).replace("\u00a0", " ").strip()
    s = re.sub(r"\s+", " ", s)
    if s.lower() in PLACEHOLDER:
        return ""
    if INT_RE.match(s):
        return str(int(s))
    if FLOAT_RE.match(s):
        f = float(s)
        return str(int(f)) if f == int(f) else repr(round(f, 10))
    return s.lower()


def infer_type(vals):
    """vals: non-empty raw values."""
    if not vals:
        return "empty"
    kinds = set()
    for v in vals:
        if isinstance(v, bool):
            kinds.add("bool"); continue
        if hasattr(v, "year") and hasattr(v, "month"):
            kinds.add("datetime"); continue
        if isinstance(v, int):
            kinds.add("int"); continue
        if isinstance(v, float):
            kinds.add("float"); continue
        s = str(v).strip()
        if URL_RE.search(s):
            kinds.add("url")
        elif INT_RE.match(s):
            kinds.add("int")
        elif FLOAT_RE.match(s):
            kinds.add("float")
        elif DATE_RE.match(s):
            kinds.add("date")
        elif s.lower() in BOOL_VALS:
            kinds.add("bool")
        else:
            kinds.add("string")
    if len(kinds) == 1:
        return kinds.pop()
    if kinds <= {"int", "float"}:
        return "float"
    if kinds <= {"int", "float", "bool"}:
        return "numeric_mixed"
    if kinds <= {"date", "datetime"}:
        return "datetime"
    if kinds <= {"url", "string"}:
        return "string"
    return "mixed(" + "|".join(sorted(kinds)) + ")"


def multivalue_ratio(vals):
    """Fraction of values that look like a packed list."""
    if not vals:
        return 0.0
    n = 0
    for v in vals:
        s = str(v)
        if len(s) < 3:
            continue
        if len(MULTI_SEP.findall(s)) >= 1 and len(s.split()) >= 2:
            n += 1
    return n / len(vals)


def is_number_hits(vals):
    return sum(1 for v in vals if IS_RE.search(str(v)))


# ---------------------------------------------------------------- semantic type
# Ordered: first matching rule wins. (regex on normalised header, label)
SEM_RULES = [
    (r"^sha_?256$|^document_hash$|_hash$", "CONTENT_HASH"),
    (r"^(source_url|source_urls)$", "SOURCE_URL"),
    (r"(document_url|download_url|notification_document_url|scope_url)", "DOCUMENT_URL"),
    (r"(^url$|_url$|^attempted_source_url$)", "URL"),
    (r"^(is_number|is|raw_is_number|canonical_is_number|display_is_number|standard_no_raw)$", "IS_NUMBER"),
    (r"(related_is|tested_is_numbers|is_numbers|superseded_standard|superseding_standard)", "IS_RELATIONSHIP"),
    (r"^standard_id$", "STANDARD_ID"),
    (r"^(qco_id)$", "QCO_ID"),
    (r"(qco|quality_control_order)", "QCO_REFERENCE"),
    (r"^(scheme_id|scheme_code|scheme_record_id|scheme_id_code)$", "SCHEME_ID"),
    (r"^(scheme|scheme_name|scheme_label|scheme_type|schemes|certification_scheme.*)$", "SCHEME_NAME"),
    (r"^(certification_type)$", "CERTIFICATION_TYPE"),
    (r"^(mandatory.*|.*mandatory_status|mandatory_voluntary)$", "MANDATORY_FLAG"),
    (r"^lab_id$", "LAB_ID"),
    (r"^(lab_name|lab_code|lab_type)$", "LAB_IDENTITY"),
    (r"(laboratory_requirement|laboratory_testing|testing_facilities)", "LAB_CAPABILITY"),
    (r"^(centre_id|centre_code)$", "CENTRE_ID"),
    (r"^centre_name$", "CENTRE_NAME"),
    (r"^(product_id)$", "PRODUCT_ID"),
    (r"^(product|product_name|related_product|alternate_names|variety_brand_raw)$", "PRODUCT_NAME"),
    (r"^(test_id)$", "TEST_ID"),
    (r"^(test_name|test_parameter|parameter)$", "TEST_NAME"),
    (r"^(test_method|method|method_standard|test_method_standard)$", "TEST_METHOD"),
    (r"^(acceptance_criteria)$", "ACCEPTANCE_CRITERIA"),
    (r"^(clause|section|page)$", "DOC_LOCATOR"),
    (r"^(effective_date|implementation_date|effective_implementation_d.*)$", "EFFECTIVE_DATE"),
    (r"(validity|expiry|reaffirmation|revision_date|publication_date|release_date|"
     r"notification_date|retrieval_timestamp|retrieved_at|detected_at|timestamp|"
     r"suspended_cancelled_date|amendment_date|^date$|_date$|validity_date_raw)", "DATE"),
    (r"^(year|standard_year)$", "YEAR"),
    (r"^(country)$", "COUNTRY"),
    (r"^(state)$", "STATE"),
    (r"^(city|district|region)$", "LOCALITY"),
    (r"^(pin|pincode|pin_code)$", "PINCODE"),
    (r"^(address|name_address_raw|factory)$", "ADDRESS"),
    (r"(contact|phone|mobile|email)", "CONTACT"),
    (r"(fee|fees|charge|testing_charge|fee_structure)", "FEE"),
    (r"^(status|record_status|.*_status|outcome|dedup_status|verification_status)$", "STATUS"),
    (r"^(missing_reason|reason|resolution_needed|error_type)$", "MISSING_REASON"),
    (r"^(source_id|source_type|source_title|scraper_engine|extraction_method|"
     r"http_status|content_type|bytes|retry_count|confidence|evidence_text)$", "PROVENANCE_META"),
    (r"^(manufacturer_id|licence|licence_status|cml_no_raw|cml_no)$", "LICENCE_IDENTITY"),
    (r"^(manufacturer|notified_by|issuing_authority|ministry|department)$", "AUTHORITY_OR_PARTY"),
    (r"^(question)$", "FAQ_QUESTION"),
    (r"^(answer)$", "FAQ_ANSWER"),
    (r"^(title|.*_title|subject|order_title|manual_title|guideline_title|"
     r"table_caption|qco_name)$", "TITLE"),
    (r"^(category|subcategory|group|entity_type|type|document_type|metal|"
     r"centre_type|field_name)$", "CATEGORY"),
    (r"^(keywords|scope|exclusions|description|applicability|remarks|notes|"
     r"specific_requirement|requirements|implementation_instructions)$", "DESCRIPTIVE_TEXT"),
    (r"^(.*_count|manufacturer_count|licence_count|page_count|sample_size|"
     r"sr_no|s_no|^id$)$", "NUMERIC_OR_COUNT"),
    (r"_id$|^record_id$|^conflict_id$|^faq_id$|^order_id$|^amendment_id$|"
     r"^notification_id$|^manual_id$|^document_id$|^scope_id$", "PRIMARY_KEY_ID"),
]


def semantic_type(norm_name, dtype, vals, mv_ratio):
    for pat, label in SEM_RULES:
        if re.search(pat, norm_name):
            if label in ("IS_NUMBER",) and mv_ratio > 0.30 and is_number_hits(vals) > len(vals) * 0.5:
                return "IS_RELATIONSHIP"
            return label
    if dtype == "url":
        return "URL"
    if dtype in ("date", "datetime"):
        return "DATE"
    if vals and is_number_hits(vals) >= max(2, 0.6 * len(vals)):
        return "IS_RELATIONSHIP" if mv_ratio > 0.3 else "IS_NUMBER"
    if dtype in ("int", "float", "numeric_mixed"):
        return "NUMERIC_OR_COUNT"
    if vals and sum(len(str(v)) for v in vals) / len(vals) > 80:
        return "FREE_TEXT"
    if dtype == "empty":
        return "EMPTY_COLUMN"
    return "UNCLASSIFIED_STRING"


# ------------------------------------------------------------ domain taxonomy
def W(inner):
    """Boundary that treats '_' as a separator too.

    `\\b` is useless against filenames because '_' is a word character, so
    r"\\bfmcs\\b" does NOT match "bis_scheme_iv_fmcs.xlsx" and r"scheme_x\\b"
    does NOT match "bis_scheme_x_industrial.xlsx". This wrapper fixes that
    class of miss without loosening the pattern into substring matching.
    """
    return r"(?<![a-z0-9])(?:%s)(?![a-z0-9])" % inner


# Each domain: (header-signal regexes, value/filename-signal regexes)
# Header hits weigh 3, value hits 2, filename hits 2. Primary requires >= 5.
DOMAINS = {
 "01_KNOW_YOUR_STANDARD": (
   [r"^standard_id$", r"^is_number$|^is$|^is number$", r"reaffirmation", r"technical_committee",
    r"^revision$", r"superseding_standard", r"superseded_standard", r"amendment_number",
    r"^publication_date$", r"parent_entity", r"^part_section$"],
   [r"standards_details", r"standards_amendments", r"gazette", r"know_your_standard"]),
 "02_PRODUCTS": (
   [r"^product_id$", r"alternate_names", r"^subcategory$", r"^keywords$",
    r"related_is_numbers", r"related_qcos", r"related_schemes"],
   [r"products_details", r"products_full_information"]),
 "03_QCO": (
   [r"^qco_(id|no|number|name|reference)", r"quality_control_order", r"mandatory_status",
    r"^notification_(no|number)", r"^effective_date$", r"exclusions", r"qco_order"],
   [r"qco", r"quality control order", r"गुणवत्ता नियंत्रण", r"आदेश"]),
 "04_SCHEME_I": (
   [],
   [W(r"scheme[_\-. ]?(?:1|i)"), r"isi\s*mark"]),
 "05_SCHEME_II_CRS": (
   [],
   [W(r"scheme[_\-. ]?(?:2|ii)"), W("crs"), r"compulsory registration"]),
 "06_SCHEME_IV_COC": (
   [],
   [W(r"scheme[_\-. ]?(?:4|iv)"), r"certificate of conformity", W("coc")]),
 "07_SCHEME_X": (
   [],
   [W(r"scheme[_\-. ]?(?:x|10)"), W("eeqco"), r"omnibus technical regulation"]),
 "08_PRODUCT_SPECIFIC": (
   [r"factory_requirements", r"infrastructure_requirements", r"process_controls",
    r"conformity_assessment", r"competent_personnel", r"^eligibility$",
    r"required_documents", r"quality_control"],
   [r"standards_intelligence", r"scheme_mapping"]),
 "09_PRODUCT_MANUALS": (
   [r"^manual_id$", r"^manual_title$", r"sampling_guidelines", r"marking_requirements",
    r"raw_material_requirements", r"process_requirements"],
   [r"product_manual"]),
 "10_TESTING": (
   [r"^test_id$", r"^test_name$", r"^test_parameter$", r"acceptance_criteria",
    r"^test_method$", r"sampling_frequency", r"required_equipment", r"rejection_handling",
    r"^parameter$", r"^sample_size$"],
   [r"testing_master", r"testing_parameters", r"combined_testing"]),
 "11_CERTIFICATION_PROCESS": (
   [r"application_procedure", r"fee_structure", r"inspection_testing_norm",
    r"^applicability$", r"guideline_title", r"application_requirements", r"^air$"],
   [r"product_certifications", r"certification.*process|licensing procedure"]),
 "12_CERTIFICATION_FAQ": (
   [r"^faq_id$", r"^question$", r"^answer$"],
   [r"faq"]),
 "13_LAB_SERVICES": (
   [r"testing_charge", r"^capability$", r"scope_status", r"scope_validity"],
   [r"laboratory_scopes", r"lab.*services"]),
 "14_LIMS_LABS": (
   [r"^lab_id$", r"^lab_name$", r"^lab_code$", r"^lab_type$", r"accreditation_validity",
    r"recognition_status"],
   [r"laborator", r"recognized_lab", W("lims")]),
 "15_LIMS_IS_TEST": (
   [r"^scope_id$"],
   [r"laboratory_scopes"]),
 "16_ACT_RULES_REGULATIONS": (
   [r"^circular_id$", r"^circular_number$", r"^notification_id$", r"issuing_authority",
    r"implementation_instructions", r"related_amendment", r"^ministry$", r"^gazette"],
   [r"circular", r"gazette", r"notification", W(r"act|rules|regulation"),
    r"अधिसूचना", r"राजपत्र", r"एस\.?ओ\.?"]),
 "17_HALLMARKING_OVERVIEW": ([], [r"hallmark", W("huid"), r"assaying", r"हॉलमार्क"]),
 "18_HALLMARKING_FAQ": ([r"^question$", r"^answer$"], [r"hallmark.*faq"]),
 "19_HALLMARKING_ORDERS": (
   [r"^order_id$", r"^fineness$", r"^metal$", r"district_phase", r"geographical_applicability",
    r"^supersession$"],
   [r"hallmarking_order", r"mandatory_hallmarking"]),
 "20_HALLMARKING_CENTRES": (
   [r"^centre_id$", r"^centre_code$", r"^centre_name$", r"^centre_type$",
    r"recognition_status_raw", r"suspended_cancelled_date"],
   [r"hallmarking_centre", W("ahc"), r"assaying & hallmarking"]),
 "21_JEWELLER_REGISTRATION": ([], [r"jewell", r"registered jeweller", r"jeweller registration"]),
 "22_FMCS": (
   [r"^cml_no_raw$|^cml_no$", r"^manufacturer_id$", r"^country$", r"^licence_status$",
    r"manufacturer_count", r"licence_count", r"name_address_raw"],
   [W("fmcs"), r"foreign manufacturer"]),
}

OTHER_SIGNALS = [
  # Pure pipeline/meta artefacts: no BIS subject domain of their own.
  (r"provenance|source_inventory|extraction_log|unresolved_records|source_conflicts",
   "OTHER_RELEVANT", 9),
  # A document registry: carries real subject content too, so only a weak nudge.
  (r"official_documents", "OTHER_RELEVANT", 4),
]

# Scheme discrimination is value-driven: a generic `scheme_id` column is not
# evidence for any particular scheme. Longest tokens first (IV before II before I)
# so that "Scheme IV" is never counted as "Scheme I".
SCHEME_TOKENS = [
  (r"FMCS|FOREIGN MANUFACTURER", "22_FMCS"),
  (r"SCHEME\s*[-–—:_]?\s*IV(?![A-Z0-9])|SCHEME 4(?![A-Z0-9])|SCH[-_ ]?IV(?![A-Z0-9])",
   "06_SCHEME_IV_COC"),
  (r"SCHEME\s*[-–—:_]?\s*II(?![A-Z0-9])|SCHEME 2(?![A-Z0-9])|SCH[-_ ]?II(?![A-Z0-9])"
   r"|\bCRS\b|COMPULSORY REGISTRATION", "05_SCHEME_II_CRS"),
  (r"SCHEME\s*[-–—:_]?\s*X(?![A-Z0-9])|SCHEME 10(?![A-Z0-9])|SCH[-_ ]?X(?![A-Z0-9])"
   r"|\bEEQCO\b", "07_SCHEME_X"),
  (r"SCHEME\s*[-–—:_]?\s*I(?![IVX0-9])|SCHEME 1(?![0-9])|SCH[-_ ]?I(?![IVX0-9])"
   r"|ISI MARK", "04_SCHEME_I"),
]

# Which columns actually *identify* the scheme, and how authoritative each is.
# `certification_type` is deliberately absent: it names the MARK or the
# assessment route ("ISI Mark", "Certificate of Conformity"), not the scheme,
# and pooling it with the real identity columns is what made
# BIS_Schemes_Master_Scheme_2.xlsx look like Scheme I.
SCHEME_ID_COLS = [
  (r"^scheme(_(name|label|title))$", 3),
  (r"^(scheme|schemes|scheme_id|scheme_code|scheme_id_code|scheme_no|scheme_number"
   r"|scheme_record_id)$", 2),
  (r"^scheme_(type|status)$", 1),
]


def scheme_col_rank(norm_name):
    """Priority of a column as scheme *identity* evidence. 0 = not identity."""
    for pat, rank in SCHEME_ID_COLS:
        if re.search(pat, norm_name):
            return rank
    return 0


def _tally(vals):
    """(domain -> hit count, token_bearing_cells) for one column's values."""
    hits, bearing = {}, 0
    for v in vals:
        s = re.sub(r"\s+", " ", str(v)).upper()
        for pat, dom in SCHEME_TOKENS:
            if re.search(pat, s):
                hits[dom] = hits.get(dom, 0) + 1
                bearing += 1
                break          # first (most specific) token wins for this cell
    return hits, bearing


def dominant_scheme(scheme_cols, floor=0.60, min_hits=3):
    """Decide the scheme a sheet is *about*, from its scheme-identity columns.

    `scheme_cols`: list of (normalized_column_name, [values]).

    Ratios are computed over token-BEARING cells within a single column, never
    over every cell of every scheme-ish column. Token-free cells ("SCH-II",
    "Product Certification", "2") are structural noise, not counter-evidence,
    and pooling columns lets one column's label outvote the authoritative one.

    Returns (primary_domain, ratio, rank, [(other_domain, ratio), ...]) where the
    extras are domains that dominate a lower-ranked identity column - real but
    weaker evidence, e.g. a Scheme-IV file whose scheme_name says FMCS.
    """
    per_col = []
    for name, vals in scheme_cols:
        rank = scheme_col_rank(name)
        if not rank or not vals:
            continue
        hits, bearing = _tally(vals)
        if not hits:
            continue
        dom, n = max(hits.items(), key=lambda kv: kv[1])
        ratio = n / bearing
        if ratio >= floor and (n >= min_hits or n >= 0.5 * len(vals)):
            per_col.append((rank, n, dom, ratio))
    if not per_col:
        return None, 0.0, 0, []
    per_col.sort(key=lambda t: (-t[0], -t[1]))
    rank, _, top, top_ratio = per_col[0]
    extras, seen = [], {top}
    for _, _, dom, r in per_col[1:]:
        if dom not in seen:
            seen.add(dom)
            extras.append((dom, r))
    return top, top_ratio, rank, extras


def ev_label(p):
    """Readable evidence tag for a regex, with the W() guard scaffolding removed."""
    s = p.replace(r"(?<![a-z0-9])(?:", "").replace(r")(?![a-z0-9])", "")
    s = re.sub(r"\(\?[:!=<][^)]*\)|[\\^$\[\]{}]|\(\?|\\s\*|\\b", "", s)
    return re.sub(r"[()?*+]", "", s).strip("|_ ")[:26] or p[:26]


def _hit(p, text):
    """The actual matched substring - far more auditable than echoing the regex."""
    m = re.search(p, text)
    return None if not m else (re.sub(r"\s+", " ", m.group(0)).strip()[:26] or ev_label(p))


def score_domains(norm_headers, sample_text, filename, scheme_cols=()):
    fn = filename.lower()
    txt = sample_text.lower()
    out = {}
    for dom, (hpats, vpats) in DOMAINS.items():
        s, ev, matched = 0, [], set()
        for p in hpats:
            for h in norm_headers:
                # 3 points per DISTINCT header, not per pattern: two patterns
                # hitting the same header is one piece of evidence, not two.
                if re.search(p, h) and h not in matched:
                    matched.add(h)
                    s += 3; ev.append("hdr:" + h)
        for p in vpats:
            h = _hit(p, fn)
            if h:
                s += 2; ev.append("file~" + h)
                continue
            h = _hit(p, txt)
            if h:
                s += 2; ev.append("val~" + h)
        if s:
            out[dom] = (s, ev)
    dom, ratio, rank, extras = dominant_scheme(list(scheme_cols))
    if dom:
        # A dedicated scheme_name/scheme_id column is strong identity evidence (7).
        # A blended column (scheme_type, scheme_status) is weaker (5), so it can
        # no longer outrank a file's real subject-matter headers.
        s, ev = out.get(dom, (0, []))
        out[dom] = (s + (7 if rank >= 2 else 5),
                    ev + ["dominant_scheme_label=%.0f%%(col_rank=%d)" % (100 * ratio, rank)])
        for d2, r2 in extras:
            s2, ev2 = out.get(d2, (0, []))
            out[d2] = (s2 + 3, ev2 + ["secondary_scheme_label=%.0f%%" % (100 * r2)])
    for p, lab, w in OTHER_SIGNALS:
        if re.search(p, fn):
            s, ev = out.get(lab, (0, []))
            out[lab] = (s + w, ev + ["file~" + (_hit(p, fn) or ev_label(p))])
    return out


