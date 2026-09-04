import asyncio
import json
import logging
import time

import websockets

from ..config import (
    AUTH_RETRY_SECONDS,
    FOMO_PRICE_SUBSCRIBE_INTERVAL_SECONDS,
    FOMO_TRENDING_TOPIC_ID,
    FOMO_WS_URL,
)
from ..store import DashboardStore
from .auth import AuthWaiting, auth_manager
from .balances import balance_manager
from .following import following_manager
from .market_data import MarketRefreshScheduler
from .runtime_health import runtime_health
from .topic import topic_manager
from .watchlist import watchlist_manager
from .ws_event_log import ws_event_log


logger = logging.getLogger("fomo.ws")


LOG_HANDLE_MAX_CHARS = 48
LOG_TICKER_MAX_CHARS = 64


class _PriceSubscriptionState:
    """Track optional held-ALERT `prices` subscriptions for one WS connection.

    The upstream unsubscribe contract is not documented, so topics already sent
    are deduplicated for the lifetime of the socket. Eligibility is re-evaluated
    continuously and stale topic payloads are ignored. A capacity rejection
    disables new optional subscriptions without touching the mandatory feeds.
    """

    def __init__(self) -> None:
        self.requested: set[str] = set()
        self.capacity_reached = False

    def next_topic(self, desired: set[str]) -> str | None:
        if self.capacity_reached:
            return None
        remaining = sorted(desired - self.requested)
        return remaining[0] if remaining else None

    def mark_requested(self, topic_id: str) -> None:
        self.requested.add(topic_id)

    def handle_error(self, message: dict) -> bool:
        """Return True when an optional `prices` rejection was consumed."""
        if message.get("topicType") != "prices" or message.get("code") != "SUBSCRIBE_REJECTED":
            return False

        text = str(message.get("message") or "")
        if "too many active topics" in text.lower():
            self.capacity_reached = True
            logger.warning(
                "Fomo prices capacity reached after %s requested held-ALERT topics; "
                "keeping trading_activity/trending_tokens live and stopping new "
                "prices subscriptions for this connection",
                len(self.requested),
            )
        else:
            logger.warning(
                "Fomo rejected optional prices subscription %s: %s",
                message.get("topicId") or "-",
                text or message,
            )
        return True


async def _held_alert_price_topics(store: DashboardStore, account_user_id: str) -> set[str]:
    """Resolve the exact BALANCE ∩ visible-ALERTS set eligible for Fomo `prices`."""
    held_keys = await balance_manager.active_token_keys(account_user_id)
    watchlisted_keys = await watchlist_manager.keys()
    desired = await store.held_alert_price_topics(held_keys - watchlisted_keys)
    await store.clear_ineligible_fomo_prices(desired)
    return desired


async def _run_price_subscription_pump(
    ws,
    store: DashboardStore,
    account_user_id: str,
    state: _PriceSubscriptionState,
    stop_event: asyncio.Event,
) -> None:
    """Add eligible price topics at a fixed, non-ACK-driven rate.

    General token pricing belongs to DexScreener. This pump exists only for
    currently held tokens that still have an ALERTS presence.
    """
    while not stop_event.is_set():
        desired = await _held_alert_price_topics(store, account_user_id)
        topic_id = state.next_topic(desired)
        if topic_id is not None:
            await ws.send(
                json.dumps(
                    {
                        "type": "subscribe",
                        "topicType": "prices",
                        "topicId": topic_id,
                    }
                )
            )
            state.mark_requested(topic_id)

        try:
            await asyncio.wait_for(
                stop_event.wait(),
                timeout=FOMO_PRICE_SUBSCRIBE_INTERVAL_SECONDS,
            )
        except asyncio.TimeoutError:
            pass


def _bounded_log_text(value: object, max_chars: int) -> str:
    """Bound untrusted display text for console logs without mutating payload data."""
    text = "" if value is None else str(value)
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}…[truncated]"


def _short_token_address(value: object) -> str:
    """Compact the contract for logs; processing still keeps the full address."""
    text = "" if value is None else str(value)
    if len(text) <= 18:
        return text or "-"
    return f"{text[:10]}…{text[-6:]}"


async def run_fomo_listener(
    store: DashboardStore,
    stop_event: asyncio.Event,
    market_refresh_scheduler: MarketRefreshScheduler,
) -> None:
    reconnect_backoff = 2

    while not stop_event.is_set():
        try:
            jwt = await auth_manager.get_valid_jwt()
        except asyncio.CancelledError:
            raise
        except AuthWaiting as exc:
            logger.info("AUTH WAITING FOR FOMO: %s", exc)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=AUTH_RETRY_SECONDS)
            except asyncio.TimeoutError:
                pass
            continue
        except Exception as exc:
            logger.error("Fomo auth unavailable: %s", exc)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=AUTH_RETRY_SECONDS)
            except asyncio.TimeoutError:
                pass
            continue

        connection_started: float | None = None
        try:
            logger.info("Connecting to Fomo WebSocket")

            async with websockets.connect(
                FOMO_WS_URL,
                ping_interval=20,
                ping_timeout=20,
                close_timeout=5,
            ) as ws:
                await runtime_health.ws_connected()
                connection_started = time.monotonic()
                price_subscriptions = _PriceSubscriptionState()
                mandatory_subscriptions: set[str] = set()
                price_pump_task: asyncio.Task | None = None
                account_user_id = topic_manager.resolve() or ""

                try:
                    while not stop_event.is_set():
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=30)
                        except asyncio.TimeoutError:
                            # Ping/pong provides liveness. This timeout only lets
                            # the loop observe stop_event during a quiet market.
                            continue

                        try:
                            message = json.loads(raw)
                        except (TypeError, json.JSONDecodeError) as exc:
                            logger.warning("Ignoring malformed Fomo WebSocket JSON: %s", exc)
                            continue
                        if not isinstance(message, dict):
                            logger.warning("Ignoring non-object Fomo WebSocket message")
                            continue

                        await runtime_health.ws_message()
                        message_type = message.get("type")

                        if message_type == "challenge":
                            await ws.send(json.dumps({"type": "challengeResponse", "jwt": jwt}))
                            logger.info("Fomo challenge answered")

                            account_user_id = topic_manager.resolve() or ""
                            if not account_user_id:
                                logger.info(
                                    "TOPIC WAITING: no verified topicId yet — refresh Fomo "
                                    "in Chrome once so the bridge sees the trading_activity subscription"
                                )
                                break

                            await ws.send(
                                json.dumps(
                                    {
                                        "type": "subscribe",
                                        "topicType": "trading_activity",
                                        "topicId": account_user_id,
                                    }
                                )
                            )
                            await ws.send(
                                json.dumps(
                                    {
                                        "type": "subscribe",
                                        "topicType": "trending_tokens",
                                        "topicId": FOMO_TRENDING_TOPIC_ID,
                                    }
                                )
                            )
                            continue

                        if message_type == "subscribed":
                            topic_type = message.get("topicType")
                            if topic_type in {"trading_activity", "trending_tokens"}:
                                mandatory_subscriptions.add(topic_type)
                                logger.info("Subscribed to Fomo %s", topic_type)
                                if (
                                    mandatory_subscriptions
                                    == {"trading_activity", "trending_tokens"}
                                    and price_pump_task is None
                                ):
                                    # Optional price subscriptions start only after
                                    # both mandatory feeds are confirmed alive.
                                    price_pump_task = asyncio.create_task(
                                        _run_price_subscription_pump(
                                            ws,
                                            store,
                                            account_user_id,
                                            price_subscriptions,
                                            stop_event,
                                        )
                                    )
                            continue

                        if message_type == "error":
                            code = message.get("code")
                            if code == "AUTH_REQUIRED":
                                await runtime_health.ws_disconnected(
                                    "Fomo authentication required"
                                )
                                logger.warning(
                                    "Fomo rejected auth; waiting for a fresh JWT from "
                                    "the browser bridge"
                                )
                                try:
                                    await asyncio.wait_for(
                                        stop_event.wait(),
                                        timeout=AUTH_RETRY_SECONDS,
                                    )
                                except asyncio.TimeoutError:
                                    pass
                                break
                            if price_subscriptions.handle_error(message):
                                continue
                            raise RuntimeError(f"Fomo error: {message}")

                        if (
                            message_type == "data"
                            and message.get("topicType") == "trending_tokens"
                        ):
                            payload = message.get("payload")
                            if isinstance(payload, dict):
                                try:
                                    changed, key, needs_market_refresh = (
                                        await store.apply_trending_payload(payload)
                                    )
                                    if changed and key and needs_market_refresh:
                                        # Dex enrichment is shared with ALERTS;
                                        # repeated rank ticks do not queue duplicates.
                                        market_refresh_scheduler.schedule(
                                            key,
                                            reschedule_if_in_flight=False,
                                        )
                                except Exception as exc:
                                    logger.warning(
                                        "Ignoring malformed trending payload: %s", exc
                                    )
                            continue

                        if message_type == "data" and message.get("topicType") == "prices":
                            topic_id = message.get("topicId")
                            payload = message.get("payload")
                            if isinstance(topic_id, str) and isinstance(payload, dict):
                                try:
                                    # Fomo's unsubscribe shape is not validated.
                                    # If eligibility disappeared after subscription,
                                    # ignore the stale payload instead of using it.
                                    desired = await _held_alert_price_topics(
                                        store, account_user_id
                                    )
                                    if topic_id not in desired:
                                        continue
                                    changed, key, needs_market_refresh = (
                                        await store.apply_price_payload(topic_id, payload)
                                    )
                                    if changed and key and needs_market_refresh:
                                        market_refresh_scheduler.schedule(key)
                                except Exception as exc:
                                    logger.warning(
                                        "Ignoring malformed price payload: %s", exc
                                    )
                            continue

                        if (
                            message_type == "data"
                            and message.get("topicType") == "trading_activity"
                        ):
                            payload = message.get("payload")
                            if isinstance(payload, dict):
                                try:
                                    result = await store.apply_fomo_payload(payload)
                                    if result.duplicate or result.malformed:
                                        continue
                                    following, favorite = await following_manager.match_status(
                                        payload.get("userId")
                                    )
                                    await ws_event_log.append(
                                        payload,
                                        accepted=bool(result),
                                        following=following,
                                        favorite=favorite,
                                    )
                                except Exception as exc:
                                    logger.warning(
                                        "Ignoring malformed trading_activity payload: %s",
                                        exc,
                                    )
                                    continue

                                if result:
                                    # BUY/SELL events request immediate DexScreener
                                    # refresh. Optional Fomo `prices` is not the
                                    # general market-data path anymore.
                                    token_address = payload.get("tokenAddress")
                                    user_id = payload.get("userId")
                                    if token_address and user_id:
                                        key = store.token_key(
                                            payload.get("networkId"), token_address
                                        )
                                        market_refresh_scheduler.schedule(key)

                                    # Keep the payload untouched. Only bound
                                    # display strings in the console log.
                                    logger.info(
                                        "%s %s %s token=%s amount=%s mc=%s",
                                        payload.get("type"),
                                        _bounded_log_text(
                                            payload.get("userHandle"),
                                            LOG_HANDLE_MAX_CHARS,
                                        ),
                                        _bounded_log_text(
                                            payload.get("ticker"),
                                            LOG_TICKER_MAX_CHARS,
                                        ),
                                        _short_token_address(
                                            payload.get("tokenAddress")
                                        ),
                                        payload.get("usdAmount"),
                                        payload.get("marketCap"),
                                    )
                finally:
                    if price_pump_task is not None:
                        price_pump_task.cancel()
                        await asyncio.gather(
                            price_pump_task, return_exceptions=True
                        )

                await runtime_health.ws_disconnected("connection closed")

        except asyncio.CancelledError:
            await runtime_health.ws_disconnected("cancelled")
            raise
        except websockets.exceptions.ConnectionClosedError as exc:
            reason = (exc.reason or "").lower()

            if exc.code == 1008 and "invalid jwt" in reason:
                await runtime_health.ws_disconnected(exc)
                logger.warning(
                    "Fomo reported invalid jwt; waiting for a fresh JWT from the "
                    "browser bridge"
                )
                try:
                    await asyncio.wait_for(
                        stop_event.wait(), timeout=AUTH_RETRY_SECONDS
                    )
                except asyncio.TimeoutError:
                    pass
                reconnect_backoff = 2
                continue

            await runtime_health.ws_disconnected(exc)
            logger.warning("Fomo listener disconnected: %s", exc)

        except Exception as exc:
            await runtime_health.ws_disconnected(exc)
            logger.warning("Fomo listener disconnected: %s", exc)

        # Only a connection that stayed healthy for at least a minute resets
        # backoff. Rapid 1013/other failures now progress 2→4→8→16→30 seconds.
        if connection_started is not None and time.monotonic() - connection_started >= 60:
            reconnect_backoff = 2

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=reconnect_backoff)
        except asyncio.TimeoutError:
            pass
        reconnect_backoff = min(reconnect_backoff * 2, 30)
