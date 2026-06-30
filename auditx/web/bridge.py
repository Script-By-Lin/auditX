"""Connect AuditLogger instances to the real-time web hub."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from auditx.core import LogLevel
from auditx.web.hub import RealtimeHub, get_hub

if TYPE_CHECKING:
    from auditx.core import AuditEntry, AuditLogger


def connect_logger(logger: AuditLogger, hub: RealtimeHub | None = None) -> RealtimeHub:
    """Publish every audit write to the dashboard hub for instant WebSocket push."""
    hub = hub or get_hub(logger.log_dir)
    if getattr(logger, "_auditx_realtime_connected", False):
        return hub

    previous = logger.on_audit

    def _callback(entry: AuditEntry) -> None:
        payload = entry.to_dict()
        hub.publish_sync("audit", payload)
        if entry.level in (LogLevel.SECURITY.value, LogLevel.CRITICAL.value, "EXTREME"):
            hub.publish_sync("security", payload)
        if previous:
            previous(entry)

    logger.on_audit = _callback
    logger._auditx_realtime_connected = True  # type: ignore[attr-defined]
    return hub


def enable_realtime(logger: AuditLogger | None = None, log_dir: str | Path | None = None) -> RealtimeHub:
    """Enable real-time dashboard push for a logger (defaults to global `audit` singleton)."""
    if logger is None:
        from auditx import _get_default_logger

        logger = _get_default_logger()
    if log_dir is not None and Path(logger.log_dir).resolve() != Path(log_dir).resolve():
        raise ValueError("log_dir does not match the configured logger log_dir")
    return connect_logger(logger)


def try_connect_default_logger(log_dir: str | Path) -> RealtimeHub | None:
    """Auto-connect the global audit logger when its log_dir matches the dashboard."""
    try:
        from auditx import _get_default_logger

        logger = _get_default_logger()
        if Path(logger.log_dir).resolve() == Path(log_dir).resolve():
            return connect_logger(logger)
    except Exception:
        return None
    return None
