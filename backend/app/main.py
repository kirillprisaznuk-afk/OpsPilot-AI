import logging

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.agent.contracts import AgentError
from app.analytics.common import AnalyticsInputError
from app.api.agent import router as agent_router
from app.api.analytics import router as analytics_router
from app.api.hybrid import router as hybrid_router
from app.api.knowledge import router as knowledge_router
from app.api.routes import router
from app.api.workflow import auth_router
from app.api.workflow import router as workflow_router
from app.api.workspace import router as workspace_router
from app.db.session import session
from app.knowledge.embeddings import KnowledgeError
from app.schemas.responses import HealthResponse
from app.services.demo import readiness
from app.workflow.common import WorkflowError
from app.workflow.http import WorkflowHTTPGuard, audit_denial, error_response, stage5

app = FastAPI(
    title="OpsPilot AI — Enterprise Operations and Knowledge Retrieval",
    version="0.5.0",
    description="Synthetic enterprise analytics with human-governed internal workflows.",
)
app.include_router(router)
app.include_router(analytics_router)
app.include_router(knowledge_router)
app.include_router(agent_router)
app.include_router(hybrid_router)
app.include_router(auth_router)
app.include_router(workflow_router)
app.include_router(workspace_router)
app.add_middleware(WorkflowHTTPGuard)


@app.exception_handler(WorkflowError)
async def workflow_error(request: Request, exc: WorkflowError):
    if request.method == "GET":
        audit_denial(request, exc.code)
    return error_response(request, exc.code, str(exc), exc.status, exc.details)


@app.exception_handler(RequestValidationError)
async def request_validation(request: Request, exc: RequestValidationError):
    if not stage5(request.url.path):
        return await request_validation_exception_handler(request, exc)
    audit_denial(request, "validation_error")
    fields = [
        {"loc": [str(x)[:80] for x in e["loc"]], "type": e["type"], "message": e["msg"][:200]}
        for e in exc.errors()[:32]
    ]
    return error_response(
        request,
        "validation_error",
        "Request does not match the Stage 5 contract.",
        422,
        {"fields": fields},
    )


@app.exception_handler(AgentError)
async def agent_error(request: Request, exc: AgentError):
    code = (
        404
        if exc.code == "conversation_not_found"
        else 422
        if exc.code == "conversation_window_conflict"
        else 503
    )
    return JSONResponse(
        status_code=code, content={"detail": {"code": exc.code, "message": str(exc)}}
    )


@app.exception_handler(KnowledgeError)
async def knowledge_error(request: Request, exc: KnowledgeError):
    return JSONResponse(
        status_code=exc.status, content={"detail": {"code": exc.code, "message": str(exc)}}
    )


@app.exception_handler(AnalyticsInputError)
async def analytics_input_error(request: Request, exc: AnalyticsInputError):
    return JSONResponse(
        status_code=422,
        content={
            "detail": {
                "code": "unsupported_analytics_parameter",
                "field": exc.field,
                "message": str(exc),
            }
        },
    )


@app.exception_handler(SQLAlchemyError)
async def database_error(request: Request, exc: SQLAlchemyError):
    # Never log query parameters, URLs or raw driver messages that might contain secrets.
    logging.getLogger("opspilot").error("Database operation failed: %s", type(exc).__name__)
    if stage5(request.url.path):
        return error_response(
            request, "workflow_database_unavailable", "Database unavailable.", 503
        )
    return JSONResponse(status_code=503, content={"detail": "Database unavailable"})


@app.get("/health", response_model=HealthResponse)
def health():
    return {"status": "ok"}


@app.get("/ready", response_model=HealthResponse)
def ready(db: Session = Depends(session)):  # noqa: B008
    if not readiness(db):
        raise HTTPException(503, "Database must be migrated and seeded")
    return {"status": "ready"}
