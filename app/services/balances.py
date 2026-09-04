import asyncio
import logging
import math
from datetime import datetime, timezone
from pathlib import Path

from ..config import BASE_DIR
from .persistent_json import atomic_write_json

logger = logging.getLogger("fomo.balances")
BALANCES_FILE = BASE_DIR / "fomo_balances.json"


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


class BalanceManager:
    """Normalized last-known Fomo portfolio snapshot persisted across restarts.

    The direct balance refresher supplies complete multi-chain API responses.
    Every persisted snapshot is tagged with its Fomo account userId so data from
    another account, including legacy untagged caches, is never exposed as current.
    """

    def __init__(self, path: Path = BALANCES_FILE) -> None:
        self._lock = asyncio.Lock()
        self._path = path
        self._balances: dict[str, dict] = {}
        self._account_user_id: str | None = None
        self._updated_at: str | None = None
        self._last_error: str | None = "waiting for direct Fomo balance refresh"
        self._load()

    @staticmethod
    def token_key(network_id, token_address) -> str:
        return f"{network_id}:{str(token_address).lower()}"

    def _load(self) -> None:
        try:
            import json
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        self._account_user_id = (
            str(data.get("accountUserId")).strip()
            if isinstance(data, dict) and data.get("accountUserId")
            else None
        )
        items = data.get("balances", []) if isinstance(data, dict) else []
        for item in items:
            if isinstance(item, dict) and item.get("key"):
                self._balances[str(item["key"])] = item
        if self._account_user_id and isinstance(data.get("balances"), list):
            self._updated_at = data.get("updatedAt")
            self._last_error = None

    @staticmethod
    def _extract(payload: object) -> list[dict] | None:
        if not isinstance(payload, dict):
            return None
        response = payload.get("responseObject")
        candidates = [payload.get("balances")]
        if isinstance(response, dict):
            candidates.append(response.get("balances"))
        for candidate in candidates:
            if isinstance(candidate, list):
                if not all(isinstance(item, dict) for item in candidate):
                    raise ValueError("balances list contained non-object entries")
                return candidate
        return None

    @classmethod
    def _normalize(cls, item: dict) -> dict | None:
        balance = item.get("balance") if isinstance(item.get("balance"), dict) else {}
        token_result = item.get("tokenFilterResult") if isinstance(item.get("tokenFilterResult"), dict) else {}
        token = token_result.get("token") if isinstance(token_result.get("token"), dict) else {}
        user_token = item.get("userToken") if isinstance(item.get("userToken"), dict) else {}

        token_address = _pick(user_token, "tokenAddress") or _pick(balance, "tokenAddress") or _pick(token, "address")
        network_id = _pick(user_token, "networkId") or _pick(token, "networkId")
        if not token_address or network_id is None:
            return None

        # `balance.shiftedBalance` is the wallet balance reported by Fomo and is
        # canonical for BALANCE. userToken is trade-accounting state and can lag.
        amount = _number(_pick(balance, "shiftedBalance"))
        if amount is None:
            amount = _number(_pick(user_token, "humanAmountRemaining"))
        price = _number(_pick(token_result, "priceUSD"))
        value = amount * price if amount is not None and price is not None else None
        cost_basis = _number(_pick(user_token, "currentCostBasisUsd"))
        unrealized = value - cost_basis if value is not None and cost_basis is not None else None

        return {
            "key": cls.token_key(network_id, token_address),
            "tokenAddress": str(token_address),
            "networkId": network_id,
            "name": _pick(token, "name") or _pick(token.get("info", {}) if isinstance(token.get("info"), dict) else {}, "name") or "",
            "symbol": _pick(token, "symbol") or _pick(token.get("info", {}) if isinstance(token.get("info"), dict) else {}, "symbol") or "?",
            "image": _pick(token.get("info", {}) if isinstance(token.get("info"), dict) else {}, "imageThumbUrl", "imageSmallUrl") or "",
            "amount": amount,
            "priceUsd": price,
            "valueUsd": value,
            "averageEntryPriceUsd": _number(_pick(user_token, "averageEntryPriceUsd")),
            "currentCostBasisUsd": cost_basis,
            "unrealizedPnlUsd": unrealized,
            "realizedPnlUsd": _number(_pick(user_token, "currentRealizedPnlUsd")),
            "updatedAt": _pick(user_token, "updatedAt"),
        }

    async def ingest(self, payload: object, *, account_user_id: str) -> int:
        account_user_id = str(account_user_id or "").strip()
        if not account_user_id:
            raise ValueError("account_user_id is required for a balance snapshot")
        if isinstance(payload, dict) and payload.get("success") is False:
            raise ValueError(str(payload.get("message") or "Fomo balances request failed"))
        raw = self._extract(payload)
        if raw is None:
            raise ValueError("balances payload did not contain a balances list")
        normalized = [entry for item in raw if (entry := self._normalize(item))]
        if raw and not normalized:
            raise ValueError("balances payload contained entries but none were usable")

        updated_at = datetime.now(timezone.utc).isoformat()
        data = {
            "accountUserId": account_user_id,
            "updatedAt": updated_at,
            "balances": normalized,
        }
        async with self._lock:
            await asyncio.to_thread(atomic_write_json, self._path, data)
            self._balances = {entry["key"]: entry for entry in normalized}
            self._account_user_id = account_user_id
            self._updated_at = updated_at
            self._last_error = None
        logger.info("Balances snapshot updated: %d", len(normalized))
        return len(normalized)

    async def set_error(self, message: str) -> None:
        async with self._lock:
            self._last_error = message

    async def snapshot(self, account_user_id: str | None) -> dict:
        """Expose balances only when the persisted snapshot belongs to the active account."""
        expected = str(account_user_id or "").strip() or None
        async with self._lock:
            if expected is None:
                return {
                    "accountUserId": None,
                    "balances": [],
                    "updatedAt": None,
                    "lastError": "waiting for Fomo account identity",
                }
            if self._account_user_id != expected:
                return {
                    "accountUserId": expected,
                    "balances": [],
                    "updatedAt": None,
                    "lastError": self._last_error or "waiting for a balance refresh for the active Fomo account",
                }
            return {
                "accountUserId": self._account_user_id,
                "balances": list(self._balances.values()),
                "updatedAt": self._updated_at,
                "lastError": self._last_error,
            }


balance_manager = BalanceManager()
