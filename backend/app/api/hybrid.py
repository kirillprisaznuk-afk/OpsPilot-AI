import asyncio
import logging
from typing import Annotated
from uuid import UUID

from app.api.workflow import bearer, request_id
from app.hybrid.contracts import HybridRequest, HybridResponse
from app.hybrid.engine import query_hybrid
from app.hybrid.registry import RELATIONSHIPS, describe
from app.workflow.auth import authenticate
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials

router = APIRouter(prefix="/api/v1/hybrid", tags=["hybrid enterprise intelligence"])


@router.get("/capabilities")
def capabilities():
    return {"capabilities": describe(), "relationships": RELATIONSHIPS, "read_only": True}


@router.get("/status")
def status():
    return {
        "default_mode": "HYBRID_LOCAL",
        "modes": ["HYBRID_LOCAL", "DETERMINISTIC", "LOCAL_FULL_AGENT"],
        "deterministic_available_without_llm": True,
        "local_llm_acceptance": "not_verified_by_status",
        "legacy": "explicit experimental /api/v1/agent/query",
        "read_only": True,
    }


def conversation_owner(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> UUID | None:
    if "authorization" not in request.headers:
        return None
    token = credentials.credentials if credentials else None
    return authenticate(token, request_id(request)).session_id


@router.post("/query", response_model=HybridResponse)
async def query(
    body: HybridRequest,
    request: Request,
    owner: Annotated[UUID | None, Depends(conversation_owner)],
):
    task = asyncio.create_task(query_hybrid(body, conversation_owner=owner))
    try:
        while not task.done():
            await asyncio.wait([task], timeout=0.1)
            if await request.is_disconnected():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                raise HTTPException(499, "Client disconnected; hybrid execution cancelled.")
        result = await task
        logging.getLogger("opspilot.hybrid").info(
            "request=%s mode=%s status=%s tools=%s llm_calls=%s elapsed_ms=%s reason=%s",
            result.request_id,
            result.operating_mode,
            result.status,
            result.usage.tool_calls,
            result.usage.llm_calls,
            result.usage.elapsed_ms,
            result.termination_reason,
        )
        return result
    except asyncio.CancelledError:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        raise
