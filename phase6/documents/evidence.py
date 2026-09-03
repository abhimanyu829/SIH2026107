"""Evidence extraction: regex field extraction per document category.

Extracts only fields useful for compliance checking (spec section 8). Each
evidence item carries page + surrounding text so decisions can cite it.
"""
import re

# ---- field patterns per category --------------------------------------------
# (field, [regex patterns with one capture group])
DATE_RE = r"(\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4}|\d{4}-\d{2}-\d{2})"

FIELD_PATTERNS = {
    "CALIBRATION_CERTIFICATE": [
        ("instrument_id", [r"instrument\s*(?:id|no|number)?\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-/]{2,20})"]),
        ("certificate_number", [r"certificate\s*(?:no|number)?\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-/]{2,20})"]),
        ("calibration_date", [r"calibrat\w*\s*date\s*[:\-]?\s*" + DATE_RE]),
        ("validity_date", [r"valid\s*(?:until|till|upto|up to|to)?\s*[:\-]?\s*" + DATE_RE,
                           r"next\s*calibration\s*(?:due)?\s*[:\-]?\s*" + DATE_RE]),
        ("laboratory_name", [r"(?:calibration\s*)?laboratory\s*[:\-]?\s*([A-Za-z][A-Za-z0-9 .&()\-]{3,60})",
                             r"lab(?:oratory)?\s*name\s*[:\-]?\s*([A-Za-z][A-Za-z0-9 .&()\-]{3,60})"]),
    ],
    "TEST_REPORT": [
        ("test_name", [r"test\s*(?:name|title)?\s*[:\-]?\s*([A-Za-z][A-Za-z ()/-]{3,60})"]),
        ("test_date", [r"test(?:ed)?\s*(?:on|date)?\s*[:\-]?\s*" + DATE_RE]),
        ("result", [r"result\s*[:\-]?\s*(pass(?:ed)?|fail(?:ed)?|conform(?:s|ing|ed)?|ok|not ok|pass/fail)",
                    r"\b(pass(?:ed)?|fail(?:ed)?|conform(?:s|ing|ed)?)\b(?=\s*$|\s*\|)"]),
        ("product_model", [r"(?:product|model|sample)\s*(?:name|no|id)?\s*[:\-]?\s*([A-Za-z0-9][A-Za-z0-9 ()/-]{2,60})"]),
        ("laboratory_name", [r"laboratory\s*[:\-]?\s*([A-Za-z][A-Za-z0-9 .&()\-]{3,60})"]),
    ],
    "FACTORY_DOCUMENT": [
        ("factory_name", [r"factory\s*(?:name|unit)?\s*[:\-]?\s*([A-Za-z][A-Za-z0-9 .&()\-]{3,60})",
                          r"manufacturer\s*[:\-]?\s*([A-Za-z][A-Za-z0-9 .&()\-]{3,60})"]),
        ("product_name", [r"product\s*(?:name|manufactured)?\s*[:\-]?\s*([A-Za-z][A-Za-z0-9 ()/-]{3,60})"]),
        ("address", [r"(?:factory|works|unit)\s*address\s*[:\-]?\s*([A-Za-z0-9][A-Za-z0-9 ,.\-()/]{5,120})"]),
        ("gst_number", [r"GST(?:IN)?\s*(?:no|number)?\s*[:\-]?\s*([0-9A-Z]{15})"]),
        ("capacity", [r"(?:production\s*)?capacity\s*[:\-]?\s*([0-9][0-9 ,.]*\s*(?:units|pcs|pieces|per|nos)[A-Za-z ]{0,12})"]),
        ("machinery", [r"(?:machinery|machines|equipment)\s*[:\-]?\s*([A-Za-z0-9][A-Za-z0-9 ,.()/-]{3,80})"]),
    ],
    "QC_DOCUMENT": [
        ("qc_plan_reference", [r"qc\s*plan\s*(?:no|ref)?\s*[:\-]?\s*([A-Z0-9][A-Z0-9\-/]{2,20})"]),
        ("inspection_stage", [r"(?:in[- ]process|final|incoming)\s*inspection", ]),
        ("quality_standard", [r"quality\s*(?:standard|policy)?\s*[:\-]?\s*([A-Za-z][A-Za-z0-9 ./-]{3,60})"]),
    ],
    "RAW_MATERIAL_DOCUMENT": [
        ("material_grade", [r"grade\s*[:\-]?\s*([A-Za-z0-9][A-Za-z0-9 .\-]{1,20})"]),
        ("composition", [r"chemical\s*composition\s*[:\-]?\s*(.{5,120})"]),
        ("material_name", [r"material\s*(?:name|type)?\s*[:\-]?\s*([A-Za-z][A-Za-z0-9 ()/-]{3,60})"]),
    ],
    "PROCESS_DOCUMENT": [
        ("process_name", [r"process\s*(?:name|step|stage)?\s*[:\-]?\s*([A-Za-z][A-Za-z0-9 ()/-]{3,60})"]),
        ("process_parameter", [r"(?:temperature|pressure|time|humidity|speed)\s*[:\-]?\s*([0-9][0-9 .%A-Za-z]{0,20})"]),
    ],
    "MACHINERY_DOCUMENT": [
        ("machine_name", [r"(?:machine|equipment)\s*(?:name|no)?\s*[:\-]?\s*([A-Za-z][A-Za-z0-9 ()/-]{3,60})"]),
        ("equipment_list", [r"(?:equipment|machinery)\s*list\s*[:\-]?\s*(.{5,200})"]),
    ],
}
# Categories without patterns still produce "presence" evidence via generic scan.
GENERIC_FIELDS = [
    ("mentioned_date", [DATE_RE]),
    ("standard_reference", [r"\bIS\s*[:\-]?\s*\d{2,6}(?:[:\-]\d{4})?\b"]),
]


def _page_confidence(field, match_len, line_len):
    """Rough extraction confidence: short, cleanly-labeled matches are better."""
    base = 0.75
    if field.endswith(("_date", "validity_date")):
        base = 0.9
    if match_len and line_len and match_len / max(line_len, 1) < 0.5:
        base += 0.05
    return round(min(0.95, base), 2)


def extract_evidence(document):
    """One classified+extracted document -> list of evidence items.

    Evidence model (spec section 11): evidence_id, document, type, field,
    value, page, text, confidence.
    """
    pages = document.get("pages", [])
    category = document.get("category", "OTHER")
    patterns = FIELD_PATTERNS.get(category, []) + (
        [] if category != "OTHER" else GENERIC_FIELDS)
    if not patterns:                     # any category with no rules -> generic
        patterns = GENERIC_FIELDS

    out, n = [], 0
    seen = set()
    for page in pages:
        text = page.get("text", "")
        for line_no, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            for field, regexes in patterns:
                for rx in regexes:
                    try:
                        m = re.search(rx, line, re.IGNORECASE)
                    except re.error:
                        continue
                    if not m:
                        continue
                    value = (m.group(1) if m.groups() else m.group(0)).strip()
                    key = (field, value.lower())
                    if not value or key in seen:
                        continue
                    seen.add(key)
                    n += 1
                    out.append({
                        "evidence_id": "EV-%03d" % n,
                        "document": document.get("filename", ""),
                        "document_id": document.get("document_id", ""),
                        "type": category,
                        "field": field,
                        "value": value[:200],
                        "page": page.get("page", 1),
                        "text": line.strip()[:240],
                        "confidence": _page_confidence(field, len(value), len(line)),
                    })
                    break
    return out


def has_sufficient_detail(evidence, category):
    """The UNKNOWN example (spec section 15): a calibration mention without
    date/instrument/certificate/validity is NOT sufficient evidence."""
    if category == "CALIBRATION_CERTIFICATE":
        needed = {"instrument_id", "certificate_number", "calibration_date",
                  "validity_date"}
        return any(e["field"] in needed for e in evidence)
    return True
