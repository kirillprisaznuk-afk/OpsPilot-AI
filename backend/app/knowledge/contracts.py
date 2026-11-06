from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ID = int


class Filters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    supplier_id: int | None = Field(None, gt=0, le=2147483647)
    document_type: Literal["policy", "supplier_agreement"] | None = None
    department_id: int | None = Field(None, gt=0, le=2147483647)
    document_id: int | None = Field(None, gt=0, le=2147483647)
    version_id: int | None = Field(None, gt=0, le=2147483647)
    contract_id: int | None = Field(None, gt=0, le=2147483647)
    contract_reference: str | None = Field(None, min_length=1, max_length=50)


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=2, max_length=512)
    mode: Literal["keyword", "vector", "hybrid"] = "hybrid"
    top_k: int = Field(5, ge=1, le=20)
    as_of: date = date(2026, 9, 30)
    filters: Filters = Field(default_factory=Filters)

    @field_validator("query")
    @classmethod
    def meaningful_query(cls, value):
        value = value.strip()
        if len(value) < 2 or not any(c.isalnum() for c in value) or any(ord(c) < 32 for c in value):
            raise ValueError("Query must contain text without control characters.")
        return value


class ContextRequest(SearchRequest):
    context_budget: int = Field(2048, ge=128, le=8192)
    business_context: str | None = Field(None, max_length=512)


class DocumentMetadata(BaseModel):
    document_id: int
    code: str
    title: str
    document_type: str
    department_id: int
    department: str
    contract_id: int | None
    contract_reference: str | None
    supplier_id: int | None
    supplier: str | None
    version_id: int
    version: int
    effective_on: date
    sha256: str


class Citation(BaseModel):
    citation_id: str
    document_id: int
    document_version_id: int
    chunk_id: str
    title: str
    version: int
    section: list[str]
    line_start: int
    line_end: int
    effective_on: date
    source_sha256: str
    text_sha256: str
    source_reference: str


class Evidence(BaseModel):
    chunk_id: str
    document_id: int
    document_version_id: int
    title: str
    section: list[str]
    text: str
    rank: int
    score: float
    lexical_score: float | None
    cosine_similarity: float | None
    retrieval_method: Literal["keyword", "vector", "hybrid"]
    effective_date: date
    metadata: DocumentMetadata
    citation: Citation
    source_provenance: dict[str, str]
    suspicious_content: bool
    trust: Literal["untrusted_source_data"] = "untrusted_source_data"


class SearchResponse(BaseModel):
    query: str
    retrieval_mode: str
    as_of: date
    status: Literal["evidence_found", "no_matches", "low_confidence", "no_effective_documents"]
    insufficient_evidence: bool
    evidence: list[Evidence]
    eligible_versions: int
    model_configuration: dict
    ranking: dict
    limitations: list[str]


class ContextResponse(BaseModel):
    question: str
    business_context: str | None
    as_of: date
    evidence: list[Evidence]
    citations: list[str]
    coverage: str
    insufficient_evidence: bool
    omitted_chunks: int
    token_count: int
    token_count_basis: str
    context_budget: int
    trust_boundary: dict[str, str | bool]


class DocumentList(BaseModel):
    documents: list[DocumentMetadata]
    total: int
    limit: int
    offset: int


class SourcePreview(BaseModel):
    metadata: DocumentMetadata
    text: str
    line_start: int
    line_end: int
    verified: bool


class CitationPreview(BaseModel):
    citation: Citation
    text: str
    verified: bool


class IndexStatus(BaseModel):
    state: str
    documents: int
    versions: int
    chunks: int
    configuration: dict | None
    configured_model: dict
    model_cached: bool
    index_bytes: int
    indexed_at: str | None
