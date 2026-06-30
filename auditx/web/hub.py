"""In-process real-time broadcast hub for audit log entries."""

from __future__ import annotations

import asyncio
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any

LogSource = str


class RealtimeHub:
    """Thread-safe pub/sub hub bridging sync log writes to async web clients."""

    def __init__(self, max_recent: int = 500) -> None:
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._recent: deque[dict[str, Any]] = deque(maxlen=max_recent)

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=500)
        with self._lock:
            self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        with self._lock:
            self._subscribers.discard(queue)

    def publish_sync(self, source: LogSource, entry: dict[str, Any]) -> None:
        event = {"source": source, "entry": entry, "ts": time.time()}
        with self._lock:
            self._recent.append(event)
            subscribers = list(self._subscribers)
            loop = self._loop

        if not loop or not subscribers:
            return

        for queue in subscribers:
            try:
                loop.call_soon_threadsafe(queue.put_nowait, event)
            except asyncio.QueueFull:
                pass

    def recent(self, source: LogSource | None = None, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            events = list(self._recent)
        if source:
            events = [event for event in events if event.get("source") == source]
        return events[-limit:]


_hubs: dict[str, RealtimeHub] = {}
_hubs_lock = threading.Lock()


def get_hub(log_dir: str | Path) -> RealtimeHub:
    key = str(Path(log_dir).resolve())
    with _hubs_lock:
        if key not in _hubs:
            _hubs[key] = RealtimeHub()
        return _hubs[key]
