import asyncio
import json
import logging
import math
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..config import (
    BALANCE_REFRESH_DEFAULT_SECONDS,
    BALANCE_REFRESH_MIN_SECONDS,
    BALANCE_SETTINGS_FILE,
    FOMO_SUPPORTED_CHAINS,
)
from .auth import auth_manager
from .balances import balance_manager
from .persistent_json import atomic_write_json
from .topic import topic_manager
from .runtime_health import runtime_health

logger = logging.getLogger("fomo.balance_refresh")


def _fetch_balances_sync(url: str, jwt: str) -> dict:
    """Execute the same direct HTTP request shape validated by the standalone balance test."""
    request = Request(
        url,
        headers={
            "Authorization": f"Bearer {jwt}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "x-supported-chains": FOMO_SUPPORTED_CHAINS,
            "User-Agent": "FomoBalanceRefresh/1.0",
        },
        method="GET",
    )

    try:
        with urlopen(request, timeout=20) as response:
            status = response.status
            raw = response.read()
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Fomo balances HTTP {exc.code}: {body[:200]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Fomo balances request failed: {exc.reason}") from exc

    if status != 200:
        raise RuntimeError(f"Fomo balances HTTP {status}")

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Fomo balances returned invalid JSON") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("Fomo balances returned an unexpected payload")
    return payload


class BalanceRefreshService:
    """Fetch complete multi-chain balances directly from Fomo on a configurable cadence."""

    def __init__(self, settings_path: Path = BALANCE_SETTINGS_FILE) -> None:
        self._settings_path = settings_path
        self._interval_seconds = self._load_interval()
        self._wake = asyncio.Event()
        self._next_refresh_at: float | None = None

    def _load_interval(self) -> int:
        try:
            data = json.loads(self._settings_path.read_text(encoding="utf-8"))
            value = int(data.get("refreshSeconds")) if isinstance(data, dict) else 0
            if value >= BALANCE_REFRESH_MIN_SECONDS:
                return value
        except Exception:
            pass
        return BALANCE_REFRESH_DEFAULT_SECONDS

    def get_interval(self) -> int:
        return self._interval_seconds

    def get_remaining_seconds(self) -> int:
        """Return whole seconds until the next scheduled scan; zero means due/in progress."""
        if self._next_refresh_at is None:
            return 0
        return max(0, math.ceil(self._next_refresh_at - time.monotonic()))

    def request_refresh(self) -> None:
        """Wake the service so the next scan starts immediately."""
        self._next_refresh_at = time.monotonic()
        self._wake.set()

    def set_interval(self, seconds: int) -> int:
        try:
            seconds = int(seconds)
        except (TypeError, ValueError) as exc:
            raise ValueError("Balance refresh interval must be a whole number of seconds.") from exc
        if seconds < BALANCE_REFRESH_MIN_SECONDS:
            raise ValueError(f"Balance refresh interval must be at least {BALANCE_REFRESH_MIN_SECONDS} seconds.")
        atomic_write_json(self._settings_path, {"refreshSeconds": seconds})
        self._interval_seconds = seconds
        self.request_refresh()
        return seconds

    async def refresh_once(self) -> int:
        user_id = topic_manager.resolve()
        if not user_id:
            raise RuntimeError("no Fomo user id yet — waiting for topicId")
        jwt = await auth_manager.get_valid_jwt()
        url = f"https://prod-api.fomo.family/v2/users/{user_id}/balances"

        # urllib is intentional here: this request shape is the one validated
        # against Fomo's /balances endpoint. Run it in a worker thread so the
        # synchronous standard-library client never blocks the asyncio loop.
        payload = await asyncio.to_thread(_fetch_balances_sync, url, jwt)

        count = await balance_manager.ingest(payload, account_user_id=user_id)
        logger.info("Balances refreshed directly from Fomo: %d", count)
        return count

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            self._next_refresh_at = None
            # Clear before the request so a refresh request that arrives during
            # the fetch remains set and triggers the next scan immediately.
            self._wake.clear()
            try:
                await self.refresh_once()
                await runtime_health.refresh_success("balances")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await balance_manager.set_error(str(exc))
                await runtime_health.refresh_error("balances", exc)
                logger.warning("Balance refresh failed: %s", exc)

            self._next_refresh_at = time.monotonic() + self._interval_seconds
            stop_task = asyncio.create_task(stop_event.wait())
            wake_task = asyncio.create_task(self._wake.wait())
            try:
                done, pending = await asyncio.wait(
                    {stop_task, wake_task},
                    timeout=self._interval_seconds,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                if stop_task in done and stop_task.result():
                    return
            finally:
                for task in (stop_task, wake_task):
                    if not task.done():
                        task.cancel()
                await asyncio.gather(stop_task, wake_task, return_exceptions=True)


balance_refresh_service = BalanceRefreshService()
