# auditX

ERP-grade audit logging for **trading** and **service** businesses. Track who did what, when, and where — with structured JSON trails suitable for compliance, SIEM, and multi-branch operations.

## Install

```bash
pip install auditX
```

**With web dashboard:**

```bash
pip install auditX[web]
```

**From source (development):**

```bash
git clone https://github.com/Script-By-Lin/auditX.git
cd auditX
pip install -e .
```

---

## Quick Start

Initialize context and write structured logs in standard Python code.

```python
from auditx import audit, RequestContext, BusinessModule, AuditAction

# 1. Set user/tenant context once per request or job
RequestContext.set(
    user="admin",
    user_role="manager",
    company_id="CO-001",
    branch_id="BR-YGN",
    ip="192.168.1.10",
)

# 2. Log security / auth events
audit.log_security("User login successful", action=AuditAction.LOGIN, user="admin")

# 3. Log trading transactions
audit.log_transaction(
    "Sales invoice posted",
    module=BusinessModule.SALES,
    action=AuditAction.POST,
    reference_no="SI-2026-0042",
    amount=1_250_000,
    entity_type="sales_invoice",
    entity_id="inv-42",
    party="Golden Trading Co.",
)

# 4. Log inventory movements
audit.log_inventory(
    "Stock issued for sales order",
    action=AuditAction.TRANSFER,
    product_id="SKU-1001",
    product_name="LED Panel 24W",
    quantity=50,
    warehouse_id="WH-MAIN",
    reference_no="SI-2026-0042",
)

# 5. Log service department jobs
audit.log_service(
    "Service job completed",
    action=AuditAction.UPDATE,
    job_id="SVC-889",
    customer_id="CUST-220",
    technician="U Kyaw",
    service_type="AC Maintenance",
    status_label="completed",
    amount=85_000,
)

# 6. Log field-level schema changes (before/after)
audit.log_change(
    "Customer credit limit updated",
    module=BusinessModule.CRM,
    action=AuditAction.UPDATE,
    entity_type="customer",
    entity_id="CUST-220",
    old_values={"credit_limit": 500_000},
    new_values={"credit_limit": 1_000_000},
)
```

---

## Run the Demo

To see `auditX` in action immediately:

```bash
python -m auditx
# or if installed as a package:
auditx-demo
```

---

## Web Dashboard

`auditX` includes an optional **read-only web UI** for browsing `audit.jsonl` and `security.jsonl` files. Install the web extras, then launch the dashboard against your log directory:

```bash
pip install auditX[web]

# Point at the directory where auditX writes logs (default: ./logs)
auditx-ui --log-dir ./logs --port 8080
```

Open **http://127.0.0.1:8080/** in your browser.

### CLI options

| Option | Default | Description |
| :--- | :--- | :--- |
| `--log-dir` | `logs` | Folder containing `audit.jsonl` and `security.jsonl` |
| `--host` | `127.0.0.1` | Bind address (use `0.0.0.0` only on trusted networks) |
| `--port` | `8080` | HTTP port |
| `--api-key` | *(none)* | Optional API key; send as `X-API-Key` header or `?api_key=` query param |

Example with API key protection:

```bash
auditx-ui --log-dir /var/log/my-erp --host 127.0.0.1 --port 9090 --api-key "change-me-in-production"
```

Then visit: `http://127.0.0.1:9090/?api_key=change-me-in-production`

### Dashboard features

- **Audit trail** and **security events** tabs
- Search and filter by user, module, level, branch, and free-text query
- Paginated table with JSON detail view (including `old_values` / `new_values`)
- **Real-time WebSocket push** — new entries appear instantly with highlight animation
- **SSE file-tail fallback** — catches logs written by other processes/workers
- Summary stats (total entries, failures, latest timestamp)

### Real-time logging (async + WebSocket)

When the dashboard runs **in the same process** as your app, audit entries are pushed to the UI instantly over WebSocket — no polling delay.

**1. Enable real-time push on your logger**

```python
from auditx import configure, audit, BusinessModule, AuditAction
from auditx.web import enable_realtime

configure(log_dir="logs")
enable_realtime()  # wires global audit singleton → dashboard hub
```

Or pass the logger explicitly when creating the dashboard:

```python
from auditx import create_logger
from auditx.web import create_app, connect_logger

logger = create_logger(log_dir="logs")
connect_logger(logger)

app = create_app(log_dir="logs", logger=logger)
```

**2. Use async log methods in FastAPI routes**

Sync `audit.log_*` methods block the event loop on file I/O. In async handlers, prefer the `alog_*` variants — they delegate to a thread pool via `asyncio.to_thread`:

```python
from auditx import audit, RequestContext, BusinessModule, AuditAction

@app.post("/sales/invoice")
async def create_invoice():
    RequestContext.set(user="admin", branch_id="BR-YGN")

    await audit.alog_transaction(
        "Sales invoice posted",
        module=BusinessModule.SALES,
        action=AuditAction.POST,
        reference_no="SI-2026-0042",
        amount=1_250_000,
    )
    return {"status": "posted"}
```

Available async methods: `alog`, `alog_change`, `alog_transaction`, `alog_inventory`, `alog_service`, `alog_security`.

**3. Integrated FastAPI app (logging + dashboard together)**

```python
from auditx import configure
from auditx.web import create_app, enable_realtime

configure(log_dir="logs")
enable_realtime()

app = create_app(log_dir="logs")  # auto-connects matching global logger

# uvicorn main:app --host 127.0.0.1 --port 8080
```

Open the dashboard, trigger logs from your API — entries appear in the table immediately.

> **Note:** Standalone `auditx-ui` still works for read-only file browsing. Real-time WebSocket push requires `enable_realtime()` or `connect_logger()` in the same process. Logs written by separate worker processes are picked up via the SSE file-tail fallback (~2s).

> [!WARNING]
> Audit logs are sensitive. The dashboard is **read-only**, but you should still bind to `127.0.0.1`, use `--api-key` in shared environments, and never expose it publicly without authentication and TLS.

### Mount into an existing FastAPI app

If your ERP already runs on FastAPI, mount the viewer under a path prefix:

```python
from fastapi import FastAPI
from auditx.web import mount_audit_viewer

app = FastAPI()

mount_audit_viewer(
    app,
    log_dir="/var/log/my-erp",
    prefix="/audit",
    api_key="change-me-in-production",  # optional
    realtime=True,
)
```

The UI and API are then available at `/audit/` (for example `http://localhost:8000/audit/`).

### Programmatic server setup

```python
from auditx.web import create_app

app = create_app(log_dir="logs", api_key=None)

# Run with uvicorn, or mount app in your ASGI stack
# uvicorn module:app --host 127.0.0.1 --port 8080
```

REST endpoints exposed by the dashboard:

| Endpoint | Description |
| :--- | :--- |
| `GET /api/stats` | Summary counts for audit and security logs |
| `GET /api/entries` | Filtered, paginated log entries (`source=audit\|security`) |
| `GET /api/recent` | In-memory buffer of recent entries (same-process realtime) |
| `GET /api/stream` | SSE stream (hub push + file-tail fallback) |
| `WS /api/ws` | WebSocket stream for instant in-process log push |

---

## Configuration & Output

Configure `auditX` once at application startup. By default, it writes to a `logs/` directory in the current working directory.

```python
from auditx import configure, create_logger

# Reconfigure the global singleton
configure(
    log_dir="/var/log/my-erp", 
    console=True, 
    max_file_bytes=10*1024*1024, # 10 MB (defaults to 10MB)
    backup_count=5               # Keep up to 5 rotated logs
)

# Or instantiate a standalone logger for a specific microservice/tenant
tenant_logger = create_logger(log_dir="logs/tenant-acme", console=False)
tenant_logger.log_transaction(...)
```

### Log File Schema

`auditX` separates log entries into three distinct files inside your configured `log_dir`:

| File | Format | Purpose |
| :--- | :--- | :--- |
| `audit.jsonl` | JSON Lines | The core immutable audit trail (one JSON object per line) containing all business events. |
| `security.jsonl` | JSON Lines | Auth failures, rate limits, and critical security-sensitive operations. |
| `app.log` | Text (formatted) | Standard application warnings, debug traces, and system messages. |

---

## FastAPI & Starlette Integration (ASGI Middleware)

`auditX` includes a built-in, async-safe **`AuditMiddleware`** that automatically captures request routing metadata, tracks response times/status codes, logs unhandled exceptions, and handles request-scoped identifiers (like Request IDs and Session IDs).

> [!NOTE]
> Because it is built on Python's native `contextvars` rather than `threading.local`, modifications to the `RequestContext` made within routes, dependency injection guards, or DB connectors will safely propagate to all downstream logs and back to the middleware's final request-response summary.

### 1. Register the Middleware

Mount `AuditMiddleware` to wrap your ASGI pipeline:

```python
from fastapi import FastAPI
from auditx import AuditMiddleware

app = FastAPI(title="My ERP App")

# Registers the audit log middleware
app.add_middleware(
    AuditMiddleware,
    exclude_paths=["/docs", "/redoc", "/openapi.json", "/favicon.ico", "/healthz"]
)
```

### 2. Extract and Set User Context in Dependencies

Use a FastAPI dependency to authenticate users, extract tenancy, and populate context variables. The middleware isolates these values automatically per async task context.

```python
from fastapi import Depends, Header, HTTPException, status
from auditx import RequestContext, audit, BusinessModule, AuditAction

async def authenticate_and_set_context(
    x_user: str = Header("SYSTEM"),
    x_role: str = Header(""),
    x_company: str = Header(""),
    x_branch: str = Header(""),
):
    # Populate context. All subsequent audit calls in this request task inherits these
    RequestContext.update(
        user=x_user,
        user_role=x_role,
        company_id=x_company,
        branch_id=x_branch,
    )
    return x_user

@app.post("/sales/invoice")
async def create_invoice(user: str = Depends(authenticate_and_set_context)):
    # Any transaction logged here inherits the request ID, client IP, and user context
    audit.log_transaction(
        "Sales invoice posted",
        module=BusinessModule.SALES,
        action=AuditAction.POST,
        reference_no="SI-2026-098",
        amount=450000,
    )
    return {"status": "posted"}
```

### 3. Request/Session ID Propagation & Errors

* **Request ID:** The middleware scans incoming request headers for a case-insensitive `X-Request-ID`. If missing, it generates a fresh UUID.
* **Session ID:** The middleware automatically scans for `X-Session-ID` to track persistent login sessions.
* **Unhandled Exceptions:** If an endpoint raises an exception, `AuditMiddleware` intercept it, logs a structured error (level `ERROR`, `success=False`, status `500`), and raises it to allow standard FastAPI/Starlette exception handlers to process the response.

---

## Django Integration (Custom Middleware)

Since Django uses standard synchronous or asynchronous thread pools depending on execution environment, `contextvars` behaves reliably when handled inside a request-response lifecycle middleware.

Here is a production-ready custom Django middleware implementation:

```python
# my_project/middleware.py
import time
import uuid
from django.utils.deprecation import MiddlewareMixin
from auditx import RequestContext, audit, BusinessModule, AuditAction

class AuditDjangoMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. Resolve client IP address
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '127.0.0.1')

        # 2. Extract context headers
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        session_id = request.headers.get("X-Session-ID", "")
        if not session_id and hasattr(request, "session") and request.session.session_key:
            session_id = request.session.session_key

        # 3. Setup context
        RequestContext.set(
            user=getattr(request.user, 'username', 'SYSTEM') if hasattr(request, 'user') else 'SYSTEM',
            user_role=getattr(request.user, 'role', '') if hasattr(request, 'user') else '',
            company_id=request.headers.get("X-Company-ID", ""),
            branch_id=request.headers.get("X-Branch-ID", ""),
            session_id=session_id,
            request_id=request_id,
            ip=ip,
        )

        start_time = time.perf_counter()

        try:
            response = self.get_response(request)
            status_code = response.status_code
        except Exception as exc:
            duration = (time.perf_counter() - start_time) * 1000
            ctx = RequestContext.get()
            audit.log(
                description=f"HTTP Request Failed: {str(exc)}",
                level="ERROR",
                module="system",
                action="READ",
                user=ctx.get("user", "SYSTEM"),
                user_role=ctx.get("user_role", ""),
                company_id=ctx.get("company_id", ""),
                branch_id=ctx.get("branch_id", ""),
                request_id=ctx.get("request_id", ""),
                session_id=ctx.get("session_id", ""),
                ip=ctx.get("ip", ip),
                method=request.method,
                endpoint=request.get_full_path(),
                status=500,
                success=False,
                metadata={"duration_ms": duration, "error": str(exc)},
            )
            raise exc

        # 4. Log completion metrics
        duration = (time.perf_counter() - start_time) * 1000
        ctx = RequestContext.get()
        success = 200 <= status_code < 400
        
        log_level = "AUDIT"
        if status_code >= 500:
            log_level = "ERROR"
        elif status_code >= 400:
            log_level = "WARNING"

        action_map = {
            "POST": "CREATE",
            "GET": "READ",
            "PUT": "UPDATE",
            "PATCH": "UPDATE",
            "DELETE": "DELETE",
        }
        action = action_map.get(request.method, "READ")

        audit.log(
            description=f"HTTP {request.method} {request.path} completed with {status_code}",
            level=log_level,
            module="system",
            action=action,
            user=ctx.get("user", "SYSTEM"),
            user_role=ctx.get("user_role", ""),
            company_id=ctx.get("company_id", ""),
            branch_id=ctx.get("branch_id", ""),
            request_id=ctx.get("request_id", ""),
            session_id=ctx.get("session_id", ""),
            ip=ctx.get("ip", ip),
            method=request.method,
            endpoint=request.get_full_path(),
            status=status_code,
            success=success,
            metadata={"duration_ms": duration},
        )

        # 5. Clear context to avoid leakage
        RequestContext.clear()
        
        return response
```

To enable this, add it to your `MIDDLEWARE` setting in `settings.py`:

```python
# settings.py
MIDDLEWARE = [
    # ... standard django middlewares ...
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    # Register auditX middleware after Session & Authentication middlewares
    'my_project.middleware.AuditDjangoMiddleware',
]
```

---

## Flask Integration (Request Hooks)

For Flask, you can implement RequestContext management using built-in lifecycle hooks. Since Flask requests run in isolated threads (under standard WSGI servers), cleanup must be performed at request teardown.

```python
import time
import uuid
from flask import Flask, request, g
from auditx import RequestContext, audit

app = Flask(__name__)

@app.before_request
def setup_audit_context():
    g.start_time = time.perf_counter()
    
    # Resolve IP
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "127.0.0.1")
    if "," in ip:
        ip = ip.split(",")[0].strip()

    # Extract headers
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    session_id = request.headers.get("X-Session-ID", "")

    # Bind request variables
    RequestContext.set(
        user="SYSTEM",
        user_role="",
        company_id="",
        branch_id="",
        session_id=session_id,
        request_id=request_id,
        ip=ip
    )

@app.after_request
def log_audit_response(response):
    if not hasattr(g, "start_time"):
        return response

    duration = (time.perf_counter() - g.start_time) * 1000
    ctx = RequestContext.get()
    
    status_code = response.status_code
    success = 200 <= status_code < 400
    
    log_level = "AUDIT"
    if status_code >= 500:
        log_level = "ERROR"
    elif status_code >= 400:
        log_level = "WARNING"

    action_map = {"POST": "CREATE", "GET": "READ", "PUT": "UPDATE", "PATCH": "UPDATE", "DELETE": "DELETE"}
    action = action_map.get(request.method, "READ")

    audit.log(
        description=f"HTTP {request.method} {request.path} completed with {status_code}",
        level=log_level,
        module="system",
        action=action,
        user=ctx.get("user", "SYSTEM"),
        user_role=ctx.get("user_role", ""),
        company_id=ctx.get("company_id", ""),
        branch_id=ctx.get("branch_id", ""),
        request_id=ctx.get("request_id", ""),
        session_id=ctx.get("session_id", ""),
        ip=ctx.get("ip", "127.0.0.1"),
        method=request.method,
        endpoint=request.full_path,
        status=status_code,
        success=success,
        metadata={"duration_ms": duration},
    )
    return response

@app.teardown_request
def clear_audit_context(exception=None):
    # Ensure memory is cleaned up and context doesn't spill into subsequent request threads
    RequestContext.clear()
```

---

## Background Tasks & Celery Integration

When passing executions off to background worker processes (like Celery, RQ, or custom Redis queues), contextvars will not automatically cross process/network boundaries.

You must manually serialize the active `RequestContext` state, pass it to your worker payload, and re-apply it inside the background worker context:

### 1. Serializing Context in a route
```python
# app/routes.py
from fastapi import APIRouter
from auditx import RequestContext
from app.tasks import run_background_report

router = APIRouter()

@router.post("/reports/generate")
async def generate_report():
    # 1. Grab the active request context dict
    parent_context = RequestContext.get()
    
    # 2. Dispatch background task, passing context dict as argument
    run_background_report.delay(parent_context, report_id="REP-992")
    return {"status": "dispatched"}
```

### 2. Restoring Context in the Worker
```python
# app/tasks.py
from celery import Celery
from auditx import RequestContext, audit, BusinessModule, AuditAction

celery_app = Celery("my_tasks", broker="redis://localhost:6379/0")

@celery_app.task
def run_background_report(parent_context: dict, report_id: str):
    # 1. Bind context variables to the celery worker execution thread
    RequestContext.set(
        user=parent_context.get("user", "SYSTEM"),
        user_role=parent_context.get("user_role", ""),
        company_id=parent_context.get("company_id", ""),
        branch_id=parent_context.get("branch_id", ""),
        session_id=parent_context.get("session_id", ""),
        request_id=parent_context.get("request_id", ""),
        ip=parent_context.get("ip", ""),
    )
    
    try:
        # Run report generation logic
        audit.log_transaction(
            "Financial statements exported",
            module=BusinessModule.REPORTING,
            action=AuditAction.EXPORT,
            reference_no=report_id,
            amount=0.0
        )
    finally:
        # 2. Cleanup context variables
        RequestContext.clear()
```

---

## Database Syncing & Hook Callbacks (`on_audit`)

`auditX` supports synchronous, custom callback handlers invoked immediately after writing a log entry to disk. Use this hook to duplicate audit entries into databases (e.g., SQLite, PostgreSQL) or trigger external alert integrations.

> [!WARNING]
> Database integrations should handle exceptions internally. Any unhandled exception raised within your callback will be logged internally in `app.log` but will not block the caller or cause file log write failures.

### Example: Syncing Audit Logs to a Database

```python
import json
import sqlite3
from auditx import configure, AuditEntry

def sync_audit_to_db(entry: AuditEntry) -> None:
    """Callback function executed on every audit event."""
    try:
        # Convert dataclass representation to dictionary
        data = entry.to_dict()
        
        # Open connection to sqlite DB
        conn = sqlite3.connect("my_application.db")
        cursor = conn.cursor()
        
        # Insert audit log into database
        cursor.execute(
            """
            INSERT INTO audit_logs (
                timestamp, level, module, action, description, 
                user, company_id, branch_id, reference_no, data_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data.get("timestamp"),
                data.get("level"),
                data.get("module"),
                data.get("action"),
                data.get("description"),
                data.get("user"),
                data.get("company_id"),
                data.get("branch_id"),
                data.get("reference_no"),
                json.dumps(data)
            )
        )
        conn.commit()
        conn.close()
    except Exception as e:
        # Avoid crashing the application if database write fails.
        # This will automatically log to app.log since configure() captures it.
        raise e

# Register the callback during configuration
configure(
    log_dir="logs",
    on_audit=sync_audit_to_db
)
```

---

## Custom Plain-Text Log Format (`logging_custom`)

While standard audit methods write structured JSON logs to `audit.jsonl` or `security.jsonl`, `logging_custom` enables writing custom-formatted plain-text log lines directly to `app.log`.

This is useful for legacy integration, specific monitoring patterns, or custom text representation.

### Log Format

```text
datetime | user | method | Level | Custom message
```

### Usage

Call `logging_custom` on `audit` or any custom logger instance:

```python
from auditx import audit, RequestContext

# 1. Automatic context extraction:
RequestContext.set(user="manager_user", ip="192.168.1.15")
audit.logging_custom("Application initialization completed", level="info")
# Output:
# 28/06/2026 04:10:59 PM | manager_user | N/A | INFO | Application initialization completed

# 2. Explicit overrides:
audit.logging_custom(
    "User modified custom system setting",
    level="warning",
    user="sys_admin",
    method="POST"
)
# Output:
# 28/06/2026 04:10:59 PM | sys_admin | POST | WARNING | User modified custom system setting

# 3. Passing custom keyword arguments:
audit.logging_custom(
    "Tenant status updated",
    level="info",
    user="billing_service",
    isActive="Not at all"
)
# Output:
# 28/06/2026 04:10:59 PM | billing_service | N/A | INFO | Tenant status updated | {"isActive": "Not at all"}
```

### Method Signature

```python
def logging_custom(
    message: str,
    *,
    level: str = "INFO",
    user: Optional[str] = None,
    method: Optional[str] = None,
    **kwargs: Any,
) -> None:
```

* **`message`** (str): The custom message to print/log.
* **`level`** (str, optional): The log level (defaults to `"INFO"`).
* **`user`** (str, optional): The actor username (falls back to `RequestContext` user or `"SYSTEM"`).
* **`method`** (str, optional): The HTTP request method (falls back to `RequestContext` method or `"N/A"`).
* **`**kwargs`** (Any, optional): Arbitrary custom fields that will be serialized as JSON and appended to the Custom part of the log output.

---

## Public API Reference

### Core Exports

| Component | Type | Description |
| :--- | :--- | :--- |
| `audit` | Proxy | Lazy global proxy instance of `AuditLogger` singleton. |
| `RequestContext` | Class | Context manager holding thread/async-isolated request parameters. |
| `AuditMiddleware` | Middleware | Raw ASGI app wrapper capturing routing details and timings. |
| `configure()` | Function | Reconfigures settings (e.g., `log_dir`, `on_audit`) of global singleton. |
| `create_logger()` | Function | Factory method to initialize separate, isolated `AuditLogger` instances. |
| `create_app()` | Function | Build the read-only web dashboard FastAPI app (`pip install auditX[web]`). |
| `enable_realtime()` | Function | Connect the global logger to the dashboard WebSocket hub. |
| `connect_logger()` | Function | Connect a specific `AuditLogger` to the real-time hub. |
| `mount_audit_viewer()` | Function | Mount the dashboard onto an existing FastAPI application. |
| `audit.alog_*()` | Methods | Async variants of log methods for non-blocking FastAPI handlers. |
| `auditx-ui` | CLI | Launch the web dashboard (`auditx-ui --log-dir ./logs`). |

### Business Enums

* **`LogLevel`**: `DEBUG`, `INFO`, `NORMAL`, `WARNING`, `ERROR`, `CRITICAL`, `AUDIT`, `SECURITY`
* **`BusinessModule`**: `AUTH`, `SALES`, `PURCHASE`, `INVENTORY`, `ACCOUNTING`, `SERVICE`, `CRM`, `HR`, `REPORTING`, `SYSTEM`
* **`AuditAction`**: `CREATE`, `READ`, `UPDATE`, `DELETE`, `APPROVE`, `REJECT`, `VOID`, `POST`, `PAYMENT`, `REFUND`, `TRANSFER`, `ADJUST`, `LOGIN`, `LOGOUT`, `EXPORT`, `IMPORT`

---

## License

Copyright (c) 2026 **auditX**. All rights reserved.

This is proprietary software. Use is permitted only within projects explicitly authorized by auditX. You may not use, copy, modify, or distribute this software in any other project without prior written consent from auditX.

See [LICENSE](LICENSE) for the full terms.
