import asyncio
import json
import logging
import math
import time
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import (
    DEFAULT_FIRST_ALERT_MC_CUTOFF,
    DEFAULT_INACTIVE_TOKEN_HOURS,
    DASHBOARD_SETTINGS_FILE,
    FOMO_AUX_MARKET_REVALIDATION_COOLDOWN_SECONDS,
    MAX_EVENT_FUTURE_SKEW_SECONDS,
    NEW_BADGE_SECONDS,
    POSITION_DUST_FRACTION,
    SOLD_COOLDOWN_SECONDS,
    TRADE_EVENT_WINDOW_MINUTES,
    TRADE_EVENT_DEDUP_MAX_ENTRIES,
    TRADE_EVENT_DEDUP_TTL_SECONDS,
)
from .models import BuyerState, SoldBuyerState, TokenState, TradeEventState
from .services.persistent_json import atomic_write_json


logger = logging.getLogger("fomo.store")


@dataclass(frozen=True)
class FomoApplyResult:
    accepted: bool
    duplicate: bool = False
    malformed: bool = False

    def __bool__(self) -> bool:
        return self.accepted


class DashboardStore:
    def __init__(
        self,
        settings_path: Path = DASHBOARD_SETTINGS_FILE,
        *,
        event_dedup_ttl_seconds: float = TRADE_EVENT_DEDUP_TTL_SECONDS,
        event_dedup_max_entries: int = TRADE_EVENT_DEDUP_MAX_ENTRIES,
        monotonic_clock=time.monotonic,
    ) -> None:
        self._tokens: dict[str, TokenState] = {}
        self._lock = asyncio.Lock()
        self._version = 0
        self._settings_path = settings_path
        self._first_alert_mc_cutoff, self._inactive_token_hours = self._load_settings()
        self._event_dedup_ttl_seconds = max(0.0, float(event_dedup_ttl_seconds))
        self._event_dedup_max_entries = max(1, int(event_dedup_max_entries))
        self._monotonic_clock = monotonic_clock
        self._seen_event_ids: OrderedDict[str, float] = OrderedDict()
        # Manual FORGET is stronger than automatic inactivity cleanup: forgotten
        # tokens are ignored for the rest of this process. Admission history is
        # kept separately so inactivity cleanup cannot accidentally re-apply the
        # first-alert cutoff to a token that was already accepted.
        self._forgotten_tokens: set[str] = set()
        self._admitted_tokens: set[str] = set()
        # A token rejected by its first usable Fomo BUY MC stays rejected for the
        # rest of this process. Otherwise a later, lower-MC BUY could incorrectly
        # bypass the meaning of FIRST ALERT MC CUTOFF.
        self._cutoff_rejected_tokens: set[str] = set()
        # trending_tokens is an indexed live list. Keep the slot->token mapping
        # so a replacement update can retire the previous card without a second
        # cache or any frontend guesswork.
        self._trending_slots: dict[int, str] = {}

    @staticmethod
    def token_key(network_id, token_address: str) -> str:
        return f"{network_id}:{token_address.lower()}"

    @staticmethod
    def parse_datetime(value: str | None) -> datetime | None:
        if not value:
            return datetime.now(timezone.utc)
        if not isinstance(value, str):
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        else:
            parsed = parsed.astimezone(timezone.utc)
        if parsed > datetime.now(timezone.utc) + timedelta(seconds=MAX_EVENT_FUTURE_SKEW_SECONDS):
            return None
        return parsed

    def _load_settings(self) -> tuple[float, float | None]:
        cutoff = float(DEFAULT_FIRST_ALERT_MC_CUTOFF)
        inactive = DEFAULT_INACTIVE_TOKEN_HOURS
        try:
            data = json.loads(self._settings_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return cutoff, inactive
        if not isinstance(data, dict):
            return cutoff, inactive
        loaded_cutoff = self._finite_positive(data.get("firstAlertMcCutoff"))
        loaded_inactive = self._finite_positive(data.get("inactiveTokenHours"))
        if loaded_cutoff is not None:
            cutoff = loaded_cutoff
        if data.get("inactiveTokenHours") is None:
            inactive = None
        elif loaded_inactive is not None:
            inactive = loaded_inactive
        return cutoff, inactive

    def _settings_payload(self, *, cutoff: float, inactive: float | None) -> dict:
        return {
            "firstAlertMcCutoff": cutoff,
            "inactiveTokenHours": inactive,
        }

    @staticmethod
    def _event_identity(payload: dict) -> str | None:
        for field in ("tradeId", "id"):
            value = payload.get(field)
            if isinstance(value, (str, int)):
                cleaned = str(value).strip()
                if cleaned and len(cleaned) <= 256:
                    return f"{field}:{cleaned}"
        return None

    def _is_duplicate_event_locked(self, payload: dict) -> bool:
        identity = self._event_identity(payload)
        if identity is None:
            return False
        now = self._monotonic_clock()
        expires_before = now - self._event_dedup_ttl_seconds
        while self._seen_event_ids:
            _, seen_at = next(iter(self._seen_event_ids.items()))
            if seen_at > expires_before:
                break
            self._seen_event_ids.popitem(last=False)
        if identity in self._seen_event_ids:
            return True
        self._seen_event_ids[identity] = now
        while len(self._seen_event_ids) > self._event_dedup_max_entries:
            self._seen_event_ids.popitem(last=False)
        return False

    async def apply_fomo_payload(self, payload: dict) -> FomoApplyResult:
        event_type = payload.get("type")
        if event_type not in {"swap_buy", "swap_sell"}:
            return FomoApplyResult(False)

        token_address = payload.get("tokenAddress")
        network_id = payload.get("networkId")
        user_id = payload.get("userId")
        if (
            not isinstance(token_address, str)
            or not token_address.strip()
            or not isinstance(user_id, (str, int))
            or isinstance(user_id, bool)
            or str(user_id).strip() == ""
            or network_id is None
        ):
            logger.warning("Ignoring BUY/SELL with invalid token/user/network identifiers")
            return FomoApplyResult(False, malformed=True)

        key = self.token_key(network_id, token_address)
        now = self.parse_datetime(payload.get("createdAt"))
        if now is None:
            logger.warning("Ignoring BUY/SELL with invalid createdAt for %s", key)
            return FomoApplyResult(False, malformed=True)
        trade_mc = self._to_float(payload.get("marketCap"))
        trade_usd = self._to_float(payload.get("usdAmount"))
        if self._is_explicitly_non_finite(payload.get("marketCap")) or self._is_explicitly_non_finite(payload.get("usdAmount")):
            logger.warning("Ignoring BUY/SELL with non-finite numeric data for %s", key)
            return FomoApplyResult(False, malformed=True)
        trade_proxy = self._position_proxy(trade_usd, trade_mc)

        async with self._lock:
            if self._is_duplicate_event_locked(payload):
                return FomoApplyResult(False, duplicate=True)
            if key in self._forgotten_tokens or key in self._cutoff_rejected_tokens:
                return FomoApplyResult(False)

            token = self._tokens.get(key)

            if event_type == "swap_sell":
                if token is None:
                    return FomoApplyResult(False)

                buyer = token.buyers.get(user_id)
                if buyer is None:
                    return FomoApplyResult(False)

                token.last_activity_at = now
                self._append_trade_event(token, payload, "sell", now, trade_mc, trade_usd)
                if trade_mc is not None:
                    # Fomo is the freshest price evidence at the exact trade
                    # moment. Show it as MC NOW immediately. A provisional Dex
                    # pair is revalidated; a confirmed pair stays locked.
                    token.last_trade_mc = trade_mc
                    token.current_mc = trade_mc
                    token.last_mc_update = now
                    token.dex_pair_needs_revalidation = True

                # A SELL is only considered a complete exit when its reconstructed
                # token quantity closes the tracked position (within the dust
                # tolerance). If Fomo ever omits USD or MC, keep the trader active
                # rather than falsely declaring a full exit.
                if trade_proxy is None or buyer.gross_buy_proxy <= 0:
                    self._version += 1
                    return FomoApplyResult(True)

                buyer.gross_sell_proxy += trade_proxy
                remaining_fraction = buyer.position_left_fraction
                is_closed = (
                    remaining_fraction is not None
                    and remaining_fraction <= POSITION_DUST_FRACTION + 1e-9
                )

                if is_closed:
                    removed = token.buyers.pop(user_id)
                    token.sold_buyers[user_id] = SoldBuyerState(
                        user_id=removed.user_id,
                        handle=removed.handle,
                        display_name=removed.display_name,
                        bought_at=removed.bought_at,
                        mc_at_alert=removed.mc_at_alert,
                        usd_amount=removed.usd_amount,
                        sell_mc=trade_mc,
                        sell_usd_amount=trade_usd,
                        sold_at=now,
                        expires_at=now + timedelta(seconds=SOLD_COOLDOWN_SECONDS),
                    )

                self._version += 1
                return FomoApplyResult(True)

            # BUY. Admission is independent from TokenState existence because a
            # token may already exist as a TRENDING-only shared market record.
            if key not in self._admitted_tokens:
                first_signal_mc = trade_mc
                # FIRST ALERT MC CUTOFF is a strict admission gate. Never
                # admit an alert before Fomo has supplied a usable MC. A shared
                # TRENDING record must not bypass this rule.
                if first_signal_mc is None:
                    logger.warning(
                        "Ignoring first BUY without marketCap for %s; cutoff cannot be evaluated",
                        key,
                    )
                    return FomoApplyResult(False)
                if first_signal_mc > self._first_alert_mc_cutoff:
                    self._cutoff_rejected_tokens.add(key)
                    logger.info(
                        "FIRST ALERT cutoff rejected %s: mc=%s cutoff=%s",
                        key,
                        first_signal_mc,
                        self._first_alert_mc_cutoff,
                    )
                    return FomoApplyResult(False)
                self._admitted_tokens.add(key)

            if token is None:
                first_signal_mc = trade_mc
                # A previously admitted token may return after automatic
                # inactivity cleanup regardless of its new MC. The cutoff applies
                # to its first admission only, not to later activity.
                token = TokenState(
                    key=key,
                    token_address=token_address,
                    network_id=network_id,
                    ticker=payload.get("ticker") or "?",
                    token_image_url=payload.get("tokenImageUrl"),
                    first_signal_mc=first_signal_mc,
                    last_trade_mc=first_signal_mc,
                    current_mc=first_signal_mc,
                    last_mc_update=now if first_signal_mc is not None else None,
                    dex_pair_needs_revalidation=first_signal_mc is not None,
                    last_activity_at=now,
                )
                self._tokens[key] = token

            previous_count = token.alert_count
            if token.first_signal_mc is None and previous_count == 0:
                token.first_signal_mc = trade_mc
            if trade_mc is not None:
                # Never leave a just-arrived BUY showing an older Dex MC. Fomo
                # becomes MC NOW instantly. Dex then refreshes the confirmed
                # pair, or revalidates a still-provisional pair against this MC.
                token.last_trade_mc = trade_mc
                token.current_mc = trade_mc
                token.last_mc_update = now
                token.dex_pair_needs_revalidation = True

            # A new BUY after a completed exit starts a fresh active position and
            # removes the temporary SOLD row for that trader.
            token.sold_buyers.pop(user_id, None)

            token.ticker = payload.get("ticker") or token.ticker
            token.token_image_url = payload.get("tokenImageUrl") or token.token_image_url
            token.last_activity_at = now
            self._append_trade_event(token, payload, "buy", now, trade_mc, trade_usd)

            buyer = token.buyers.get(user_id)
            if buyer is None:
                buyer = BuyerState(
                    user_id=user_id,
                    handle=payload.get("userHandle") or payload.get("displayName") or "?",
                    display_name=payload.get("displayName") or payload.get("userHandle") or "?",
                    bought_at=now,
                    mc_at_alert=trade_mc,
                    usd_amount=trade_usd,
                )
                token.buyers[user_id] = buyer
            else:
                # One trader still counts once. Keep the row focused on the most
                # recent BUY while cumulative proxies preserve the full position.
                buyer.handle = payload.get("userHandle") or payload.get("displayName") or buyer.handle
                buyer.display_name = payload.get("displayName") or payload.get("userHandle") or buyer.display_name
                buyer.bought_at = now
                buyer.mc_at_alert = trade_mc
                buyer.usd_amount = trade_usd

            if trade_proxy is not None:
                buyer.gross_buy_proxy += trade_proxy
            if token.alert_count > previous_count and token.alert_count >= 2:
                token.new_until = now + timedelta(seconds=NEW_BADGE_SECONDS)

            self._version += 1
            return FomoApplyResult(True)

    async def cleanup(self) -> bool:
        """Prune live trade history, expire SOLD rows, and remove stale cards.

        Automatic inactivity cleanup uses the latest Fomo BUY/SELL timestamp.
        Unlike manual FORGET, it does not blacklist the token: a later Fomo
        trade can recreate a card without re-applying first-alert admission.
        """
        now = datetime.now(timezone.utc)
        changed = False

        async with self._lock:
            inactive_before = (
                now - timedelta(hours=self._inactive_token_hours)
                if self._inactive_token_hours is not None
                else None
            )
            event_before = now - timedelta(minutes=TRADE_EVENT_WINDOW_MINUTES)
            remove_keys: list[str] = []

            for key, token in self._tokens.items():
                kept_events = [
                    event for event in token.trade_events if event.occurred_at >= event_before
                ]
                if len(kept_events) != len(token.trade_events):
                    token.trade_events = kept_events
                    changed = True

                if (
                    inactive_before is not None
                    and (token.buyers or token.sold_buyers)
                    and token.last_activity_at < inactive_before
                ):
                    if token.is_trending:
                        token.buyers.clear()
                        token.sold_buyers.clear()
                        token.trade_events.clear()
                        changed = True
                    else:
                        remove_keys.append(key)
                    continue

                expired_ids = [
                    user_id
                    for user_id, sold in token.sold_buyers.items()
                    if sold.expires_at <= now
                ]

                for user_id in expired_ids:
                    del token.sold_buyers[user_id]
                    changed = True

                if not token.buyers and not token.sold_buyers and not token.is_trending:
                    remove_keys.append(key)

            for key in remove_keys:
                if self._tokens.pop(key, None) is not None:
                    changed = True

            if changed:
                self._version += 1

        return changed

    async def forget_token(self, key: str) -> bool:
        """Remove ALERTS state and ignore later trades until process restart.

        A token that is also TRENDING remains in the shared market registry;
        FORGET is an ALERTS action and must not silently remove another view.
        """
        async with self._lock:
            token = self._tokens.get(key)
            if token is None or (not token.buyers and not token.sold_buyers):
                return False
            self._forgotten_tokens.add(key)
            if token.is_trending:
                token.buyers.clear()
                token.sold_buyers.clear()
                token.trade_events.clear()
            else:
                self._tokens.pop(key, None)
            self._version += 1
            return True

    async def set_inactive_token_hours(self, hours: float | None) -> None:
        if hours is not None and self._finite_positive(hours) is None:
            raise ValueError("Inactive-token duration must be greater than zero, or empty to disable.")
        async with self._lock:
            next_inactive = float(hours) if hours is not None else None
            payload = self._settings_payload(
                cutoff=self._first_alert_mc_cutoff,
                inactive=next_inactive,
            )
            await asyncio.to_thread(atomic_write_json, self._settings_path, payload)
            self._inactive_token_hours = next_inactive
            self._version += 1

    async def get_inactive_token_hours(self) -> float | None:
        async with self._lock:
            return self._inactive_token_hours

    async def update_market_data(
        self,
        key: str,
        market_cap: float | None,
        volume_24h: float | None,
        oldest_pair_created_at: datetime | None,
        dex_pair_address: str | None,
        *,
        pair_revalidated: bool = False,
        pair_confirmed: bool | None = None,
    ) -> bool:
        # DexScreener market data is applied only after market_data.py has
        # selected a chain-correct pair. The chosen pair is persisted so later
        # refreshes follow that same market even if its MC moves far from entry.
        if market_cap is None and volume_24h is None and oldest_pair_created_at is None:
            return False

        async with self._lock:
            token = self._tokens.get(key)
            if token is None:
                return False

            if market_cap is not None:
                token.current_mc = market_cap
                # This timestamp labels MC freshness in the UI. AGE/volume-only
                # enrichment must not make an older Fomo MC look freshly updated.
                token.last_mc_update = datetime.now(timezone.utc)
            if volume_24h is not None:
                token.volume_24h = volume_24h
            if oldest_pair_created_at is not None:
                token.oldest_pair_created_at = oldest_pair_created_at
            if dex_pair_address:
                token.dex_pair_address = dex_pair_address
            if pair_confirmed is not None:
                token.dex_pair_confirmed = pair_confirmed
            if pair_revalidated:
                token.dex_pair_needs_revalidation = False

            self._version += 1
            return True

    async def mark_market_enrichment_attempted(self, key: str) -> bool:
        """Mark a successful Dex lookup for one shared token.

        TRENDING-only cards use Dex for one-time enrichment (primarily AGE),
        while ALERTS retain their normal event/periodic refresh lifecycle.
        """
        async with self._lock:
            token = self._tokens.get(key)
            if token is None or token.dex_enrichment_attempted:
                return False
            token.dex_enrichment_attempted = True
            return True

    def _claim_aux_market_revalidation(self, token: TokenState) -> bool:
        """Throttle non-trade evidence that asks Dex to re-check a pair."""
        if token.dex_pair_confirmed or not (token.buyers or token.sold_buyers):
            return False
        now = self._monotonic_clock()
        previous = token.last_aux_market_refresh_requested_at
        if (
            previous is not None
            and now - previous < FOMO_AUX_MARKET_REVALIDATION_COOLDOWN_SECONDS
        ):
            return False
        token.last_aux_market_refresh_requested_at = now
        token.dex_pair_needs_revalidation = True
        return True

    async def apply_trending_payload(self, payload: dict) -> tuple[bool, str | None, bool]:
        """Apply one indexed trending_tokens update to the shared token state.

        Returns (changed, token_key, market_refresh_needed). Replacing an index retires only the old
        TRENDING membership; an ALERTS position for that token remains intact.
        """
        if payload.get("kind") != "update" or not isinstance(payload.get("update"), dict):
            return False, None, False
        update = payload["update"]
        token_data = update.get("token")
        index = payload.get("index")
        if not isinstance(token_data, dict) or not isinstance(index, int):
            return False, None, False
        address = token_data.get("address")
        network_id = token_data.get("networkId")
        if not address or network_id is None:
            return False, None, False
        if self._is_explicitly_non_finite(update.get("marketCap")) or self._is_explicitly_non_finite(update.get("priceUSD")):
            logger.warning("Ignoring trending update with non-finite market data")
            return False, None, False
        key = self.token_key(network_id, address)
        now = datetime.now(timezone.utc)

        async with self._lock:
            # Fomo can re-rank a token into another index before the old slot's
            # replacement update arrives. A token owns at most one current slot;
            # removing stale slot aliases prevents that later update from
            # accidentally retiring the token from its new rank.
            for slot, slot_key in list(self._trending_slots.items()):
                if slot_key == key and slot != index:
                    del self._trending_slots[slot]

            previous_key = self._trending_slots.get(index)
            if previous_key and previous_key != key:
                previous = self._tokens.get(previous_key)
                if previous:
                    previous.is_trending = False
                    previous.trending_index = None
                    if not previous.buyers and not previous.sold_buyers:
                        self._tokens.pop(previous_key, None)

            item = self._tokens.get(key)
            if item is None:
                item = TokenState(
                    key=key,
                    token_address=str(address),
                    network_id=network_id,
                    ticker=token_data.get("symbol") or "?",
                    token_image_url=((token_data.get("info") or {}).get("imageThumbUrl")),
                    last_activity_at=now,
                )
                self._tokens[key] = item

            info = token_data.get("info") if isinstance(token_data.get("info"), dict) else {}
            item.ticker = token_data.get("symbol") or item.ticker
            item.token_name = token_data.get("name") or item.token_name
            item.token_image_url = info.get("imageThumbUrl") or item.token_image_url
            item.fomo_trending_mc = self._to_float(update.get("marketCap"))
            item.fomo_trending_price = self._to_float(update.get("priceUSD"))
            try:
                item.holders = int(update["holders"]) if update.get("holders") is not None else item.holders
            except (TypeError, ValueError):
                pass
            item.trending_index = index
            item.trending_updated_at = now
            item.is_trending = True
            self._trending_slots[index] = key

            if item.buyers or item.sold_buyers:
                # For ALERTS tokens, TRENDING is useful extra Fomo evidence but
                # it must not trigger Dex on every ranking tick.
                market_refresh_needed = self._claim_aux_market_revalidation(item)
            else:
                # TRENDING already carries the live MC/price used by its card.
                # Dex is requested once for shared enrichment such as AGE.
                market_refresh_needed = not item.dex_enrichment_attempted
            self._version += 1
            return True, key, market_refresh_needed

    async def apply_price_payload(self, topic_id: str, payload: dict) -> tuple[bool, str | None, bool]:
        """Store official Fomo price evidence for a subscribed held ALERTS token.

        General market tracking is handled by DexScreener. TRENDING-only and
        unheld ALERTS tokens never request this per-token Fomo stream.
        """
        if not isinstance(payload, dict):
            return False, None, False
        try:
            address, network_id = topic_id.rsplit(":", 1)
        except ValueError:
            return False, None, False
        key = self.token_key(network_id, address)
        price = self._to_float(payload.get("priceUsd"))
        if price is None:
            return False, None, False
        async with self._lock:
            token = self._tokens.get(key)
            if token is None:
                return False, None, False
            token.fomo_price = price
            needs_market_refresh = self._claim_aux_market_revalidation(token)
            self._version += 1
            return True, key, needs_market_refresh

    async def held_alert_price_topics(self, held_token_keys: set[str]) -> set[str]:
        """Return `prices` topics only for held tokens that are still in ALERTS.

        General ALERTS/TRENDING market refreshes use DexScreener. The optional
        Fomo per-token stream is deliberately restricted to the intersection of
        the active account's positive BALANCE positions and live ALERTS state.
        """
        async with self._lock:
            return {
                f"{token.token_address}:{token.network_id}"
                for token in self._tokens.values()
                if token.key in held_token_keys and (token.buyers or token.sold_buyers)
            }

    async def clear_ineligible_fomo_prices(self, eligible_topics: set[str]) -> int:
        """Drop cached `prices` evidence as soon as a token is no longer eligible."""
        cleared = 0
        async with self._lock:
            for token in self._tokens.values():
                topic_id = f"{token.token_address}:{token.network_id}"
                if topic_id not in eligible_topics and token.fomo_price is not None:
                    token.fomo_price = None
                    cleared += 1
            if cleared:
                self._version += 1
        return cleared

    @staticmethod
    def _market_reference_mc(token: TokenState, force_revalidate: bool) -> float | None:
        """Choose the freshest useful Fomo MC evidence for Dex discovery."""
        trade_time = token.last_activity_at if token.last_trade_mc is not None else None
        trend_time = token.trending_updated_at if token.fomo_trending_mc is not None else None
        if force_revalidate or token.dex_pair_needs_revalidation:
            if trend_time and (trade_time is None or trend_time >= trade_time):
                return token.fomo_trending_mc
            if token.last_trade_mc is not None:
                return token.last_trade_mc
        return token.fomo_trending_mc if token.fomo_trending_mc is not None else token.first_signal_mc

    async def set_first_alert_mc_cutoff(self, value: float) -> None:
        validated = self._finite_positive(value)
        if validated is None:
            raise ValueError("Cutoff must be greater than zero.")
        async with self._lock:
            payload = self._settings_payload(
                cutoff=validated,
                inactive=self._inactive_token_hours,
            )
            await asyncio.to_thread(atomic_write_json, self._settings_path, payload)
            self._first_alert_mc_cutoff = validated
            self._version += 1

    async def get_first_alert_mc_cutoff(self) -> float:
        async with self._lock:
            return self._first_alert_mc_cutoff

    async def token_refs(
        self,
        keys: set[str] | None = None,
        *,
        revalidate_pair: bool = False,
        include_trending_only: bool = True,
    ) -> list[tuple[str, str, int | str | None, float | None, float | None, str | None, bool, bool]]:
        """Return one deduplicated market-data reference per shared token.

        ALERTS and TRENDING feed the same TokenState, so a token visible in both
        views produces one DexScreener reference. `include_trending_only=False`
        is used by periodic refreshes: TRENDING-only cards use Fomo for live MC
        and Dex only for their one-time enrichment request.

        A fresh Fomo trade carries new MC evidence. Provisional pairs are
        revalidated against it so later alerts can correct an initially wrong
        market. Once successive Fomo-guided selections confirm a pair,
        market_data.py keeps that exact pair locked until Dex stops returning it.
        """
        async with self._lock:
            return [
                (
                    token.key,
                    token.token_address,
                    token.network_id,
                    self._market_reference_mc(token, revalidate_pair),
                    token.fomo_price if token.fomo_price is not None else token.fomo_trending_price,
                    token.dex_pair_address,
                    token.dex_pair_confirmed,
                    revalidate_pair or token.dex_pair_needs_revalidation,
                )
                for token in self._tokens.values()
                if (
                    token.buyers
                    or token.sold_buyers
                    or (include_trending_only and token.is_trending)
                )
                and (keys is None or token.key in keys)
            ]

    async def snapshot(self) -> dict:
        async with self._lock:
            now = datetime.now(timezone.utc)
            tokens = []
            for token in self._tokens.values():
                if not (token.buyers or token.sold_buyers):
                    continue
                buyers = sorted(
                    token.buyers.values(),
                    key=lambda buyer: buyer.bought_at,
                )
                tokens.append(
                    {
                        "key": token.key,
                        "tokenAddress": token.token_address,
                        "networkId": token.network_id,
                        "ticker": token.ticker,
                        "tokenImageUrl": token.token_image_url,
                        "alertCount": token.alert_count,
                        "firstSignalMc": token.first_signal_mc,
                        "lastTradeMc": token.last_trade_mc,
                        "currentMc": token.current_mc,
                        "volume24h": token.volume_24h,
                        "tokenCreatedAt": (
                            token.oldest_pair_created_at.isoformat()
                            if token.oldest_pair_created_at
                            else None
                        ),
                        "lastMcUpdate": (
                            token.last_mc_update.isoformat()
                            if token.last_mc_update
                            else None
                        ),
                        "lastActivityAt": token.last_activity_at.isoformat(),
                        "isNew": bool(token.new_until and token.new_until > now),
                        "newUntil": token.new_until.isoformat() if token.new_until else None,
                        "tradeEvents": [
                            {
                                "type": event.event_type,
                                "userId": event.user_id,
                                "handle": event.handle,
                                "displayName": event.display_name,
                                "occurredAt": event.occurred_at.isoformat(),
                                "marketCap": event.market_cap,
                                "usdAmount": event.usd_amount,
                            }
                            for event in token.trade_events
                            if event.occurred_at
                            >= now - timedelta(minutes=TRADE_EVENT_WINDOW_MINUTES)
                        ],
                        "buyers": [
                            {
                                "userId": buyer.user_id,
                                "handle": buyer.handle,
                                "displayName": buyer.display_name,
                                "boughtAt": buyer.bought_at.isoformat(),
                                "mcAtAlert": buyer.mc_at_alert,
                                "usdAmount": buyer.usd_amount,
                                "positionLeftPct": (
                                    buyer.position_left_fraction * 100
                                    if buyer.position_left_fraction is not None
                                    else None
                                ),
                                "isPartial": buyer.is_partial,
                            }
                            for buyer in buyers
                        ],
                        "soldBuyers": [
                            {
                                "userId": sold.user_id,
                                "handle": sold.handle,
                                "displayName": sold.display_name,
                                "boughtAt": sold.bought_at.isoformat(),
                                "mcAtAlert": sold.mc_at_alert,
                                "usdAmount": sold.usd_amount,
                                "sellMc": sold.sell_mc,
                                "sellUsdAmount": sold.sell_usd_amount,
                                "soldAt": sold.sold_at.isoformat(),
                                "expiresAt": sold.expires_at.isoformat(),
                            }
                            for sold in sorted(
                                token.sold_buyers.values(),
                                key=lambda item: item.sold_at,
                                reverse=True,
                            )
                            if sold.expires_at > now
                        ],
                    }
                )

            tokens.sort(
                key=lambda item: (
                    item["alertCount"],
                    item["lastActivityAt"],
                ),
                reverse=True,
            )

            trending = [
                {
                    "key": token.key,
                    "tokenAddress": token.token_address,
                    "networkId": token.network_id,
                    "ticker": token.ticker,
                    "name": token.token_name,
                    "tokenImageUrl": token.token_image_url,
                    # TRENDING is ranked by Fomo's native MC. Dex remains the
                    # shared enrichment source for token age/pair validation.
                    "marketCap": token.fomo_trending_mc,
                    "holders": token.holders,
                    "index": token.trending_index,
                    "tokenCreatedAt": (
                        token.oldest_pair_created_at.isoformat()
                        if token.oldest_pair_created_at else None
                    ),
                    "updatedAt": token.trending_updated_at.isoformat()
                    if token.trending_updated_at else None,
                }
                for token in self._tokens.values()
                if token.is_trending
            ]
            trending.sort(key=lambda item: item["index"] if item["index"] is not None else 10**9)

            return {
                "version": self._version,
                "generatedAt": now.isoformat(),
                "firstAlertMcCutoff": self._first_alert_mc_cutoff,
                "inactiveTokenHours": self._inactive_token_hours,
                "tokens": tokens,
                "trending": trending,
            }

    @staticmethod
    def _append_trade_event(
        token: TokenState,
        payload: dict,
        event_type: str,
        occurred_at: datetime,
        market_cap: float | None,
        usd_amount: float | None,
    ) -> None:
        """Append one accepted Fomo fill and keep only the live 60-minute window."""
        token.trade_events.append(
            TradeEventState(
                event_type=event_type,
                user_id=str(payload.get("userId") or ""),
                handle=payload.get("userHandle") or payload.get("displayName") or "?",
                display_name=payload.get("displayName") or payload.get("userHandle") or "?",
                occurred_at=occurred_at,
                market_cap=market_cap,
                usd_amount=usd_amount,
            )
        )
        cutoff = occurred_at - timedelta(minutes=TRADE_EVENT_WINDOW_MINUTES)
        token.trade_events = [
            event for event in token.trade_events if event.occurred_at >= cutoff
        ]

    @staticmethod
    def _position_proxy(usd_amount: float | None, market_cap: float | None) -> float | None:
        """Return a supply-independent proxy for token quantity.

        For a fixed token supply, USD / market cap is proportional to raw token
        quantity. The unknown supply factor cancels when BUY and SELL proxies are
        compared for the same token.
        """
        if usd_amount is None or market_cap is None or usd_amount <= 0 or market_cap <= 0:
            return None
        return usd_amount / market_cap

    @staticmethod
    def _to_float(value):
        if value is None:
            return None
        try:
            number = float(value)
            return number if math.isfinite(number) else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _finite_positive(value) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) and number > 0 else None

    @staticmethod
    def _is_explicitly_non_finite(value: object) -> bool:
        if value is None or value == "":
            return False
        try:
            return not math.isfinite(float(value))
        except (TypeError, ValueError):
            return False


store = DashboardStore()
