# auditX

ERP-grade audit logging for **trading** and **service** businesses. Track who did what, when, and where — with structured JSON trails suitable for compliance, SIEM, and multi-branch operations.

## Install

```bash
pip install auditX
```

**From source (development):**

```bash
git clone https://github.com/Script-By-Lin/auditX.git
cd auditX
pip install -e .
```

## Quick start

```python
from auditx import audit, RequestContext, BusinessModule, AuditAction

# Set user/tenant context once per request or job
RequestContext.set(
    user="admin",
    user_role="manager",
    company_id="CO-001",
    branch_id="BR-YGN",
    ip="192.168.1.10",
)

# Mock user context dictionary
user = {"role": "admin"}

# Security / auth
audit.log_security("User login successful", action=AuditAction.LOGIN, user=user.get("role"))

# Trading — sales, purchase, payments
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

# Inventory
audit.log_inventory(
    "Stock issued for sales order",
    action=AuditAction.TRANSFER,
    product_id="SKU-1001",
    product_name="LED Panel 24W",
    quantity=50,
    warehouse_id="WH-MAIN",
    reference_no="SI-2026-0042",
)

# Service jobs
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

# Field-level change audit (before/after)
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

## Run the demo

```bash
python -m auditx
# or after install:
auditx-demo
```

## Configuration

```python
from auditx import configure, create_logger

# Reconfigure the global singleton at app startup
configure(log_dir="/var/log/my-erp", console=False)

# Or create separate loggers per tenant/service
tenant_logger = create_logger(log_dir="logs/tenant-acme", console=False)
tenant_logger.log_transaction(...)
```

### Log files

| File | Purpose |
|------|---------|
| `logs/audit.jsonl` | Immutable audit trail (one JSON object per line) |
| `logs/security.jsonl` | Auth failures, rate limits, critical security events |
| `logs/app.log` | General application messages (`audit.info()`, etc.) |

## FastAPI Integration (ASGI Middleware)

auditX includes a built-in, async-safe **`AuditMiddleware`** that automatically logs incoming HTTP requests, captures response times/status codes, tracks unhandled exceptions, and handles request-scoped variables (like request IDs and client IPs).

Because it uses Python `contextvars` instead of `threading.local`, request context modifications made by your dependencies or endpoints will correctly propagate to all inner log calls and the final HTTP request log written by the middleware.

### 1. Add Middleware to FastAPI

```python
from fastapi import FastAPI
from auditx import AuditMiddleware

app = FastAPI()

# Register the middleware (it must wrap the entire app)
app.add_middleware(AuditMiddleware)
```

### 2. Update Request Context inside Endpoints/Dependencies

Use `RequestContext.update()` inside your authentication dependency to update user and branch details. Because of async task isolation, this context will be safely scoped to only the current request:

```python
from fastapi import Depends, Header
from auditx import RequestContext, audit, BusinessModule, AuditAction

async def get_current_user(
    x_user: str = Header("SYSTEM"),
    x_role: str = Header(""),
    x_branch: str = Header("")
):
    # Set the authenticated user details for this async request context
    RequestContext.update(
        user=x_user,
        user_role=x_role,
        branch_id=x_branch,
    )
    return x_user

@app.post("/sales/invoice")
async def create_invoice(user: str = Depends(get_current_user)):
    # Any audit log written here automatically inherits user, request_id, and ip
    audit.log_transaction(
        "Sales invoice posted",
        module=BusinessModule.SALES,
        action=AuditAction.POST,
        reference_no="SI-2026-098",
        amount=450000,
    )
    return {"status": "posted"}
```

### 3. Excluded Paths

By default, the middleware will ignore common paths like API docs or favicon. You can customize this when adding the middleware:

```python
app.add_middleware(
    AuditMiddleware, 
    exclude_paths=["/docs", "/redoc", "/openapi.json", "/healthz"]
)
```

## Database hook (optional)

Persist audit entries to your database:

```python
def save_to_db(entry):
    db.execute(
        "INSERT INTO audit_log (data) VALUES (?)",
        [json.dumps(entry.to_dict())],
    )

from auditx import configure
configure(log_dir="logs", on_audit=save_to_db)
```

## Public API

| Export | Description |
|--------|-------------|
| `audit` | Global logger singleton |
| `AuditLogger` | Create custom logger instances |
| `configure()` | Reconfigure the global singleton |
| `create_logger()` | Factory for new logger instances |
| `RequestContext` | Async & thread-safe user/tenant context (`contextvars`-backed) |
| `AuditMiddleware` | ASGI Middleware for FastAPI/Starlette request logging |
| `AuditEntry` | Structured audit record dataclass |
| `BusinessModule` | `SALES`, `PURCHASE`, `INVENTORY`, `SERVICE`, etc. |
| `AuditAction` | `CREATE`, `UPDATE`, `POST`, `PAYMENT`, `LOGIN`, etc. |
| `LogLevel` | `DEBUG`, `INFO`, `AUDIT`, `SECURITY`, `CRITICAL`, etc. |

## License

Copyright (c) 2026 **auditX**. All rights reserved.

This is proprietary software. Use is permitted only within projects explicitly
authorized by auditX. You may not use, copy, modify, or distribute this software
in any other project without prior written consent from auditX.

See [LICENSE](LICENSE) for the full terms.
