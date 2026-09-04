import asyncio
import json
import logging
import math
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..config import (
    FOLLOWING_REFRESH_DEFAULT_SECONDS,
    FOLLOWING_REFRESH_MIN_SECONDS,
    FOLLOWING_SETTINGS_FILE,
)
from .auth import auth_manager
from .following import following_manager
from .persistent_json import atomic_write_json
from .topic import topic_manager
from .runtime_health import runtime_health

logger = logging.getLogger("fomo.following_refresh")
MAX_FOLLOWING_PAGES = 20


def _fetch_following_page_sync(url: str, jwt: str) -> dict:
    """Fetch one Following page with the request shape validated by the standalone test."""
    request = Request(
        url,
        headers={
            "Authorization": f"Bearer {jwt}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "User-Agent": "FomoFollowingRefresh/1.0",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=20) as response:
            status = response.status
            raw = response.read()
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Fomo following HTTP {exc.code}: {body[:200]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Fomo following request failed: {exc.reason}") from exc

    if status != 200:
        raise RuntimeError(f"Fomo following HTTP {status}")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Fomo following returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Fomo following returned an unexpected payload")
    if payload.get("success") is False:
        raise RuntimeError(str(payload.get("message") or "Fomo following request failed"))
    return payload


def _extract_users(payload: dict) -> list[dict] | None:
    response = payload.get("responseObject")
    candidates = [payload.get("users")]
    if isinstance(response, dict):
        candidates.append(response.get("users"))
    candidates.append(payload.get("data"))
    for candidate in candidates:
        if isinstance(candidate, list):
            if not all(isinstance(item, dict) for item in candidate):
                raise RuntimeError("Fomo following users list contained non-object entries")
            return candidate
    return None


def _fetch_all_following_sync(base_url: str, jwt: str) -> dict:
    """Walk Fomo's validated `lastId` cursor and return one complete unique snapshot."""
    users_by_id: dict[str, dict] = {}
    seen_cursors: set[str] = set()
    url = base_url

    for _ in range(MAX_FOLLOWING_PAGES):
        payload = _fetch_following_page_sync(url, jwt)
        users = _extract_users(payload)
        if users is None:
            raise RuntimeError("Fomo following response did not contain a users list")
        if not users:
            return {
                "success": True,
                "message": "Following found",
                "responseObject": {"users": list(users_by_id.values())},
            }

        for user in users:
            user_id = user.get("id")
            if user_id:
                users_by_id[str(user_id)] = user

        last_id = str(users[-1].get("id") or "")
        if not last_id:
            raise RuntimeError("Fomo following page ended with a user without id")
        if last_id in seen_cursors:
            raise RuntimeError("Fomo following pagination repeated a lastId cursor")
        seen_cursors.add(last_id)
        url = f"{base_url}?{urlencode({'lastId': last_id})}"

    raise RuntimeError(f"Fomo following exceeded {MAX_FOLLOWING_PAGES} pages")


class FollowingRefreshService:
    """Refresh the complete Following snapshot directly from Fomo on a saved cadence."""

    def __init__(self, settings_path: Path = FOLLOWING_SETTINGS_FILE) -> None:
        self._settings_path = settings_path
        self._interval_seconds = self._load_interval()
        self._wake = asyncio.Event()
        self._next_refresh_at: float | None = None

    def _load_interval(self) -> int:
        try:
            data = json.loads(self._settings_path.read_text(encoding="utf-8"))
            value = int(data.get("refreshSeconds")) if isinstance(data, dict) else 0
            if value >= FOLLOWING_REFRESH_MIN_SECONDS:
                return value
        except Exception:
            pass
        return FOLLOWING_REFRESH_DEFAULT_SECONDS

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
            raise ValueError("Following refresh interval must be a whole number of seconds.") from exc
        if seconds < FOLLOWING_REFRESH_MIN_SECONDS:
            raise ValueError(
                f"Following refresh interval must be at least {FOLLOWING_REFRESH_MIN_SECONDS} seconds."
            )
        atomic_write_json(self._settings_path, {"refreshSeconds": seconds})
        self._interval_seconds = seconds
        self.request_refresh()
        return seconds

    async def refresh_once(self) -> int:
        user_id = topic_manager.resolve()
        if not user_id:
            raise RuntimeError("no Fomo user id yet — waiting for topicId")
        jwt = await auth_manager.get_valid_jwt()
        base_url = f"https://prod-api.fomo.family/v2/users/{user_id}/followingPaginate"

        # urllib + lastId are intentional: this is the exact direct pagination
        # contract validated against the live account before moving it backend-side.
        payload = await asyncio.to_thread(_fetch_all_following_sync, base_url, jwt)
        count = await following_manager.ingest(payload)
        logger.info("Following direct scan complete: %d profiles", count)
        return count

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            self._next_refresh_at = None
            self._wake.clear()
            try:
                await self.refresh_once()
                await runtime_health.refresh_success("following")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                message = str(exc)
                await following_manager.set_error(message)
                await runtime_health.refresh_error("following", exc)
                logger.warning("Following refresh failed: %s", message)

            self._next_refresh_at = time.monotonic() + self._interval_seconds
            try:
                await asyncio.wait_for(self._wait_for_wake_or_stop(stop_event), timeout=self._interval_seconds)
            except asyncio.TimeoutError:
                pass

    async def _wait_for_wake_or_stop(self, stop_event: asyncio.Event) -> None:
        stop_task = asyncio.create_task(stop_event.wait())
        wake_task = asyncio.create_task(self._wake.wait())
        try:
            await asyncio.wait({stop_task, wake_task}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            stop_task.cancel()
            wake_task.cancel()
            await asyncio.gather(stop_task, wake_task, return_exceptions=True)


following_refresh_service = FollowingRefreshService()
