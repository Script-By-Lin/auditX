"""FastAPI/Starlette integration for auditX.

Copyright (c) 2026 auditX. All rights reserved.
Proprietary — not licensed for use in other projects without permission.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Optional

try:
    from starlette.types import ASGIApp, Receive, Scope, Send
except ImportError as err:
    raise ImportError(
        "Please install starlette and fastapi to use the auditx.fastapi module."
    ) from err

from auditx.core import AuditAction, AuditLogger, BusinessModule, LogLevel, RequestContext


class AuditMiddleware:
    """Raw ASGI middleware for auditX that tracks HTTP requests and context.

    Because it is a raw ASGI middleware, mutations to the `RequestContext`
    made within route handlers correctly propagate back to the middleware
    before writing the final HTTP request audit trail entry.
    """

    def __init__(
        self,
        app: ASGIApp,
        logger: Optional[AuditLogger] = None,
        exclude_paths: Optional[list[str]] = None,
    ):
        self.app = app
        if logger is None:
            from auditx import audit
            self.logger = audit
        else:
            self.logger = logger
        self.exclude_paths = exclude_paths or ["/docs", "/redoc", "/openapi.json", "/favicon.ico"]

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if any(path.startswith(p) for p in self.exclude_paths):
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "")
        query_string = scope.get("query_string", b"").decode("utf-8")
        endpoint = f"{path}?{query_string}" if query_string else path

        # Extract client IP
        client = scope.get("client")
        ip = client[0] if client else "127.0.0.1"

        # Check for request ID in headers (case-insensitive check)
        request_id = ""
        session_id = ""
        for name, value in scope.get("headers", []):
            if name.lower() == b"x-request-id":
                request_id = value.decode("utf-8")
            elif name.lower() == b"x-session-id":
                session_id = value.decode("utf-8")

        if not request_id:
            request_id = str(uuid.uuid4())

        # Initialize the request context
        RequestContext.set(
            user="SYSTEM",
            user_role="",
            company_id="",
            branch_id="",
            session_id=session_id,
            request_id=request_id,
            ip=ip,
        )

        start_time = time.perf_counter()
        status_code = [500]

        async def send_wrapper(message: Any) -> None:
            if message["type"] == "http.response.start":
                status_code[0] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
            success = 200 <= status_code[0] < 400
        except Exception as exc:
            duration = (time.perf_counter() - start_time) * 1000
            ctx = RequestContext.get()
            self.logger.log(
                description=f"HTTP Request Failed: {str(exc)}",
                level=LogLevel.ERROR.value,
                module=BusinessModule.SYSTEM.value,
                action=AuditAction.READ.value,
                user=ctx.get("user", "SYSTEM"),
                user_role=ctx.get("user_role", ""),
                company_id=ctx.get("company_id", ""),
                branch_id=ctx.get("branch_id", ""),
                request_id=ctx.get("request_id", ""),
                session_id=ctx.get("session_id", ""),
                ip=ctx.get("ip", ip),
                method=method,
                endpoint=endpoint,
                status=500,
                success=False,
                metadata={"duration_ms": duration, "error": str(exc)},
            )
            raise exc from None

        duration = (time.perf_counter() - start_time) * 1000
        ctx = RequestContext.get()

        # Log level based on status code
        log_level = LogLevel.AUDIT.value
        if status_code[0] >= 500:
            log_level = LogLevel.ERROR.value
        elif status_code[0] >= 400:
            log_level = LogLevel.WARNING.value

        action_map = {
            "POST": AuditAction.CREATE.value,
            "GET": AuditAction.READ.value,
            "PUT": AuditAction.UPDATE.value,
            "PATCH": AuditAction.UPDATE.value,
            "DELETE": AuditAction.DELETE.value,
        }
        action = action_map.get(method.upper(), AuditAction.READ.value)

        self.logger.log(
            description=f"HTTP {method} {path} completed with {status_code[0]}",
            level=log_level,
            module=BusinessModule.SYSTEM.value,
            action=action,
            user=ctx.get("user", "SYSTEM"),
            user_role=ctx.get("user_role", ""),
            company_id=ctx.get("company_id", ""),
            branch_id=ctx.get("branch_id", ""),
            request_id=ctx.get("request_id", ""),
            session_id=ctx.get("session_id", ""),
            ip=ctx.get("ip", ip),
            method=method,
            endpoint=endpoint,
            status=status_code[0],
            success=success,
            metadata={"duration_ms": duration},
        )
