"""Creates small synthetic test documents (PDF/DOCX/XLSX/TXT/PDF-image-no-OCR)
for the Phase-6 test suite. Run once: python tests/make_fixtures.py"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
FIX = os.path.join(HERE, "fixtures")
os.makedirs(FIX, exist_ok=True)


def pdf_with_text(path, lines):
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    text = "\n".join(lines)
    page.insert_text((72, 72), text, fontsize=11)
    doc.save(path)
    doc.close()


def calibration_pdf():
    pdf_with_text(os.path.join(FIX, "calibration_certificate.pdf"), [
        "ACME Calibration Laboratory",
        "CALIBRATION CERTIFICATE",
        "Certificate No: CC-2026-0042",
        "Instrument ID: MCH-021",
        "Instrument: Digital Force Gauge",
        "Calibration Date: 12/03/2026",
        "Valid Until: 12/03/2027",
        "Laboratory: ACME Calibration Lab, Pune",
        "Traceable to NIST standards",
    ])


def calibration_expired_pdf():
    pdf_with_text(os.path.join(FIX, "calibration_expired.pdf"), [
        "CALIBRATION CERTIFICATE",
        "Certificate No: CC-2023-0007",
        "Instrument ID: MCH-002",
        "Calibration Date: 01/03/2023",
        "Valid Until: 01/03/2024",
    ])


def fixed_validity_pdf():
    pdf_with_text(os.path.join(FIX, "fixed_validity.pdf"), [
        "CALIBRATION CERTIFICATE",
        "Certificate No: CC-2026-0100",
        "Instrument ID: MCH-021",
        "Calibration Date: 12/03/2026",
        "Valid Until: 12/03/2029",
    ])


def vague_calibration_txt():
    with open(os.path.join(FIX, "vague_calibration.txt"), "w",
              encoding="utf-8") as f:
        f.write("Equipment calibrated regularly by our team.\n"
                "We maintain calibration practices.\n")


def test_report_pdf():
    pdf_with_text(os.path.join(FIX, "test_report.pdf"), [
        "BIS RECOGNIZED TESTING LABORATORY",
        "TEST REPORT",
        "Product Model: ErgoChair Pro",
        "Test Name: Stability test",
        "Test Method: IS 17631",
        "Tested on: 05/06/2026",
        "Result: PASS",
        "Laboratory: National Test House, Mumbai",
    ])


def factory_docx():
    import docx
    d = docx.Document()
    d.add_paragraph("FACTORY DOCUMENT")
    d.add_paragraph("Factory Name: Supreme Chairs Manufacturing Unit")
    d.add_paragraph("Factory Address: Plot 21, MIDC, Pune 411019")
    d.add_paragraph("Product: Office work chairs")
    t = d.add_table(rows=2, cols=2)
    t.cell(0, 0).text = "Machinery"
    t.cell(0, 1).text = "Hydraulic press, welding station"
    t.cell(1, 0).text = "Capacity"
    t.cell(1, 1).text = "500 units per day"
    d.save(os.path.join(FIX, "factory_details.docx"))


def machinery_xlsx():
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Equipment"
    ws.append(["Machine Name", "Quantity"])
    ws.append(["CNC bending machine", 2])
    ws.append(["Hydraulic press 40T", 1])
    ws.append(["Powder coating booth", 1])
    wb.save(os.path.join(FIX, "machinery_list.xlsx"))


def raw_material_txt():
    with open(os.path.join(FIX, "raw_material.txt"), "w",
              encoding="utf-8") as f:
        f.write("MATERIAL TEST CERTIFICATE\n"
                "Material Name: Cold rolled steel\n"
                "Grade: CR2\n"
                "Chemical Composition: C 0.10, Mn 0.45\n")


def conflicting_validity_pdf():
    pdf_with_text(os.path.join(FIX, "conflicting_validity.pdf"), [
        "CALIBRATION CERTIFICATE",
        "Certificate No: CC-2026-0055",
        "Instrument ID: MCH-021",
        "Calibration Date: 12/03/2026",
        "Valid Until: 12/03/2030",
    ])


if __name__ == "__main__":
    calibration_pdf()
    calibration_expired_pdf()
    fixed_validity_pdf()
    vague_calibration_txt()
    test_report_pdf()
    factory_docx()
    machinery_xlsx()
    raw_material_txt()
    conflicting_validity_pdf()
    print("fixtures written to %s" % FIX)
    for f in sorted(os.listdir(FIX)):
        print("  %s (%d bytes)" % (f, os.path.getsize(os.path.join(FIX, f))))
