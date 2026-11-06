from datetime import date
from typing import Annotated

from app.api.routes import DB
from app.knowledge import citations, context, search, service
from app.knowledge.contracts import (
    CitationPreview,
    ContextRequest,
    ContextResponse,
    DocumentList,
    IndexStatus,
    SearchRequest,
    SearchResponse,
    SourcePreview,
)
from fastapi import APIRouter, Path, Query

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])
EntityID = Annotated[int, Path(gt=0, le=2147483647)]


@router.get("/status", response_model=IndexStatus)
def get_status(db: DB):
    return service.status(db)


@router.get("/documents", response_model=DocumentList)
def get_documents(
    db: DB,
    as_of: date = date(2026, 9, 30),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0, le=1_000_000),
):
    return service.list_documents(db, as_of, limit, offset)


@router.get("/documents/{document_id}", response_model=SourcePreview)
def get_document(db: DB, document_id: EntityID, as_of: date = date(2026, 9, 30)):
    return service.preview(db, document_id, None, as_of)


@router.get("/documents/{document_id}/versions/{version_id}", response_model=SourcePreview)
def get_version(
    db: DB, document_id: EntityID, version_id: EntityID, as_of: date = date(2026, 9, 30)
):
    return service.preview(db, document_id, version_id, as_of)


@router.get("/citations/{citation_id}", response_model=CitationPreview)
def get_citation(
    db: DB, citation_id: str = Path(min_length=67, max_length=67, pattern=r"^kc_[a-f0-9]{64}$")
):
    return citations.resolve(db, citation_id)


@router.post("/search", response_model=SearchResponse)
def post_search(db: DB, request: SearchRequest):
    return search.search(db, request)


@router.post("/context", response_model=ContextResponse)
def post_context(db: DB, request: ContextRequest):
    return context.build_context(db, request)
