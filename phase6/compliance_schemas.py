"""Phase-6 pydantic schemas: audit lifecycle + compliance results.

Pure data contracts for the /api/compliance endpoints. The audit context
itself is a plain dict (spec section 29) stored as local JSON.
"""
from pydantic import BaseModel, Field

# ---- requests ---------------------------------------------------------------


class AuditCreateRequest(BaseModel):
    product_text: str = Field(..., min_length=2, max_length=400,
                              description="e.g. 'office work chairs'")


class AnalyzeRequest(BaseModel):
    """Optional overrides; defaults resolve from the audit context."""
    max_requirements: int = Field(40, ge=5, le=200)
    use_llm: bool = True


class RecheckRequest(AnalyzeRequest):
    pass


class ProcessRequest(BaseModel):
    document_ids: list = Field(default_factory=list,
                               description="empty = all uploaded docs")


# ---- responses --------------------------------------------------------------


class AuditSummary(BaseModel):
    audit_id: str
    product_text: str
    created_at: str = ""
    status: str = "CREATED"          # CREATED/PROCESSING/ANALYZED/FAILED
    documents: list = []
    evidence_count: int = 0
    last_score: dict | None = None


class Decision(BaseModel):
    requirement_id: str
    requirement: str
    type: str = ""
    decision: str                    # PASS | GAP | UNKNOWN
    reason: str
    evidence_refs: list = []
    bis_source: str = ""
    clause: str = ""
    conflicts: list = []


class Score(BaseModel):
    score: int                       # 0-100, "Compliance Readiness Score"
    total: int
    passed: int
    gaps: int
    unknown: int
    label: str = "Compliance Readiness Score"


class RemediationItem(BaseModel):
    requirement_id: str
    gap: str
    missing_evidence: str
    recommendation: str
    bis_source: str = ""


class ComplianceReport(BaseModel):
    audit_id: str
    product: dict
    bis_standard: dict
    qco_scheme: dict
    documents: list
    requirements_checked: int
    passed: list
    gaps: list
    unknown: list
    score: Score
    critical_missing_evidence: list
    remediation: list
    bis_sources: list
    disclaimer: str
