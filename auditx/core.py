"""Core audit logger implementation for auditX.

Copyright (c) 2026 auditX. All rights reserved.
Proprietary — not licensed for use in other projects without permission.
"""

from __future__ import annotations

import datetime
import contextvars
import json
import logging
import socket
import threading
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

try:
    from colorama import Fore, init

    init(autoreset=True)
    _COLORAMA = True
except ImportError:
    _COLORAMA = False
    Fore = type("Fore", (), {"GREEN": "", "YELLOW": "", "RED": "", "CYAN": "", "WHITE": "", "MAGENTA": "", "BLUE": ""})()


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    AUDIT = "AUDIT"
    SECURITY = "SECURITY"


class BusinessModule(str, Enum):
    AUTH = "auth"
    SALES = "sales"
    PURCHASE = "purchase"
    INVENTORY = "inventory"
    ACCOUNTING = "accounting"
    SERVICE = "service"
    CRM = "crm"
    HR = "hr"
    REPORTING = "reporting"
    SYSTEM = "system"


class AuditAction(str, Enum):
    CREATE = "CREATE"
    READ = "READ"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    VOID = "VOID"
    POST = "POST"
    PAYMENT = "PAYMENT"
    REFUND = "REFUND"
    TRANSFER = "TRANSFER"
    ADJUST = "ADJUST"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    EXPORT = "EXPORT"
    IMPORT = "IMPORT"


@dataclass
class AuditEntry:
    timestamp: str
    level: str
    module: str
    action: str
    description: str
    user: str = "SYSTEM"
    user_role: str = ""
    company_id: str = ""
    branch_id: str = ""
    entity_type: str = ""
    entity_id: str = ""
    reference_no: str = ""
    amount: Optional[float] = None
    currency: str = "MMK"
    old_values: dict[str, Any] = field(default_factory=dict)
    new_values: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    request_id: str = ""
    session_id: str = ""
    ip: str = ""
    hostname: str = ""
    method: str = ""
    endpoint: str = ""
    status: int = 0
    success: bool = True

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return {k: v for k, v in data.items() if v not in (None, "", {}, [])}


class RequestContext:
    """Carries user and tenant context across a request or background job."""

    _context: contextvars.ContextVar[dict[str, str]] = contextvars.ContextVar(
        "request_context",
        default={
            "user": "SYSTEM",
            "user_role": "",
            "company_id": "",
            "branch_id": "",
            "session_id": "",
            "request_id": "",
            "ip": "",
        },
    )

    @classmethod
    def set(
        cls,
        *,
        user: str = "SYSTEM",
        user_role: str = "",
        company_id: str = "",
        branch_id: str = "",
        session_id: str = "",
        request_id: str = "",
        ip: str = "",
    ) -> None:
        cls._context.set({
            "user": user,
            "user_role": user_role,
            "company_id": company_id,
            "branch_id": branch_id,
            "session_id": session_id,
            "request_id": request_id or str(uuid.uuid4()),
            "ip": ip,
        })

    @classmethod
    def update(cls, **kwargs: Any) -> None:
        """Update specific fields of the request context dynamically."""
        current = dict(cls.get())
        current.update(kwargs)
        cls._context.set(current)

    @classmethod
    def get(cls) -> dict[str, str]:
        return cls._context.get()

    @classmethod
    def clear(cls) -> None:
        cls._context.set({
            "user": "SYSTEM",
            "user_role": "",
            "company_id": "",
            "branch_id": "",
            "session_id": "",
            "request_id": "",
            "ip": "",
        })


class AuditLogger:
    """
    ERP audit logger with structured JSON trails, console output, and domain helpers.

    Log files (under log_dir):
      - audit.jsonl    — immutable audit trail (one JSON object per line)
      - app.log        — human-readable application log
      - security.jsonl — security-sensitive events
    """

    _LEVEL_COLORS = {
        LogLevel.DEBUG.value: Fore.WHITE,
        LogLevel.INFO.value: Fore.CYAN,
        LogLevel.NORMAL.value: Fore.GREEN,
        LogLevel.WARNING.value: Fore.YELLOW,
        LogLevel.ERROR.value: Fore.RED,
        LogLevel.CRITICAL.value: Fore.RED,
        LogLevel.AUDIT.value: Fore.MAGENTA,
        LogLevel.SECURITY.value: Fore.RED,
        "EXTREME": Fore.RED,
    }

    _METHOD_COLORS = {
        "GET": Fore.CYAN,
        "POST": Fore.GREEN,
        "PUT": Fore.YELLOW,
        "PATCH": Fore.YELLOW,
        "DELETE": Fore.RED,
    }

    def __init__(
        self,
        log_dir: str | Path = "logs",
        app_log_file: str = "app.log",
        audit_log_file: str = "audit.jsonl",
        security_log_file: str = "security.jsonl",
        max_file_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5,
        console: bool = True,
        on_audit: Optional[Callable[[AuditEntry], None]] = None,
    ):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.app_log_path = self.log_dir / app_log_file
        self.audit_log_path = self.log_dir / audit_log_file
        self.security_log_path = self.log_dir / security_log_file

        self.max_file_bytes = max_file_bytes
        self.backup_count = backup_count
        self.console = console
        self.on_audit = on_audit

        self.hostname = socket.gethostname()
        try:
            self.default_ip = socket.gethostbyname(self.hostname)
        except socket.gaierror:
            self.default_ip = "127.0.0.1"

        self._lock = threading.Lock()
        self._ip_counter: dict[str, int] = {}
        self._rate_limit_window: dict[str, datetime.datetime] = {}

        logger_name = f"auditx.app.{id(self)}"
        self._app_logger = logging.getLogger(logger_name)
        if not self._app_logger.handlers:
            handler = logging.FileHandler(self.app_log_path, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
            self._app_logger.addHandler(handler)
            self._app_logger.setLevel(logging.DEBUG)
            self._app_logger.propagate = False

    @staticmethod
    def _iso_timestamp() -> str:
        return datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(timespec="seconds")

    @staticmethod
    def _display_timestamp() -> str:
        return datetime.datetime.now().strftime("%d/%m/%Y %I:%M:%S %p")

    def _format_level(self, level: str) -> str:
        level = level.upper()
        if _COLORAMA:
            color = self._LEVEL_COLORS.get(level, Fore.WHITE)
            return color + level
        return level

    def _format_method(self, method: str) -> str:
        method = method.upper()
        if _COLORAMA:
            color = self._METHOD_COLORS.get(method, Fore.WHITE)
            return color + method
        return method

    def _rotate_if_needed(self, path: Path) -> None:
        if not path.exists() or path.stat().st_size < self.max_file_bytes:
            return
        for i in range(self.backup_count - 1, 0, -1):
            src = path.with_suffix(path.suffix + f".{i}")
            dst = path.with_suffix(path.suffix + f".{i + 1}")
            if src.exists():
                src.replace(dst)
        path.replace(path.with_suffix(path.suffix + ".1"))

    def _append_line(self, path: Path, line: str) -> None:
        with self._lock:
            self._rotate_if_needed(path)
            with path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")

    def _emit_console(self, entry: AuditEntry) -> None:
        if not self.console:
            return
        ts = self._display_timestamp()
        method = self._format_method(entry.method) if entry.method else "N/A"
        level = self._format_level(entry.level)
        ref = f" [{entry.reference_no}]" if entry.reference_no else ""
        entity = f" {entry.entity_type}:{entry.entity_id}" if entry.entity_type else ""
        amount = f" {entry.amount:,.2f} {entry.currency}" if entry.amount is not None else ""
        print(
            f"{ts} | {level} | {entry.module}/{entry.action} | "
            f"{method} {entry.endpoint} | {entry.status} | "
            f"{entry.description}{ref}{entity}{amount} | "
            f"{entry.user}@{entry.branch_id or 'HQ'} | req:{entry.request_id[:8]} | IP:{entry.ip}"
        )

    def _write_audit(self, entry: AuditEntry) -> None:
        self._append_line(self.audit_log_path, json.dumps(entry.to_dict(), ensure_ascii=False, default=str))

        if entry.level in (LogLevel.SECURITY.value, LogLevel.CRITICAL.value, "EXTREME"):
            self._append_line(self.security_log_path, json.dumps(entry.to_dict(), ensure_ascii=False, default=str))

        if self.on_audit:
            try:
                self.on_audit(entry)
            except Exception as exc:
                self._app_logger.error("on_audit callback failed: %s", exc)

    def _build_entry(
        self,
        *,
        description: str,
        level: str = LogLevel.AUDIT.value,
        module: str = BusinessModule.SYSTEM.value,
        action: str = AuditAction.READ.value,
        user: Optional[str] = None,
        user_role: str = "",
        company_id: str = "",
        branch_id: str = "",
        entity_type: str = "",
        entity_id: str = "",
        reference_no: str = "",
        amount: Optional[float] = None,
        currency: str = "MMK",
        old_values: Optional[dict[str, Any]] = None,
        new_values: Optional[dict[str, Any]] = None,
        metadata: Optional[dict[str, Any]] = None,
        request_id: str = "",
        session_id: str = "",
        ip: Optional[str] = None,
        method: str = "",
        endpoint: str = "",
        status: int = 200,
        success: bool = True,
    ) -> AuditEntry:
        ctx = RequestContext.get()
        return AuditEntry(
            timestamp=self._iso_timestamp(),
            level=level.upper(),
            module=module,
            action=action,
            description=description,
            user=user or ctx.get("user", "SYSTEM"),
            user_role=user_role or ctx.get("user_role", ""),
            company_id=company_id or ctx.get("company_id", ""),
            branch_id=branch_id or ctx.get("branch_id", ""),
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id else "",
            reference_no=reference_no,
            amount=amount,
            currency=currency,
            old_values=old_values or {},
            new_values=new_values or {},
            metadata=metadata or {},
            request_id=request_id or ctx.get("request_id", "") or str(uuid.uuid4()),
            session_id=session_id or ctx.get("session_id", ""),
            ip=ip or ctx.get("ip") or self.default_ip,
            hostname=self.hostname,
            method=method.upper() if method else "",
            endpoint=endpoint,
            status=status,
            success=success,
        )

    def check_rate_limit(self, ip: str, limit: int = 5, window_seconds: int = 60) -> bool:
        now = datetime.datetime.now()
        window_start = self._rate_limit_window.get(ip)

        if window_start is None or (now - window_start).total_seconds() > window_seconds:
            self._rate_limit_window[ip] = now
            self._ip_counter[ip] = 1
            return True

        self._ip_counter[ip] = self._ip_counter.get(ip, 0) + 1
        return self._ip_counter[ip] <= limit

    def reset_rate_limit(self, ip: str) -> None:
        self._ip_counter.pop(ip, None)
        self._rate_limit_window.pop(ip, None)

    def log(
        self,
        description: str,
        *,
        level: str = LogLevel.AUDIT.value,
        module: str = BusinessModule.SYSTEM.value,
        action: str = AuditAction.READ.value,
        **kwargs: Any,
    ) -> AuditEntry:
        entry = self._build_entry(
            description=description,
            level=level,
            module=module,
            action=action,
            **kwargs,
        )
        self._emit_console(entry)
        self._write_audit(entry)
        return entry

    def log_change(
        self,
        description: str,
        *,
        module: BusinessModule | str,
        action: AuditAction | str,
        entity_type: str,
        entity_id: str,
        old_values: dict[str, Any],
        new_values: dict[str, Any],
        reference_no: str = "",
        **kwargs: Any,
    ) -> AuditEntry:
        return self.log(
            description=description,
            level=LogLevel.AUDIT.value,
            module=module.value if isinstance(module, BusinessModule) else module,
            action=action.value if isinstance(action, AuditAction) else action,
            entity_type=entity_type,
            entity_id=entity_id,
            reference_no=reference_no,
            old_values=old_values,
            new_values=new_values,
            **kwargs,
        )

    def log_transaction(
        self,
        description: str,
        *,
        module: BusinessModule,
        action: AuditAction,
        reference_no: str,
        amount: float,
        currency: str = "MMK",
        entity_type: str = "",
        entity_id: str = "",
        party: str = "",
        **kwargs: Any,
    ) -> AuditEntry:
        metadata = kwargs.pop("metadata", {}) or {}
        if party:
            metadata["party"] = party
        return self.log(
            description=description,
            level=LogLevel.AUDIT.value,
            module=module.value,
            action=action.value,
            reference_no=reference_no,
            amount=amount,
            currency=currency,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata=metadata,
            **kwargs,
        )

    def log_inventory(
        self,
        description: str,
        *,
        action: AuditAction,
        product_id: str,
        product_name: str = "",
        quantity: float,
        unit: str = "pcs",
        warehouse_id: str = "",
        reference_no: str = "",
        **kwargs: Any,
    ) -> AuditEntry:
        metadata = kwargs.pop("metadata", {}) or {}
        metadata.update({"product_name": product_name, "quantity": quantity, "unit": unit, "warehouse_id": warehouse_id})
        return self.log(
            description=description,
            level=LogLevel.AUDIT.value,
            module=BusinessModule.INVENTORY.value,
            action=action.value,
            entity_type="product",
            entity_id=product_id,
            reference_no=reference_no,
            metadata=metadata,
            **kwargs,
        )

    def log_service(
        self,
        description: str,
        *,
        action: AuditAction,
        job_id: str,
        customer_id: str = "",
        technician: str = "",
        service_type: str = "",
        status_label: str = "",
        amount: Optional[float] = None,
        **kwargs: Any,
    ) -> AuditEntry:
        metadata = kwargs.pop("metadata", {}) or {}
        metadata.update({
            "customer_id": customer_id,
            "technician": technician,
            "service_type": service_type,
            "status": status_label,
        })
        return self.log(
            description=description,
            level=LogLevel.AUDIT.value,
            module=BusinessModule.SERVICE.value,
            action=action.value,
            entity_type="service_job",
            entity_id=job_id,
            amount=amount,
            metadata=metadata,
            **kwargs,
        )

    def log_security(
        self,
        description: str,
        *,
        action: AuditAction = AuditAction.LOGIN,
        user: str = "UNKNOWN",
        ip: Optional[str] = None,
        success: bool = True,
        **kwargs: Any,
    ) -> AuditEntry:
        level = LogLevel.SECURITY.value if not success else LogLevel.AUDIT.value
        check_ip = ip or RequestContext.get().get("ip") or self.default_ip

        if not self.check_rate_limit(check_ip):
            description = "Rate limit exceeded - possible brute force"
            level = LogLevel.CRITICAL.value
            success = False

        return self.log(
            description=description,
            level=level,
            module=BusinessModule.AUTH.value,
            action=action.value,
            user=user,
            ip=check_ip,
            success=success,
            **kwargs,
        )

    def debug(self, message: str, **extra: Any) -> None:
        self._app_logger.debug(self._format_app_message(message, extra))

    def info(self, message: str, **extra: Any) -> None:
        self._app_logger.info(self._format_app_message(message, extra))

    def warning(self, message: str, **extra: Any) -> None:
        self._app_logger.warning(self._format_app_message(message, extra))

    def error(self, message: str, **extra: Any) -> None:
        self._app_logger.error(self._format_app_message(message, extra))

    def critical(self, message: str, **extra: Any) -> None:
        self._app_logger.critical(self._format_app_message(message, extra))

    @staticmethod
    def _format_app_message(message: str, extra: dict[str, Any]) -> str:
        if not extra:
            return message
        return f"{message} | {json.dumps(extra, ensure_ascii=False, default=str)}"

    def auditing(
        self,
        description: str,
        level: str = "NORMAL",
        user: str = "SYSTEM",
        method: str = "N/A",
        endpoint: str = "/",
        status: int = 200,
        ip: Optional[str] = None,
        **kwargs: Any,
    ) -> AuditEntry:
        return self.log(
            description=description,
            level=level,
            module=kwargs.pop("module", BusinessModule.SYSTEM.value),
            action=kwargs.pop("action", AuditAction.READ.value),
            user=user,
            method=method,
            endpoint=endpoint,
            status=status,
            ip=ip,
            **kwargs,
        )

    def logging_custom(
        self,
        message: str,
        *,
        level: str = "INFO",
        user: Optional[str] = None,
        method: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Log a custom message in the format: datetime | user | method | Level | Custom"""
        dt = self._display_timestamp()
        ctx = RequestContext.get()
        user_val = user or ctx.get("user", "SYSTEM")
        method_val = method or ctx.get("method") or "N/A"
        level_val = level.upper()

        custom_part = message
        if kwargs:
            custom_part = f"{message} | {json.dumps(kwargs, ensure_ascii=False, default=str)}"

        # Format for file (no colors)
        file_line = f"{dt} | {user_val} | {method_val.upper()} | {level_val} | {custom_part}"
        self._append_line(self.app_log_path, file_line)

        # Format for console (with colors if console is True)
        if self.console:
            console_method = self._format_method(method_val) if method_val != "N/A" else "N/A"
            console_level = self._format_level(level_val)
            console_line = f"{dt} | {user_val} | {console_method} | {console_level} | {custom_part}"
            print(console_line)

