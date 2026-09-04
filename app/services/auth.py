import asyncio
import base64
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..config import JWT_FILE, PRIVY_APP_ID
from .persistent_json import atomic_write_json

logger = logging.getLogger("fomo.auth")


class AuthWaiting(RuntimeError):
    """No usable JWT yet — the browser bridge hasn't supplied a fresh one."""


def _decode_jwt_claims(token: str) -> dict:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return {}
        payload = parts[1]
        payload += "=" * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload.encode("ascii"))
        data = json.loads(decoded.decode("utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _looks_like_jwt(value: object) -> bool:
    return isinstance(value, str) and value.count(".") == 2


def _flatten_candidates(candidates: object) -> dict[str, str]:
    # The bridge sends {source_key: value}; a value may itself be a JWT string,
    # a JSON-quoted string, or a nested object. Flatten to leaf strings so the
    # picker sees raw token values.
    flat: dict[str, str] = {}

    def add(key: str, val: object) -> None:
        if val is None:
            return
        if isinstance(val, str):
            s = val.strip()
            if s and (s[0] in "{[" or (s[0] == '"' and s[-1] == '"')):
                try:
                    add(key, json.loads(s))
                    return
                except Exception:
                    pass
            if s:
                flat[key] = s
        elif isinstance(val, dict):
            for k, v in val.items():
                add(f"{key}.{k}", v)
        elif isinstance(val, list):
            for i, v in enumerate(val):
                add(f"{key}[{i}]", v)

    if isinstance(candidates, dict):
        for k, v in candidates.items():
            add(str(k), v)
    return flat


def _pick_fomo_jwt(flat: dict[str, str]) -> str | None:
    # Accept only a Fomo user-session JWT: audience is the Fomo Privy app id
    # and it is not a PAT. Keep the one with the furthest expiry.
    best: str | None = None
    best_exp = -1
    for value in flat.values():
        if not _looks_like_jwt(value):
            continue
        claims = _decode_jwt_claims(value)
        if claims.get("aud") == PRIVY_APP_ID and claims.get("att") != "pat":
            try:
                exp = int(claims.get("exp") or 0)
            except (TypeError, ValueError):
                exp = 0
            if exp > best_exp:
                best_exp = exp
                best = value
    return best


@dataclass(frozen=True)
class AuthStatus:
    has_credentials: bool
    expires_at: str | None
    expires_in_seconds: int | None
    last_refresh_at: str | None
    last_error: str | None


class AuthManager:
    """JWT-only. The Fomo access JWT is supplied by the Chrome bridge, which
    intercepts the browser's own Fomo WebSocket challengeResponse. This class
    never talks to Privy: it just stores the freshest JWT and serves it."""

    def __init__(self, jwt_file: Path = JWT_FILE) -> None:
        self.jwt_file = jwt_file
        self._lock = asyncio.Lock()
        self._last_refresh_at: datetime | None = None

    def _read_jwt(self) -> str | None:
        if not self.jwt_file.exists():
            return None
        try:
            with self.jwt_file.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            return None
        jwt = (data.get("jwt") or "").strip() if isinstance(data, dict) else ""
        return jwt or None

    @staticmethod
    def _jwt_exp(jwt: str) -> int | None:
        exp = _decode_jwt_claims(jwt).get("exp")
        try:
            return int(exp) if exp is not None else None
        except (TypeError, ValueError):
            return None

    @classmethod
    def _expires_in_seconds(cls, jwt: str) -> int | None:
        exp = cls._jwt_exp(jwt)
        if exp is None:
            return None
        return exp - int(datetime.now(timezone.utc).timestamp())

    async def ingest_credentials(self, candidates: object) -> AuthStatus:
        # Called by the bridge. Writes jwt.json only when the incoming JWT is at
        # least as fresh as the stored one, so an old frame never downgrades a
        # newer token.
        flat = _flatten_candidates(candidates)
        new_jwt = _pick_fomo_jwt(flat)
        if not new_jwt:
            raise RuntimeError("No Fomo-compatible JWT in browser payload")

        async with self._lock:
            cur = self._read_jwt()
            if not cur or (self._jwt_exp(new_jwt) or 0) >= (self._jwt_exp(cur) or 0):
                if new_jwt != cur:
                    await asyncio.to_thread(
                        atomic_write_json, self.jwt_file, {"jwt": new_jwt}
                    )
                    logger.info("jwt.json updated from browser bridge ingest")
                self._last_refresh_at = datetime.now(timezone.utc)

        return await self.status()

    async def get_valid_jwt(self) -> str:
        jwt = self._read_jwt()
        if not jwt:
            raise AuthWaiting("no JWT yet — open/refresh Fomo in Chrome")
        expires_in = self._expires_in_seconds(jwt)
        if expires_in is not None and expires_in <= 0:
            raise AuthWaiting("JWT expired — waiting for Fomo to issue a fresh one")
        return jwt

    async def status(self) -> AuthStatus:
        jwt = self._read_jwt()
        if not jwt:
            return AuthStatus(
                has_credentials=False,
                expires_at=None,
                expires_in_seconds=None,
                last_refresh_at=(
                    self._last_refresh_at.isoformat() if self._last_refresh_at else None
                ),
                last_error=None,
            )
        exp = self._jwt_exp(jwt)
        return AuthStatus(
            has_credentials=True,
            expires_at=(
                datetime.fromtimestamp(exp, tz=timezone.utc).isoformat()
                if exp is not None
                else None
            ),
            expires_in_seconds=self._expires_in_seconds(jwt),
            last_refresh_at=(
                self._last_refresh_at.isoformat() if self._last_refresh_at else None
            ),
            last_error=None,
        )


auth_manager = AuthManager()
