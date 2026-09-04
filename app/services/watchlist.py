import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from ..config import BASE_DIR
from .persistent_json import atomic_write_json

logger = logging.getLogger("fomo.watchlist")
WATCHLIST_FILE = BASE_DIR / "fomo_watchlist.json"


class WatchlistManager:
    """Persistent token watchlist with a last-known card snapshot.

    Membership and the most recent known token payload are kept on disk. This
    makes WATCHLIST useful immediately after a restart, before the live Fomo
    stream has reconstructed those tokens. Live store data always overrides the
    cached payload when it is available.
    """

    def __init__(self, path: Path = WATCHLIST_FILE) -> None:
        self._lock = asyncio.Lock()
        self._path = path
        self._keys: set[str] = set()
        self._tokens: dict[str, dict] = {}
        self._updated_at: str | None = None
        self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return

        keys = data.get("keys", []) if isinstance(data, dict) else []
        tokens = data.get("tokens", {}) if isinstance(data, dict) else {}
        self._keys = {str(key) for key in keys if key}
        if isinstance(tokens, dict):
            self._tokens = {
                str(key): dict(value)
                for key, value in tokens.items()
                if str(key) in self._keys and isinstance(value, dict)
            }
        self._updated_at = data.get("updatedAt") if isinstance(data, dict) else None

    def _persist(self, keys: set[str], tokens: dict[str, dict], updated_at: str | None) -> None:
        atomic_write_json(
            self._path,
            {
                "keys": sorted(keys),
                "tokens": {key: tokens[key] for key in sorted(tokens)},
                "updatedAt": updated_at,
            },
        )

    async def keys(self) -> list[str]:
        async with self._lock:
            return sorted(self._keys)

    async def toggle(self, key: str, live_token: dict | None) -> bool:
        """Toggle membership, persisting a full card snapshot when adding."""
        async with self._lock:
            next_keys = set(self._keys)
            next_tokens = dict(self._tokens)
            if key in next_keys:
                next_keys.remove(key)
                next_tokens.pop(key, None)
                watched = False
            else:
                if not isinstance(live_token, dict):
                    raise KeyError(key)
                next_keys.add(key)
                next_tokens[key] = dict(live_token)
                watched = True

            updated_at = datetime.now(timezone.utc).isoformat()
            await asyncio.to_thread(self._persist, next_keys, next_tokens, updated_at)
            self._keys = next_keys
            self._tokens = next_tokens
            self._updated_at = updated_at
            return watched

    async def sync_live(self, live_tokens: list[dict]) -> bool:
        """Refresh saved card payloads from live state without changing membership."""
        live_by_key = {
            str(token.get("key")): token
            for token in live_tokens
            if isinstance(token, dict) and token.get("key")
        }

        async with self._lock:
            next_tokens = dict(self._tokens)
            for key in self._keys:
                live = live_by_key.get(key)
                if live is not None and next_tokens.get(key) != live:
                    next_tokens[key] = dict(live)

            changed = next_tokens != self._tokens
            if changed:
                updated_at = datetime.now(timezone.utc).isoformat()
                await asyncio.to_thread(
                    self._persist, self._keys, next_tokens, updated_at
                )
                self._tokens = next_tokens
                self._updated_at = updated_at
            return changed

    async def snapshot(self, live_tokens: list[dict]) -> dict:
        """Return watched cards, preferring live state over the persisted cache."""
        live_by_key = {
            str(token.get("key")): token
            for token in live_tokens
            if isinstance(token, dict) and token.get("key")
        }

        async with self._lock:
            tokens = []
            live_count = 0
            for key in sorted(self._keys):
                source = live_by_key.get(key)
                cached = source is None
                if source is None:
                    source = self._tokens.get(key)
                if not isinstance(source, dict):
                    continue
                item = dict(source)
                item["watchlistCached"] = cached
                tokens.append(item)
                if not cached:
                    live_count += 1

            tokens.sort(
                key=lambda item: str(item.get("lastActivityAt") or ""), reverse=True
            )
            return {
                "keys": sorted(self._keys),
                "tokens": tokens,
                "liveCount": live_count,
                "updatedAt": self._updated_at,
            }


watchlist_manager = WatchlistManager()
