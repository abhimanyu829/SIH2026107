"""Tests 1-5: PDF / DOCX / XLSX extraction, classification, evidence fields."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _base import FIXTURES, run_cases  # noqa: E402


def t_pdf():
    from documents.extraction import extract
    pages, meta = extract(os.path.join(FIXTURES, "calibration_certificate.pdf"))
    if not pages or meta.get("chars", 0) < 30:
        return "PDF text extraction failed: %s" % meta
    if pages[0].to_dict()["page"] != 1:
        return "page numbering wrong"
    if "CALIBRATION" not in pages[0].text.upper():
        return "expected calibration content missing"
    return ""


def t_docx():
    from documents.extraction import extract
    pages, meta = extract(os.path.join(FIXTURES, "factory_details.docx"))
    if not pages or meta.get("chars", 0) < 30:
        return "DOCX extraction failed: %s" % meta
    joined = " ".join(p.text for p in pages)
    if "Supreme Chairs" not in joined:
        return "paragraph text missing"
    if "Hydraulic press" not in joined:
        return "table text missing (tables must be extracted)"
    return ""


def t_xlsx():
    from documents.extraction import extract
    pages, meta = extract(os.path.join(FIXTURES, "machinery_list.xlsx"))
    joined = " ".join(p.text for p in pages)
    if "CNC bending machine" not in joined:
        return "XLSX cell text missing"
    if "Sheet: Equipment" not in joined:
        return "sheet name missing"
    return ""


def t_txt():
    from documents.extraction import extract
    pages, meta = extract(os.path.join(FIXTURES, "vague_calibration.txt"))
    if not pages or "calibrated" not in pages[0].text:
        return "TXT extraction failed"
    return ""


def t_ocr_fallback():
    """OCR fallback: an image file with no text layer must degrade gracefully
    (no crash, clear status), never a hard error. Both 'OCR unavailable' and
    'no usable text' are graceful outcomes for a blank image."""
    from documents.extraction import extract
    import pymupdf
    img = os.path.join(FIXTURES, "_t_ocr_probe.png")
    doc = pymupdf.open()
    page = doc.new_page()
    pix = page.get_pixmap(dpi=50)
    pix.save(img)
    doc.close()
    try:
        pages, meta = extract(img)
        err = meta.get("error") or ""
        if err and not any(s in err for s in ("OCR unavailable",
                                               "no usable text",
                                               "OCR produced")):
            return "unexpected error: %s" % err
        return ""
    finally:
        os.remove(img)


def t_classification():
    from documents.classification import classify_text
    cat, conf, _ = classify_text("CALIBRATION CERTIFICATE\nInstrument ID: X\n"
                                 "Valid Until: 2027")
    if cat != "CALIBRATION_CERTIFICATE":
        return "calibration classified as %s" % cat
    cat, _, _ = classify_text("TEST REPORT\nTest Name: Stability\nResult: PASS")
    if cat != "TEST_REPORT":
        return "test report classified as %s" % cat
    cat, _, _ = classify_text("Factory Name: X\nFactory Address: Y\n"
                              "Production Capacity")
    if cat != "FACTORY_DOCUMENT":
        return "factory classified as %s" % cat
    cat, _, _ = classify_text("random text about nothing")
    if cat != "OTHER":
        return "OTHER expected, got %s" % cat
    return ""


def t_evidence():
    from documents import classification, evidence
    from documents.extraction import extract
    pages, meta = extract(os.path.join(FIXTURES, "calibration_certificate.pdf"))
    doc = {"filename": "calibration_certificate.pdf", "pages":
           [p.to_dict() for p in pages]}
    doc["category"] = classification.classify(doc)["category"]
    items = evidence.extract_evidence(doc)
    fields = {i["field"] for i in items}
    for need in ("instrument_id", "certificate_number", "calibration_date",
                 "validity_date"):
        if need not in fields:
            return "field %s not extracted (got %s)" % (need, fields)
    if not all(i.get("page") for i in items):
        return "evidence missing page citation"
    return ""


if __name__ == "__main__":
    ok = run_cases("document_tests", [
        ("pdf_extraction", t_pdf),
        ("docx_extraction", t_docx),
        ("xlsx_extraction", t_xlsx),
        ("txt_extraction", t_txt),
        ("ocr_fallback_graceful", t_ocr_fallback),
        ("classification_rules", t_classification),
        ("evidence_extraction", t_evidence),
    ])
    sys.exit(0 if ok else 1)
