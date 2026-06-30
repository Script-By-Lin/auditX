"""FastAPI web dashboard and CLI for auditX logs."""

from __future__ import annotations

import argparse
import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

try:
    from fastapi import Depends, FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
    from fastapi.responses import FileResponse, StreamingResponse
    from fastapi.staticfiles import StaticFiles
except ImportError as err:
    raise ImportError(
        "Please install auditX with web extras: pip install auditX[web]"
    ) from err

from auditx.web.bridge import connect_logger, try_connect_default_logger
from auditx.web.hub import get_hub
from auditx.web.reader import LogQuery, LogReader, LogSource

try:
    from auditx import __version__
    from auditx.core import AuditLogger
except ImportError:
    __version__ = "0.9.1"
    AuditLogger = Any  # type: ignore[misc,assignment]

_STATIC_DIR = Path(__file__).resolve().parent / "static"


def _static_index() -> Path:
    return _STATIC_DIR / "index.html"


def _verify_api_key(request: Request, api_key: Optional[str]) -> None:
    if not api_key:
        return
    provided = request.headers.get("X-API-Key") or request.query_params.get("api_key")
    if provided != api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


def _format_sse(source: LogSource, entry: dict[str, Any], cursor: int | None = None) -> str:
    payload = {"source": source, "entry": entry, "transport": "file"}
    if cursor is not None:
        payload["cursor"] = cursor
    return f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"


def create_app(
    log_dir: str | Path = "logs",
    api_key: Optional[str] = None,
    audit_log_file: str = "audit.jsonl",
    security_log_file: str = "security.jsonl",
    realtime: bool = True,
    logger: AuditLogger | None = None,
) -> FastAPI:
    reader = LogReader(log_dir, audit_log_file, security_log_file)
    hub = get_hub(log_dir)

    @asynccontextmanager
    async def lifespan(app: FastAPI):  # noqa: ARG001
        hub.bind_loop(asyncio.get_running_loop())
        if realtime:
            if logger is not None:
                connect_logger(logger, hub)
            else:
                try_connect_default_logger(log_dir)
        yield

    app = FastAPI(
        title="auditX Dashboard",
        description="Read-only web viewer with real-time audit log streaming.",
        version=__version__,
        lifespan=lifespan,
    )

    def auth(request: Request) -> None:
        _verify_api_key(request, api_key)

    @app.get("/")
    async def index(_: None = Depends(auth)) -> FileResponse:
        index_path = _static_index()
        if not index_path.exists():
            raise HTTPException(status_code=500, detail="Dashboard assets not found")
        return FileResponse(index_path)

    @app.get("/api/stats")
    async def stats(_: None = Depends(auth)) -> dict[str, Any]:
        return reader.stats()

    @app.get("/api/entries")
    async def entries(
        _: None = Depends(auth),
        source: LogSource = Query("audit"),
        limit: int = Query(100, ge=1, le=5000),
        offset: int = Query(0, ge=0),
        module: str = Query(""),
        level: str = Query(""),
        user: str = Query(""),
        branch_id: str = Query(""),
        q: str = Query(""),
    ) -> dict[str, Any]:
        query = LogQuery(
            source=source,
            limit=limit,
            offset=offset,
            module=module,
            level=level,
            user=user,
            branch_id=branch_id,
            q=q,
        )
        items, total = reader.read(query)
        return {"items": items, "total": total, "limit": limit, "offset": offset, "source": source}

    @app.get("/api/recent")
    async def recent(
        _: None = Depends(auth),
        source: LogSource = Query("audit"),
        limit: int = Query(50, ge=1, le=200),
    ) -> dict[str, Any]:
        events = hub.recent(source=source, limit=limit)
        return {"items": [event["entry"] for event in events], "source": source}

    @app.websocket("/api/ws")
    async def websocket_stream(websocket: WebSocket) -> None:
        if api_key:
            provided = websocket.headers.get("X-API-Key") or websocket.query_params.get("api_key")
            if provided != api_key:
                await websocket.close(code=4401)
                return

        await websocket.accept()
        queue = hub.subscribe()
        try:
            await websocket.send_json({"type": "connected", "transport": "websocket"})
            while True:
                event = await queue.get()
                await websocket.send_json(
                    {
                        "type": "entry",
                        "source": event["source"],
                        "entry": event["entry"],
                        "transport": "realtime",
                    }
                )
        except WebSocketDisconnect:
            pass
        finally:
            hub.unsubscribe(queue)

    @app.get("/api/stream")
    async def stream(
        request: Request,
        source: LogSource = Query("audit"),
        after: int = Query(0, ge=0),
    ) -> StreamingResponse:
        _verify_api_key(request, api_key)

        async def event_generator() -> Any:
            cursor = after
            queue = hub.subscribe()
            try:
                new_entries, cursor = await asyncio.to_thread(reader.tail, source, cursor)
                for entry in new_entries:
                    yield _format_sse(source, entry, cursor)

                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=2.0)
                        if event.get("source") == source:
                            yield _format_sse(source, event["entry"])
                    except asyncio.TimeoutError:
                        new_entries, cursor = await asyncio.to_thread(reader.tail, source, cursor)
                        for entry in new_entries:
                            yield _format_sse(source, entry, cursor)
            finally:
                hub.unsubscribe(queue)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    if _STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    return app


def mount_audit_viewer(
    app: Any,
    log_dir: str | Path = "logs",
    prefix: str = "/audit",
    api_key: Optional[str] = None,
    realtime: bool = True,
    logger: AuditLogger | None = None,
) -> None:
    """Mount the read-only audit dashboard onto an existing FastAPI app."""
    sub_app = create_app(
        log_dir=log_dir,
        api_key=api_key,
        realtime=realtime,
        logger=logger,
    )
    app.mount(prefix, sub_app)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="auditx-ui",
        description="Launch the auditX read-only web dashboard.",
    )
    parser.add_argument("--log-dir", default="logs", help="Directory containing audit.jsonl (default: logs)")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8080, help="Bind port (default: 8080)")
    parser.add_argument("--api-key", default="", help="Optional API key for dashboard access")
    parser.add_argument(
        "--no-realtime",
        action="store_true",
        help="Disable in-process WebSocket push (file tail only)",
    )
    args = parser.parse_args()

    try:
        import uvicorn
    except ImportError as err:
        raise SystemExit("uvicorn is required. Install with: pip install auditX[web]") from err

    api_key = args.api_key or None
    app = create_app(log_dir=args.log_dir, api_key=api_key, realtime=not args.no_realtime)

    print(f"auditX dashboard → http://{args.host}:{args.port}/")
    print(f"Reading logs from: {Path(args.log_dir).resolve()}")
    print("Real-time WebSocket push enabled (use --no-realtime to disable)")
    if api_key:
        print("API key protection enabled (send X-API-Key header or ?api_key=...)")
    else:
        print("No API key set — dashboard is open on the bound host.")

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
