"""Example showing auditX integration with FastAPI.

This script acts as a self-contained demonstration and test suite using FastAPI's
`TestClient` to simulate actual API request/response cycles.
"""

import json
import os
import shutil
from pathlib import Path

# Safe imports for FastAPI and TestClient
try:
    from fastapi import Depends, FastAPI, Header
    from fastapi.testclient import TestClient
except ImportError:
    import sys
    print("Error: FastAPI is required to run this example. Installing required packages...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "fastapi", "httpx"])
    from fastapi import Depends, FastAPI, Header
    from fastapi.testclient import TestClient

from auditx import (
    AuditAction,
    AuditMiddleware,
    BusinessModule,
    RequestContext,
    audit,
    configure,
)

# 1. Reconfigure the global logger to log to a test directory
TEST_LOG_DIR = Path("test_logs")
if TEST_LOG_DIR.exists():
    shutil.rmtree(TEST_LOG_DIR)

configure(log_dir=TEST_LOG_DIR, console=True)

# 2. Define the FastAPI Application
app = FastAPI(title="auditX FastAPI Demo")

# 3. Add the auditX ASGI Middleware
app.add_middleware(AuditMiddleware)


# 4. Define a mock authentication dependency
async def get_current_user(
    x_user: str = Header("SYSTEM"),
    x_role: str = Header(""),
    x_company: str = Header(""),
    x_branch: str = Header(""),
) -> str:
    """Extract user credentials from headers and update the RequestContext."""
    RequestContext.update(
        user=x_user,
        user_role=x_role,
        company_id=x_company,
        branch_id=x_branch,
    )
    return x_user


# 5. Define API Routes
@app.get("/items")
async def get_items(user: str = Depends(get_current_user)):
    """Simple read request."""
    # Context will contain headers values
    return {"message": "Hello World", "authenticated_user": user}


@app.post("/items")
async def create_item(user: str = Depends(get_current_user)):
    """Write/Creation request that triggers a domain-level audit log."""
    # Write a business domain log
    audit.log_change(
        description="New product SKU-9900 registered",
        module=BusinessModule.INVENTORY,
        action=AuditAction.CREATE,
        entity_type="product",
        entity_id="SKU-9900",
        old_values={},
        new_values={"name": "Gaming Keyboard", "price": 125000, "currency": "MMK"},
    )
    return {"status": "success", "item": "SKU-9900"}


@app.get("/error")
async def trigger_error(user: str = Depends(get_current_user)):
    """Simulate an internal server error to check exception logging."""
    raise ValueError("Simulated database connection failure")


# 6. Test Suite execution
def run_demo() -> None:
    client = TestClient(app)

    print("\n--- Running FastAPI Demo & Test Suite ---")

    # Request 1: GET /items (anonymous system user)
    print("\n[Request 1] GET /items (anonymous)")
    response = client.get("/items")
    print(f"Response: {response.status_code} | {response.json()}")

    # Request 2: POST /items (authenticated user: linlinaung)
    print("\n[Request 2] POST /items (authenticated user: linlinaung)")
    headers = {
        "x-user": "linlinaung",
        "x-role": "admin",
        "x-company": "CO-001",
        "x-branch": "BR-YGN",
        "x-request-id": "req-custom-id-12345",
    }
    response = client.post("/items", headers=headers)
    print(f"Response: {response.status_code} | {response.json()}")

    # Request 3: GET /error (authenticated user: staff_user)
    print("\n[Request 3] GET /error (simulated internal exception)")
    headers = {
        "x-user": "staff_user",
        "x-role": "staff",
        "x-company": "CO-001",
        "x-branch": "BR-MDY",
    }
    try:
        client.get("/error", headers=headers)
    except ValueError:
        print("Caught expected simulated ValueError in client test runner.")

    # 7. Print and verify the resulting audit.jsonl output
    print("\n--- Verification: Contents of test_logs/audit.jsonl ---")
    audit_file = TEST_LOG_DIR / "audit.jsonl"
    if audit_file.exists():
        with audit_file.open("r", encoding="utf-8") as f:
            for line in f:
                log_entry = json.loads(line)
                print(f"\nAudit Log Entry:")
                print(f"  Timestamp:   {log_entry.get('timestamp')}")
                print(f"  Level:       {log_entry.get('level')}")
                print(f"  Module/Act:  {log_entry.get('module')}/{log_entry.get('action')}")
                print(f"  Description: {log_entry.get('description')}")
                print(f"  User context:{log_entry.get('user')} ({log_entry.get('user_role')}) at branch {log_entry.get('branch_id') or 'N/A'}")
                print(f"  HTTP request:{log_entry.get('method')} {log_entry.get('endpoint')} | Status: {log_entry.get('status')}")
                print(f"  Request ID:  {log_entry.get('request_id')}")
                if log_entry.get("new_values"):
                    print(f"  New Values:  {log_entry.get('new_values')}")
    else:
        print("Error: audit.jsonl not found!")


if __name__ == "__main__":
    run_demo()
