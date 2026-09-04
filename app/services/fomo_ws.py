import asyncio
import json
import logging

import websockets

from ..config import (
    AUTH_RETRY_SECONDS,
    FOMO_PRICE_SUBSCRIBE_BATCH_SIZE,
    FOMO_TRENDING_TOPIC_ID,
    FOMO_WS_URL,
)
from ..store import DashboardStore
from .auth import AuthWaiting, auth_manager
from .topic import topic_manager
from .following import following_manager
from .ws_event_log import ws_event_log
from .market_data import MarketRefreshScheduler
from .runtime_health import runtime_health


logger = logging.getLogger("fomo.ws")


LOG_HANDLE_MAX_CHARS = 48
LOG_TICKER_MAX_CHARS = 64


class _PriceSubscriptionState:
    """Track optional per-token `prices` subscriptions for one WS connection.

    Fomo does not document an unsubscribe contract here, and the server enforces
    an active-topic ceiling. Price evidence is optional, so a capacity rejection
    disables further price subscriptions on this connection without disrupting
    the mandatory trading_activity/trending_tokens feeds.
    """

    def __init__(self) -> None:
        self.requested: set[str] = set()
        self.capacity_reached = False

    def next_topics(self, desired: set[str]) -> list[str]:
        if self.capacity_reached:
            return []
        remaining = sorted(desired - self.requested)
        return remaining[:FOMO_PRICE_SUBSCRIBE_BATCH_SIZE]

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
                "Fomo prices capacity reached after %s requested topics; "
                "keeping trading_activity/trending_tokens live and stopping "
                "new prices subscriptions for this connection",
                len(self.requested),
            )
        else:
            logger.warning(
                "Fomo rejected optional prices subscription %s: %s",
                message.get("topicId") or "-",
                text or message,
            )
        return True


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
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=AUTH_RETRY_SECONDS,
                )
            except asyncio.TimeoutError:
                pass
            continue

        try:
            logger.info("Connecting to Fomo WebSocket")

            async with websockets.connect(
                FOMO_WS_URL,
                ping_interval=20,
                ping_timeout=20,
                close_timeout=5,
            ) as ws:
                await runtime_health.ws_connected()
                reconnect_backoff = 2
                price_subscriptions = _PriceSubscriptionState()

                async def sync_price_subscriptions() -> None:
                    # `prices` is optional pair evidence for active ALERTS, not a
                    # second live feed for every TRENDING card. Subscriptions are
                    # deduplicated and advanced in small batches because the
                    # upstream active-topic ceiling and unsubscribe semantics are
                    # not documented.
                    desired = await store.relevant_price_topics()
                    for price_topic in price_subscriptions.next_topics(desired):
                        await ws.send(json.dumps({
                            "type": "subscribe",
                            "topicType": "prices",
                            "topicId": price_topic,
                        }))
                        price_subscriptions.mark_requested(price_topic)

                while not stop_event.is_set():
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=30)
                    except asyncio.TimeoutError:
                        # Quiet market: keep the connection; ping/pong
                        # (20/20) already guarantees liveness. The timeout
                        # only exists to re-check stop_event for shutdown.
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
                        await ws.send(
                            json.dumps(
                                {
                                    "type": "challengeResponse",
                                    "jwt": jwt,
                                }
                            )
                        )
                        logger.info("Fomo challenge answered")

                        topic_id = topic_manager.resolve()
                        if not topic_id:
                            logger.info(
                                "TOPIC WAITING: no verified topicId yet — refresh Fomo "
                                "in Chrome once so the bridge sees the trading_activity subscription"
                            )
                            break

                        await ws.send(json.dumps({
                            "type": "subscribe",
                            "topicType": "trading_activity",
                            "topicId": topic_id,
                        }))
                        await ws.send(json.dumps({
                            "type": "subscribe",
                            "topicType": "trending_tokens",
                            "topicId": FOMO_TRENDING_TOPIC_ID,
                        }))
                        await sync_price_subscriptions()
                        continue

                    if message_type == "subscribed":
                        topic_type = message.get("topicType")
                        if topic_type in {"trading_activity", "trending_tokens"}:
                            logger.info("Subscribed to Fomo %s", topic_type)
                        elif topic_type == "prices":
                            # Acknowledgements let a large existing ALERTS board
                            # progress without sending a subscription burst.
                            await sync_price_subscriptions()
                        continue

                    if message_type == "error":
                        code = message.get("code")
                        if code == "AUTH_REQUIRED":
                            await runtime_health.ws_disconnected("Fomo authentication required")
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

                    if message_type == "data" and message.get("topicType") == "trending_tokens":
                        payload = message.get("payload")
                        if isinstance(payload, dict):
                            try:
                                changed, key, needs_market_refresh = await store.apply_trending_payload(payload)
                                if changed and key:
                                    if needs_market_refresh:
                                        # Repeated rank ticks during the same Dex
                                        # lookup do not need a second enrichment
                                        # pass. Fresh evidence remains in the
                                        # shared TokenState for later refreshes.
                                        market_refresh_scheduler.schedule(
                                            key,
                                            reschedule_if_in_flight=False,
                                        )
                                    await sync_price_subscriptions()
                            except Exception as exc:
                                logger.warning("Ignoring malformed trending payload: %s", exc)
                        continue

                    if message_type == "data" and message.get("topicType") == "prices":
                        topic_id = message.get("topicId")
                        payload = message.get("payload")
                        if isinstance(topic_id, str) and isinstance(payload, dict):
                            try:
                                changed, key, needs_market_refresh = await store.apply_price_payload(topic_id, payload)
                                if changed and key and needs_market_refresh:
                                    market_refresh_scheduler.schedule(key)
                            except Exception as exc:
                                logger.warning("Ignoring malformed price payload: %s", exc)
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
                                following, favorite = await following_manager.match_status(payload.get("userId"))
                                await ws_event_log.append(
                                    payload,
                                    accepted=bool(result),
                                    following=following,
                                    favorite=favorite,
                                )
                            except Exception as exc:
                                logger.warning("Ignoring malformed trading_activity payload: %s", exc)
                                continue
                            if result:
                                # BUY and SELL are the moments when MC NOW matters
                                # most. Queue an immediate targeted DexScreener
                                # refresh instead of waiting for the periodic pass.
                                token_address = payload.get("tokenAddress")
                                user_id = payload.get("userId")
                                if token_address and user_id:
                                    key = store.token_key(
                                        payload.get("networkId"),
                                        token_address,
                                    )
                                    market_refresh_scheduler.schedule(key)
                                    await sync_price_subscriptions()
                                # Keep the event and its full payload untouched. Only
                                # bound untrusted display strings in the console so a
                                # pathological ticker cannot make the runtime log unusable.
                                logger.info(
                                    "%s %s %s token=%s amount=%s mc=%s",
                                    payload.get("type"),
                                    _bounded_log_text(
                                        payload.get("userHandle"), LOG_HANDLE_MAX_CHARS
                                    ),
                                    _bounded_log_text(
                                        payload.get("ticker"), LOG_TICKER_MAX_CHARS
                                    ),
                                    _short_token_address(payload.get("tokenAddress")),
                                    payload.get("usdAmount"),
                                    payload.get("marketCap"),
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

                # The bridge heals jwt.json on the next browser push; just wait
                # before the next top-level attempt rather than reconnect-looping.
                try:
                    await asyncio.wait_for(
                        stop_event.wait(),
                        timeout=AUTH_RETRY_SECONDS,
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

        try:
            await asyncio.wait_for(
                stop_event.wait(),
                timeout=reconnect_backoff,
            )
        except asyncio.TimeoutError:
            pass
        reconnect_backoff = min(reconnect_backoff * 2, 30)
