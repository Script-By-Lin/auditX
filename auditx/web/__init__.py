"""Web dashboard for browsing auditX log files."""

from __future__ import annotations

from auditx.web.bridge import connect_logger, enable_realtime, try_connect_default_logger
from auditx.web.hub import RealtimeHub, get_hub
from auditx.web.server import create_app, main, mount_audit_viewer

__all__ = [
    "RealtimeHub",
    "connect_logger",
    "create_app",
    "enable_realtime",
    "get_hub",
    "main",
    "mount_audit_viewer",
    "try_connect_default_logger",
]
