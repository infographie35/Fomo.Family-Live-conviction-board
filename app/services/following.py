import asyncio
import json
import logging
import math
from datetime import datetime, timezone
from pathlib import Path

from ..config import BASE_DIR
from .persistent_json import atomic_write_json

logger = logging.getLogger("fomo.following")
FAVORITES_FILE = BASE_DIR / "fomo_favorites.json"


def _number(value):
    if value is None or value == "":
        return None
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _pick(obj: dict, *keys):
    for key in keys:
        if obj.get(key) is not None:
            return obj.get(key)
    return None


class FollowingManager:
    """Atomic cache of directly refreshed Fomo following profiles and local favorites.

    The refresh service walks every `followingPaginate` page before calling
    :meth:`ingest`, so a failed partial scan never replaces the last complete
    snapshot. Favorites remain local and survive profile refreshes.
    """

    def __init__(self, favorites_file: Path = FAVORITES_FILE) -> None:
        self._lock = asyncio.Lock()
        self._profiles: dict[str, dict] = {}
        self._favorites_file = favorites_file
        self._favorites = self._load_favorites()
        self._updated_at: str | None = None
        self._last_error: str | None = "waiting for direct Fomo following refresh"

    def _load_favorites(self) -> set[str]:
        try:
            data = json.loads(self._favorites_file.read_text(encoding="utf-8"))
            return {str(x) for x in data.get("favorites", []) if x}
        except Exception:
            return set()

    def _persist_favorites(self, favorites: set[str]) -> None:
        atomic_write_json(self._favorites_file, {"favorites": sorted(favorites)})

    @staticmethod
    def _extract_users(payload: object) -> list[dict] | None:
        if not isinstance(payload, dict):
            return None
        candidates = [payload.get("users")]
        response = payload.get("responseObject")
        if isinstance(response, dict):
            candidates.extend([response.get("users"), response.get("data")])
        data = payload.get("data")
        if isinstance(data, dict):
            candidates.append(data.get("users"))
        elif isinstance(data, list):
            candidates.append(data)
        for candidate in candidates:
            if isinstance(candidate, list):
                if not all(isinstance(item, dict) for item in candidate):
                    raise ValueError("following users list contained non-object entries")
                return candidate
        return None

    @staticmethod
    def _normalize(user: dict) -> dict | None:
        user_id = _pick(user, "id", "userId", "user_id")
        if not user_id:
            return None
        return {
            "id": str(user_id),
            "displayName": _pick(user, "displayName", "name") or "",
            "userHandle": _pick(user, "userHandle", "handle", "username") or "",
            "followers": _number(_pick(user, "followers", "followerCount", "numFollowers")),
            "trades": _number(_pick(user, "numTrades", "trades", "tradeCount", "swapCount")),
            "volume": _number(_pick(user, "totalVolume", "volume", "tradingVolume")),
            "pnl24h": _number(_pick(user, "pnl24h", "pnl24H", "pnl_24h")),
            "profilePicture": _pick(
                user, "profilePictureLink", "profilePicture", "avatarUrl", "imageUrl"
            ) or "",
        }

    async def ingest(self, payload: object) -> int:
        """Atomically replace the cache with one fully paginated direct Fomo snapshot."""
        users = self._extract_users(payload)
        if users is None:
            raise ValueError("following payload did not contain a users list")
        normalized = [p for user in users if (p := self._normalize(user))]
        if not normalized and users:
            raise ValueError("following payload contained users but none were usable")
        if isinstance(payload, dict) and payload.get("success") is False:
            raise ValueError(str(payload.get("message") or "Fomo following request failed"))

        async with self._lock:
            self._profiles = {p["id"]: p for p in normalized}
            self._updated_at = datetime.now(timezone.utc).isoformat()
            self._last_error = None
        logger.info("Following profiles refreshed directly from Fomo: %d", len(normalized))
        return len(normalized)

    async def set_error(self, message: str) -> None:
        """Expose refresh failures without discarding the last complete snapshot."""
        async with self._lock:
            self._last_error = message

    async def favorite_ids(self) -> list[str]:
        """Return the local favorite user ids used to decorate live ALERTS."""
        async with self._lock:
            return sorted(user_id for user_id in self._favorites if user_id in self._profiles)

    async def match_status(self, user_id: str | None) -> tuple[bool, bool]:
        """Return whether a WS trader is followed and locally marked favorite."""
        if not user_id:
            return False, False
        key = str(user_id)
        async with self._lock:
            return key in self._profiles, key in self._profiles and key in self._favorites

    async def snapshot(self) -> dict:
        async with self._lock:
            profiles = []
            for profile in self._profiles.values():
                item = dict(profile)
                item["favorite"] = item["id"] in self._favorites
                profiles.append(item)
            return {
                "profiles": profiles,
                "updatedAt": self._updated_at,
                "lastError": self._last_error,
            }

    async def toggle_favorite(self, user_id: str) -> bool:
        async with self._lock:
            next_favorites = set(self._favorites)
            if user_id in next_favorites:
                next_favorites.remove(user_id)
                favorite = False
            else:
                next_favorites.add(user_id)
                favorite = True
            await asyncio.to_thread(self._persist_favorites, next_favorites)
            self._favorites = next_favorites
            return favorite


following_manager = FollowingManager()
