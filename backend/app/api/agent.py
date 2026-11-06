import asyncio

from app.agent.config import agent_settings
from app.agent.contracts import AgentRequest, AgentResponse
from app.agent.service import query_agent
from app.agent.tools import TOOLS
from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])


@router.get("/status")
def status():
    s = agent_settings()
    return {
        "state": "configured_unverified" if s.configured else "provider_not_configured",
        "provider": s.llm_provider,
        "model": s.llm_model,
        "local_profile": {
            "compact_transport": s.ollama_compact_transport,
            "reference_output": s.ollama_reference_output,
            "model_selected_catalogue": s.ollama_tool_selection,
            "context_tokens": s.ollama_context_tokens,
            "gpu_layers": s.ollama_gpu_layers,
            "batch_tokens": s.ollama_batch_tokens,
        }
        if s.llm_provider == "ollama"
        else None,
        "read_only": True,
        "live_validation": "not_performed_by_status",
        "limits": {
            "llm_calls": s.agent_max_rounds,
            "tool_calls": s.agent_max_tools,
            "request_seconds": s.agent_timeout_seconds,
        },
        "conversation_storage": "single-process memory, bounded history; lost on restart",
        "authentication": "not_implemented_local_demo_only",
    }


@router.get("/tools")
def tools():
    return {
        "tools": [
            {
                "name": t.name,
                "description": t.description,
                "arguments": t.arguments.model_json_schema(),
                "response": t.response.__name__,
                "read_only": True,
                "permission_class": t.permission,
                "result_bytes": agent_settings().agent_result_bytes,
                "error_contract": "structured code/message, no raw SQL/provider trace",
            }
            for t in TOOLS.values()
        ]
    }


@router.post("/query", response_model=AgentResponse)
async def query(body: AgentRequest, request: Request):
    task = asyncio.create_task(query_agent(body))
    try:
        while not task.done():
            await asyncio.wait([task], timeout=0.1)
            if await request.is_disconnected():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                raise HTTPException(499, "Client disconnected; agent execution cancelled.")
        return await task
    except asyncio.CancelledError:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        raise
