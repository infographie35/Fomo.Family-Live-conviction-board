"""Small in-process health registry for long-running dashboard components."""

import asyncio
from datetime import datetime, timezone

from ..config import HEALTH_WS_STALE_SECONDS


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RuntimeHealth:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._ws_connected = False
        self._ws_last_message_at: datetime | None = None
        self._ws_last_error: str | None = "not connected yet"
        self._refreshes: dict[str, dict[str, str | None]] = {}
        self._tasks: dict[str, asyncio.Task] = {}

    def register_task(self, name: str, task: asyncio.Task) -> None:
        self._tasks[name] = task

    async def ws_connected(self) -> None:
        async with self._lock:
            self._ws_connected = True
            self._ws_last_error = None

    async def ws_message(self) -> None:
        async with self._lock:
            self._ws_last_message_at = _utc_now()

    async def ws_disconnected(self, error: object | None = None) -> None:
        async with self._lock:
            self._ws_connected = False
            if error is not None:
                self._ws_last_error = str(error)[:500]

    async def refresh_success(self, name: str) -> None:
        async with self._lock:
            self._refreshes[name] = {
                "lastSuccessAt": _utc_now().isoformat(),
                "lastError": None,
            }

    async def refresh_error(self, name: str, error: object) -> None:
        async with self._lock:
            current = self._refreshes.get(name, {"lastSuccessAt": None})
            self._refreshes[name] = {
                "lastSuccessAt": current.get("lastSuccessAt"),
                "lastError": str(error)[:500],
            }

    async def snapshot(self) -> dict:
        async with self._lock:
            now = _utc_now()
            stale = bool(
                self._ws_connected
                and (
                    self._ws_last_message_at is None
                    or (now - self._ws_last_message_at).total_seconds()
                    > HEALTH_WS_STALE_SECONDS
                )
            )
            task_states = {}
            dead_task = False
            for name, task in self._tasks.items():
                error = None
                if task.done() and not task.cancelled():
                    try:
                        exception = task.exception()
                    except asyncio.CancelledError:
                        exception = None
                    error = str(exception)[:500] if exception else "stopped unexpectedly"
                    dead_task = True
                task_states[name] = {
                    "running": not task.done(),
                    "error": error,
                }

            degraded = not self._ws_connected or stale or dead_task
            return {
                "ok": not degraded,
                "degraded": degraded,
                "components": {
                    "websocket": {
                        "connected": self._ws_connected,
                        "stale": stale,
                        "lastMessageAt": (
                            self._ws_last_message_at.isoformat()
                            if self._ws_last_message_at else None
                        ),
                        "lastError": self._ws_last_error,
                    },
                    "tasks": task_states,
                    "refreshes": dict(self._refreshes),
                },
            }


runtime_health = RuntimeHealth()
