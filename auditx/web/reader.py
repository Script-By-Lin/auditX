"""Read and filter auditX JSONL log files."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Literal

LogSource = Literal["audit", "security"]


@dataclass
class LogQuery:
    source: LogSource = "audit"
    limit: int = 50
    offset: int = 0
    module: str = ""
    level: str = ""
    user: str = ""
    branch_id: str = ""
    q: str = ""


class LogReader:
    """Read-only access to audit.jsonl and security.jsonl files."""

    def __init__(
        self,
        log_dir: str | Path,
        audit_log_file: str = "audit.jsonl",
        security_log_file: str = "security.jsonl",
    ) -> None:
        self.log_dir = Path(log_dir)
        self.audit_log_path = self.log_dir / audit_log_file
        self.security_log_path = self.log_dir / security_log_file

    def _path_for(self, source: LogSource) -> Path:
        return self.security_log_path if source == "security" else self.audit_log_path

    def _iter_entries(self, path: Path) -> Iterator[dict[str, Any]]:
        if not path.exists():
            return
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue

    @staticmethod
    def _matches(entry: dict[str, Any], query: LogQuery) -> bool:
        if query.module and entry.get("module", "").lower() != query.module.lower():
            return False
        if query.level and entry.get("level", "").upper() != query.level.upper():
            return False
        if query.user and query.user.lower() not in entry.get("user", "").lower():
            return False
        if query.branch_id and query.branch_id.lower() not in entry.get("branch_id", "").lower():
            return False
        if query.q:
            haystack = json.dumps(entry, ensure_ascii=False, default=str).lower()
            if query.q.lower() not in haystack:
                return False
        return True

    def read(self, query: LogQuery) -> tuple[list[dict[str, Any]], int]:
        path = self._path_for(query.source)
        matched = [entry for entry in self._iter_entries(path) if self._matches(entry, query)]
        total = len(matched)
        if query.offset:
            matched = matched[query.offset :]
        if query.limit >= 0:
            matched = matched[: query.limit]
        matched.reverse()
        return matched, total

    def stats(self) -> dict[str, Any]:
        audit_entries = list(self._iter_entries(self.audit_log_path))
        security_entries = list(self._iter_entries(self.security_log_path))

        def summarize(entries: list[dict[str, Any]]) -> dict[str, Any]:
            modules: dict[str, int] = {}
            levels: dict[str, int] = {}
            failures = 0
            for entry in entries:
                modules[entry.get("module", "unknown")] = modules.get(entry.get("module", "unknown"), 0) + 1
                levels[entry.get("level", "UNKNOWN")] = levels.get(entry.get("level", "UNKNOWN"), 0) + 1
                if entry.get("success") is False:
                    failures += 1
            return {
                "total": len(entries),
                "failures": failures,
                "modules": modules,
                "levels": levels,
                "latest_timestamp": entries[-1].get("timestamp") if entries else None,
            }

        return {
            "log_dir": str(self.log_dir.resolve()),
            "audit": summarize(audit_entries),
            "security": summarize(security_entries),
        }

    def tail(self, source: LogSource, after_line: int = 0) -> tuple[list[dict[str, Any]], int]:
        path = self._path_for(source)
        entries: list[dict[str, Any]] = []
        line_no = 0
        for entry in self._iter_entries(path):
            line_no += 1
            if line_no > after_line:
                entries.append(entry)
        return entries, line_no
