"""Typed tool I/O contracts. Tools validate through these models."""
from pydantic import BaseModel, Field


class ProductQuery(BaseModel):
    query: str = Field(..., description="Free product text, e.g. 'adjustable office work chairs'")


class StandardQuery(BaseModel):
    is_number: str = Field(..., description="IS number with or without year, e.g. 'IS 17631' or '17631:2022'")
    year: str = ""


class EvidenceQuery(BaseModel):
    query: str = Field(..., description="Natural-language evidence search text")
    canonical_is_number: str = ""
    document_type: str = ""
    is_id: str = ""
    top_k: int = Field(5, ge=1, le=25)


class LabQuery(BaseModel):
    is_number: str = Field(..., description="IS number to find labs for")


class IdentifierQuery(BaseModel):
    identifier: str = Field(..., description="Licence/CML/registration/HUID or other BIS identifier")
    context: str = ""


class CompareQuery(BaseModel):
    is_a: str = Field(..., description="First IS number")
    is_b: str = Field(..., description="Second IS number")
