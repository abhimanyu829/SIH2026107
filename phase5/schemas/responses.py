"""Pydantic request/response schemas for /api/chat, /api/agent/run, /api/search."""
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: str = ""
    language: str = "en"


class AgentRunRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: str = ""
    language: str = "en"
    force_agent: bool = False


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    document_type: str = ""
    canonical_is_number: str = ""
    is_id: str = ""
    top_k: int = Field(10, ge=1, le=50)


class Citation(BaseModel):
    document_id: str = ""
    title: str = ""
    page: int | str = ""
    clause: str = ""
    source_url: str = ""


class RelatedInfo(BaseModel):
    products: list = []
    qcos: list = []
    schemes: list = []
    tests: list = []
    labs: list = []


class AgentUsage(BaseModel):
    used: bool = False
    steps: int = 0
    tools_used: list = []


class ChatResponse(BaseModel):
    answer: str
    confidence: float = 0.0
    language: str = "en"
    intent: str = ""
    entities: dict = {}
    sources: list = []
    related: RelatedInfo = RelatedInfo()
    agent: AgentUsage = AgentUsage()


class EvidenceItem(BaseModel):
    document_id: str = ""
    canonical_is_number: str = ""
    document_type: str = ""
    title: str = ""
    section: str = ""
    clause: str = ""
    page: int | str = ""
    content: str = ""
    source_url: str = ""
    version: str = ""
    effective_date: str = ""
    relevance_score: float = 0.0


class AgentRunResponse(BaseModel):
    answer: str
    status: str = "completed"
    plan: list = []
    steps: list = []
    tools_used: list = []
    evidence: list = []
    citations: list = []
    confidence: float = 0.0
    entities: dict = {}
    unresolved_items: list = []
    conversation_id: str = ""
