from __future__ import annotations

import asyncio
import json
import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from ..config import BASE_DIR, PONS_GRADUATIONS_POLL_SECONDS, PONS_NETWORK_ID
from .persistent_json import atomic_write_json

logger = logging.getLogger("fomo.pons_graduations")

PONS_GRADUATIONS_URL = "https://www.ponsfamily.com/api/pons-launches/graduations"
PONS_GRADUATIONS_PARAMS = {"catalog": "1", "v": "12"}
PONS_GRADUATIONS_FILE = BASE_DIR / "pons_graduations.json"
PONS_LOCAL_TZ = ZoneInfo("Europe/Zagreb")
PONS_REQUEST_TIMEOUT_SECONDS = 15


def _parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _finite_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _quote_symbol(item: dict[str, Any]) -> str:
    quote = item.get("quoteAsset")
    if isinstance(quote, dict) and quote.get("symbol"):
        return str(quote["symbol"])
    return "?"


def _duration_label(seconds: int | None) -> str:
    if seconds is None or seconds < 0:
        return "?"
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)
    if days:
        return f"{days}d{hours:02d}h{minutes:02d}m"
    if hours:
        return f"{hours}h{minutes:02d}m{secs:02d}s"
    return f"{minutes}m{secs:02d}s"


def _normalize_graduation(item: dict[str, Any]) -> dict[str, Any] | None:
    contract = item.get("token")
    graduated_at = _parse_iso(item.get("graduatedAt"))
    if not isinstance(contract, str) or not contract or graduated_at is None:
        return None

    launched_at = _parse_iso(item.get("launchedAt"))
    duration_seconds = None
    if launched_at is not None:
        raw_seconds = int((graduated_at - launched_at).total_seconds())
        if raw_seconds >= 0:
            duration_seconds = raw_seconds

    return {
        "contract": contract,
        "symbol": str(item.get("symbol") or "?"),
        "name": str(item.get("name") or "?"),
        "pair": _quote_symbol(item),
        "marketCapUsd": _finite_number(item.get("marketCapUsd")),
        "launchedAt": launched_at.isoformat() if launched_at else None,
        "graduatedAt": graduated_at.isoformat(),
        "graduatedAtLocal": graduated_at.astimezone(PONS_LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S"),
        "durationSeconds": duration_seconds,
        "duration": _duration_label(duration_seconds),
        # PONS Launchpad graduations tracked by this endpoint are Robinhood-chain
        # tokens. Keeping the chain explicit lets the existing Fomo URL helper be
        # reused instead of creating a PONS-specific hyperlink format.
        "networkId": PONS_NETWORK_ID,
        "tokenAddress": contract,
    }


def _fetch_catalog_sync() -> list[dict[str, Any]]:
    url = f"{PONS_GRADUATIONS_URL}?{urlencode(PONS_GRADUATIONS_PARAMS)}"
    request = Request(
        url,
        headers={
            "Accept": "*/*",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": "https://www.ponsfamily.com/launchpad",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/151.0.0.0 Safari/537.36"
            ),
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=PONS_REQUEST_TIMEOUT_SECONDS) as response:
            status = response.status
            raw = response.read()
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"PONS graduations HTTP {exc.code}: {body[:200]}") from exc
    except URLError as exc:
        raise RuntimeError(f"PONS graduations request failed: {exc.reason}") from exc

    if status != 200:
        raise RuntimeError(f"PONS graduations HTTP {status}")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("PONS graduations returned invalid JSON") from exc
    if not isinstance(payload, list):
        raise RuntimeError("PONS graduations returned an unexpected payload")
    return [item for item in payload if isinstance(item, dict)]


class PonsGraduationManager:
    """Persistent append-only log of new PONS graduations.

    The upstream catalogue is not stable: old rows may disappear and reappear.
    A persisted graduatedAt watermark therefore defines new events. On a fresh
    install the first successful catalogue is baseline only; later rows strictly
    newer than that watermark are appended and survive dashboard restarts.
    """

    def __init__(self, path: Path = PONS_GRADUATIONS_FILE) -> None:
        self._lock = asyncio.Lock()
        self._path = path
        self._items: dict[str, dict[str, Any]] = {}
        self._watermark: datetime | None = None
        self._updated_at: str | None = None
        self._last_error: str | None = None
        self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return
        if not isinstance(data, dict):
            return
        self._watermark = _parse_iso(data.get("watermark"))
        self._updated_at = data.get("updatedAt") if isinstance(data.get("updatedAt"), str) else None
        for item in data.get("graduations", []):
            if isinstance(item, dict) and isinstance(item.get("contract"), str):
                self._items[item["contract"].lower()] = item

    def _payload(self) -> dict[str, Any]:
        items = sorted(
            self._items.values(),
            key=lambda item: _parse_iso(item.get("graduatedAt")) or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        return {
            "watermark": self._watermark.isoformat() if self._watermark else None,
            "updatedAt": self._updated_at,
            "graduations": items,
        }

    async def ingest_catalog(self, catalog: list[dict[str, Any]]) -> tuple[int, bool]:
        normalized = [row for item in catalog if (row := _normalize_graduation(item)) is not None]
        latest = max((_parse_iso(row["graduatedAt"]) for row in normalized), default=None)
        now = datetime.now(timezone.utc).isoformat()

        async with self._lock:
            # The first successful fetch establishes the same baseline semantics
            # as the standalone watcher: existing catalogue rows are not emitted
            # as newly graduated merely because the dashboard was just installed.
            if self._watermark is None:
                if latest is None:
                    raise RuntimeError("PONS baseline contains no valid graduatedAt")
                self._watermark = latest
                self._updated_at = now
                self._last_error = None
                await asyncio.to_thread(atomic_write_json, self._path, self._payload())
                return 0, True

            candidates = [
                row
                for row in normalized
                if (_parse_iso(row["graduatedAt"]) or datetime.min.replace(tzinfo=timezone.utc)) > self._watermark
                and row["contract"].lower() not in self._items
            ]
            candidates.sort(key=lambda row: _parse_iso(row["graduatedAt"]) or datetime.min.replace(tzinfo=timezone.utc))

            for row in candidates:
                self._items[row["contract"].lower()] = row

            if candidates:
                newest = max(_parse_iso(row["graduatedAt"]) for row in candidates)
                if newest is not None and newest > self._watermark:
                    self._watermark = newest

            self._updated_at = now
            self._last_error = None
            await asyncio.to_thread(atomic_write_json, self._path, self._payload())
            return len(candidates), False

    async def set_error(self, message: str) -> None:
        async with self._lock:
            self._last_error = message

    async def snapshot(self) -> dict[str, Any]:
        async with self._lock:
            payload = self._payload()
            payload["lastError"] = self._last_error
            payload["count"] = len(payload["graduations"])
            return payload


class PonsGraduationWatcher:
    """Poll PONS every three seconds and append only genuinely new graduations."""

    def __init__(self, manager: PonsGraduationManager) -> None:
        self._manager = manager

    async def refresh_once(self) -> int:
        catalog = await asyncio.to_thread(_fetch_catalog_sync)
        inserted, baseline = await self._manager.ingest_catalog(catalog)
        if baseline:
            logger.info("PONS graduations baseline established: %d visible rows", len(catalog))
        elif inserted:
            logger.info("PONS graduations appended: %d", inserted)
        return inserted

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            started = asyncio.get_running_loop().time()
            try:
                await self.refresh_once()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await self._manager.set_error(str(exc))
                logger.warning("PONS graduation poll failed: %s", exc)

            elapsed = asyncio.get_running_loop().time() - started
            timeout = max(0.0, PONS_GRADUATIONS_POLL_SECONDS - elapsed)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                pass


pons_graduation_manager = PonsGraduationManager()
pons_graduation_watcher = PonsGraduationWatcher(pons_graduation_manager)
