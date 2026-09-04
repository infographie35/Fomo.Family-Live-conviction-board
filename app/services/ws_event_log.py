"""Bounded in-memory Fomo trade log with coalesced atomic persistence."""

import asyncio
import logging
import math
from datetime import datetime, timezone
from pathlib import Path

from ..config import WS_LOG_FILE, WS_LOG_FLUSH_DELAY_SECONDS
from .persistent_json import atomic_write_json

logger = logging.getLogger("fomo.ws_event_log")
MAX_EVENTS = 5000


def _json_scalar(value):
    """Keep expected scalar fields JSON-safe without truncating valid strings."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return None


class WsEventLog:
    """Keep one session in memory and persist bursts through one controlled writer."""

    def __init__(
        self,
        path: Path = WS_LOG_FILE,
        *,
        flush_delay_seconds: float = WS_LOG_FLUSH_DELAY_SECONDS,
    ) -> None:
        self._path = path
        self._flush_delay_seconds = max(0.0, float(flush_delay_seconds))
        self._lock = asyncio.Lock()
        self._started_at = datetime.now(timezone.utc).isoformat()
        self._events: list[dict] = []
        self._version = 0
        self._dirty = True
        self._writer_task: asyncio.Task | None = None
        self._flush_now = asyncio.Event()
        self._persistence_error: str | None = None

    def _payload_locked(self) -> dict:
        return {"startedAt": self._started_at, "events": list(self._events)}

    def _ensure_writer(self) -> None:
        if self._writer_task is None or self._writer_task.done():
            self._writer_task = asyncio.create_task(self._writer(), name="ws-log-writer")

    async def _writer(self) -> None:
        try:
            try:
                await asyncio.wait_for(
                    self._flush_now.wait(), timeout=self._flush_delay_seconds
                )
            except asyncio.TimeoutError:
                pass
            self._flush_now.clear()

            while True:
                async with self._lock:
                    if not self._dirty:
                        return
                    payload = self._payload_locked()
                    self._dirty = False
                try:
                    await asyncio.to_thread(atomic_write_json, self._path, payload)
                except Exception as exc:
                    async with self._lock:
                        self._dirty = True
                        self._persistence_error = str(exc)[:500]
                    logger.error("WS log persistence failed: %s", exc)
                    return
                async with self._lock:
                    self._persistence_error = None
                    if not self._dirty:
                        return
        finally:
            self._writer_task = None

    async def append(
        self,
        payload: dict,
        *,
        accepted: bool,
        following: bool,
        favorite: bool,
    ) -> None:
        event_type = payload.get("type")
        if event_type not in {"swap_buy", "swap_sell"}:
            return
        item = {
            "id": _json_scalar(payload.get("id")),
            "tradeId": _json_scalar(payload.get("tradeId")),
            "createdAt": _json_scalar(payload.get("createdAt")),
            "type": event_type,
            "userId": _json_scalar(payload.get("userId")),
            "displayName": _json_scalar(payload.get("displayName")),
            "userHandle": _json_scalar(payload.get("userHandle")),
            "usdAmount": _json_scalar(payload.get("usdAmount")),
            "marketCap": _json_scalar(payload.get("marketCap")),
            "ticker": _json_scalar(payload.get("ticker")),
            "tokenAddress": _json_scalar(payload.get("tokenAddress")),
            "networkId": _json_scalar(payload.get("networkId")),
            "following": bool(following),
            "favorite": bool(favorite),
            "accepted": bool(accepted),
        }
        async with self._lock:
            self._events.append(item)
            if len(self._events) > MAX_EVENTS:
                del self._events[:-MAX_EVENTS]
            self._version += 1
            self._dirty = True
            self._ensure_writer()

    async def flush(self) -> bool:
        """Flush current events; persistence failure never interrupts ingestion."""
        async with self._lock:
            self._ensure_writer()
            writer = self._writer_task
            self._flush_now.set()
        if writer is not None:
            await asyncio.shield(writer)
        async with self._lock:
            return not self._dirty and self._persistence_error is None

    async def close(self) -> bool:
        return await self.flush()

    async def snapshot(self) -> dict:
        async with self._lock:
            return {
                "startedAt": self._started_at,
                "version": self._version,
                "count": len(self._events),
                "events": list(reversed(self._events)),
                "persistenceError": self._persistence_error,
            }


ws_event_log = WsEventLog()
