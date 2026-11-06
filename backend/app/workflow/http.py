"""Small Stage 5 HTTP boundary: bounded body, no cookie auth, secret-safe errors."""

import asyncio
import uuid

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.workflow.audit import event
from app.workflow.common import transaction


def stage5(path):
    return path.startswith(("/api/v1/auth", "/api/v1/workflows", "/api/v1/workspace"))


class WorkflowHTTPGuard:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not stage5(scope["path"]):
            return await self.app(scope, receive, send)
        state = scope.setdefault("state", {})
        state["correlation_id"] = uuid.uuid4()
        supplied = dict(scope.get("headers", [])).get(b"x-request-id")
        if supplied:
            try:
                state["correlation_id"] = uuid.UUID(supplied.decode("ascii"))
            except (UnicodeError, ValueError):
                return await self.error(scope, receive, send, "invalid_request_id", 422)
        if scope["method"] in {"POST", "PUT", "PATCH"}:
            body = bytearray()
            try:
                async with asyncio.timeout(10):
                    while True:
                        message = await receive()
                        if message["type"] == "http.disconnect":
                            return
                        body.extend(message.get("body", b""))
                        if len(body) > 65536:
                            return await self.error(scope, receive, send, "request_too_large", 413)
                        if not message.get("more_body", False):
                            break
            except TimeoutError:
                return await self.error(scope, receive, send, "request_body_timeout", 408)
            delivered = False
            original_receive = receive

            async def replay():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": bytes(body), "more_body": False}
                return await original_receive()

            receive = replay

        async def safe_send(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend(
                    [
                        (b"cache-control", b"no-store"),
                        (b"pragma", b"no-cache"),
                        (b"x-content-type-options", b"nosniff"),
                        (b"x-request-id", str(state["correlation_id"]).encode()),
                    ]
                )
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, safe_send)

    async def error(self, scope, receive, send, code, status):
        response = JSONResponse(
            {
                "error": {
                    "code": code,
                    "message": "Stage 5 request rejected.",
                    "request_id": str(scope["state"]["correlation_id"]),
                }
            },
            status_code=status,
            headers={"Cache-Control": "no-store"},
        )
        await response(scope, receive, send)


def audit_denial(request, code):
    actor = getattr(request.state, "workflow_actor", None)
    bind = getattr(request.state, "workflow_bind", None)
    if actor and bind is not None:
        try:
            with transaction("auth", bind) as db:
                event(
                    db,
                    actor,
                    "request.denied",
                    request_id=request.state.correlation_id,
                    result="DENIED",
                    after={"code": code},
                )
        except Exception:
            # An unavailable audit connection cannot turn a denied request into an allowed one.
            pass


def error_response(request, code, message, status, details=None):
    return JSONResponse(
        jsonable_encoder(
            {
                "error": {
                    "code": code,
                    "message": message,
                    "request_id": getattr(request.state, "correlation_id", uuid.uuid4()),
                    "details": details,
                }
            }
        ),
        status_code=status,
        headers={"WWW-Authenticate": "Bearer"} if status == 401 else None,
    )
