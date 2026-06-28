"""Backward-compatible shim — use `pip install auditX` and `from auditx import audit` instead."""

import warnings

warnings.warn(
    "AuditTrailX.logging_core is deprecated. Install auditX: pip install auditX",
    DeprecationWarning,
    stacklevel=2,
)

from auditx import (  # noqa: F401
    AuditAction,
    AuditEntry,
    AuditLogger,
    BusinessModule,
    LogLevel,
    RequestContext,
    audit,
    configure,
    create_logger,
)

__all__ = [
    "AuditAction",
    "AuditEntry",
    "AuditLogger",
    "BusinessModule",
    "LogLevel",
    "RequestContext",
    "audit",
    "configure",
    "create_logger",
]
