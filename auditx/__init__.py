"""
auditX — ERP-grade audit logging for trading and service businesses.

Copyright (c) 2026 auditX. All rights reserved.
Proprietary — not licensed for use in other projects without permission.

Install:
    pip install auditX

Quick start:
    from auditx import audit, RequestContext, BusinessModule, AuditAction

    RequestContext.set(user="admin", company_id="CO-001", branch_id="BR-YGN")
    audit.log_transaction(
        "Sales invoice posted",
        module=BusinessModule.SALES,
        action=AuditAction.POST,
        reference_no="SI-2026-0042",
        amount=1_250_000,
    )
"""

from __future__ import annotations

from typing import Any, Optional

from auditx.core import (
    AuditAction,
    AuditEntry,
    AuditLogger,
    BusinessModule,
    LogLevel,
    RequestContext,
)

try:
    from auditx.fastapi import AuditMiddleware
except ImportError:
    class AuditMiddleware:  # type: ignore
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise ImportError("Please install starlette and fastapi to use AuditMiddleware.")

__version__ = "0.1.2"
__author__ = "auditX"
__license__ = "Proprietary"
__all__ = [
    "__version__",
    "AuditAction",
    "AuditEntry",
    "AuditLogger",
    "BusinessModule",
    "LogLevel",
    "RequestContext",
    "AuditMiddleware",
    "audit",
    "configure",
    "create_logger",
]

_default_logger: Optional[AuditLogger] = None


def create_logger(**kwargs: Any) -> AuditLogger:
    """Create a new AuditLogger instance with custom settings."""
    return AuditLogger(**kwargs)


def configure(**kwargs: Any) -> AuditLogger:
    """Replace the global `audit` singleton (e.g. set log_dir, disable console)."""
    global _default_logger
    _default_logger = AuditLogger(**kwargs)
    return _default_logger


def _get_default_logger() -> AuditLogger:
    global _default_logger
    if _default_logger is None:
        _default_logger = AuditLogger(log_dir="logs")
    return _default_logger


class _AuditProxy:
    """Lazy proxy so `from auditx import audit` uses the configured singleton."""

    def __getattr__(self, name: str) -> Any:
        return getattr(_get_default_logger(), name)

    def __repr__(self) -> str:
        return repr(_get_default_logger())


audit = _AuditProxy()
