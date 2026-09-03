"""Identifier verification against authoritative available data only.

Rules (spec):
1. Identifier format alone is NOT proof of validity.
2. Query authoritative available data (fmcs_master licences, hallmarking ids,
   document ids).
3. Return VALIDATED / NOT_FOUND / NOT_VERIFIED / CONTEXT_MISMATCH.
4. Never fabricate a result.
5. Preserve returned evidence.
"""
import re

from ._shared import supabase
from .registry import ToolResult, tool

# Recognized shapes (recognition only - NEVER treated as proof).
CML_RE = re.compile(r"^\d{5,7}$", re.I)                  # CML licence number
HUID_RE = re.compile(r"^[A-Z0-9]{6}$", re.I)              # hallmark unique id
REG_RE = re.compile(r"^RN/?\d{5,8}$", re.I)              # registration number


def _context_num(text):
    m = re.search(r"IS\s*[:\-]?\s*(\d{2,6})", text or "", re.I)
    return m.group(1) if m else None


@tool("verify_identifier",
      "Verify a BIS identifier (CML licence no, hallmarking HUID, registration "
      "no, document id) against authoritative Phase-3 data. Format alone is "
      "never proof. Returns VALIDATED / NOT_FOUND / NOT_VERIFIED / "
      "CONTEXT_MISMATCH with preserved evidence.",
      "Supabase bis.fmcs_master / bis.hallmarking_master / bis.document_master")
def verify_identifier(identifier: str, context: str = "") -> ToolResult:
    ident = (identifier or "").strip()
    if not ident:
        return ToolResult(ok=False, tool="verify_identifier", data=None,
                          error="empty identifier", provenance="verification")
    pg = supabase().impl
    verdict, evidence = "NOT_VERIFIED", []

    with pg.conn.cursor() as cur:
        # CML licence numbers - fmcs_master
        cur.execute("SELECT fmcs_id, manufacturer_name, country, "
                    "canonical_is_number, licence_status, validity_date, "
                    "source_url FROM bis.fmcs_master WHERE cml_licence_no = %s "
                    "LIMIT 5", (ident,))
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        if rows:
            verdict, evidence = "VALIDATED", [{"source_table": "fmcs_master",
                                               "rows": rows}]
        else:
            # Hallmarking centres / HUID-adjacent ids
            cur.execute("SELECT hm_id, centre_name, centre_code, city, state, "
                        "recognition_status, source_url FROM "
                        "bis.hallmarking_master WHERE centre_code = %s "
                        "LIMIT 5", (ident,))
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            if rows:
                verdict, evidence = "VALIDATED", [
                    {"source_table": "hallmarking_master", "rows": rows}]
            else:
                # Registered documents (document_id)
                cur.execute("SELECT document_id, document_type, title, "
                            "canonical_is_number, source_url FROM "
                            "bis.document_master WHERE document_id = %s "
                            "LIMIT 1", (ident,))
                cols = [d[0] for d in cur.description]
                rows = [dict(zip(cols, r)) for r in cur.fetchall()]
                if rows:
                    verdict, evidence = "VALIDATED", [
                        {"source_table": "document_master", "rows": rows}]

    # CONTEXT_MISMATCH: identifier resolves, but the IS context does not match
    want_is = _context_num(context)
    if verdict == "VALIDATED" and want_is:
        got = str((evidence[0]["rows"][0].get("canonical_is_number") or ""))
        want = "".join(ch for ch in want_is if ch.isdigit())
        got_d = "".join(ch for ch in got if ch.isdigit())
        if got_d and want and got_d != want:
            verdict = "CONTEXT_MISMATCH"
        elif not got_d:
            # resolved, but record carries no IS linkage to compare
            verdict = "NOT_VERIFIED"

    data = {"identifier": ident,
            "verdict": verdict,
            "recognized_format": bool(CML_RE.match(ident) or HUID_RE.match(ident)
                                      or REG_RE.match(ident)),
            "format_is_not_proof": True,
            "evidence": evidence}
    return ToolResult(ok=True, tool="verify_identifier", data=data, error="",
                      provenance="Supabase fmcs_master / hallmarking_master / "
                                 "document_master (exact match only)")
