import asyncio
import logging
import math
from collections import defaultdict, deque
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import aiohttp

from ..config import (
    DEX_BATCH_SIZE,
    DEX_HARD_REQUESTS_PER_MINUTE,
    DEX_MIN_REQUEST_INTERVAL_SECONDS,
    DEX_MIN_REFRESH_SECONDS,
    DEX_PAIR_LIQUIDITY_WEIGHT,
    DEX_PAIR_VOLUME_WEIGHT,
    DEX_RATE_LIMIT_BACKOFF_INITIAL_SECONDS,
    DEX_RATE_LIMIT_BACKOFF_MAX_SECONDS,
    DEX_RATE_LIMIT_MAX_RETRIES,
    DEX_REVALIDATION_MAX_MC_RATIO,
    DEX_TARGET_REQUESTS_PER_MINUTE,
    DEXSCREENER_URL,
)
from ..store import DashboardStore
from .runtime_health import runtime_health


logger = logging.getLogger("market.data")

# Fomo network IDs mapped to DexScreener chain IDs. Unknown networks are not
# guessed: using market data from another chain is worse than leaving it blank.
DEX_CHAIN_IDS = {
    "1": "ethereum",
    "56": "bsc",
    "8453": "base",
    "1399811149": "solana",
    "4663": "robinhood",
}

# For this dashboard, market cap should normally be expressed from a direct
# USD/stable quote when DexScreener exposes one. Many tracked Robinhood-chain
# tokens also trade against their linked stock token; that pool can dominate
# liquidity while producing a different USD-derived MC than the direct stable
# market that Fomo uses. Symbols are deliberately explicit rather than using a
# fuzzy "contains USD" rule, which could accidentally classify unrelated assets.
USD_STABLE_QUOTE_SYMBOLS = frozenset({
    "USDC",
    "USDT",
    "USDG",
    "USDS",
    "DAI",
    "PYUSD",
    "FDUSD",
    "USDE",
})

# Store token_refs() shape kept local to this service for clarity.
# key, address, network_id, reference_mc, reference_price, selected_pair_address, pair_confirmed, revalidate_pair
MarketRef = tuple[str, str, int | str | None, float | None, float | None, str | None, bool, bool]


def _mapping(value: object) -> dict:
    return value if isinstance(value, dict) else {}


class _DexRequestGovernor:
    """Globally pace Dex requests and back off after upstream HTTP 429s.

    The sliding window enforces the configured maximum while `min_interval`
    prevents the short request bursts that a pure per-minute counter permits.
    A 429 pauses every caller through this same governor, so later batches do
    not continue hammering Dex while the service is throttling us.
    """

    def __init__(
        self,
        requests_per_minute: int,
        min_interval_seconds: float = DEX_MIN_REQUEST_INTERVAL_SECONDS,
    ) -> None:
        self._limit = max(1, int(requests_per_minute))
        self._min_interval = max(0.0, float(min_interval_seconds))
        self._timestamps: deque[float] = deque()
        self._next_request_at = 0.0
        self._backoff_until = 0.0
        self._backoff_seconds = 0.0

    async def acquire(self) -> None:
        loop = asyncio.get_running_loop()
        while True:
            now = loop.time()
            while self._timestamps and now - self._timestamps[0] >= 60:
                self._timestamps.popleft()

            wait_until = max(self._next_request_at, self._backoff_until)
            if len(self._timestamps) >= self._limit:
                wait_until = max(wait_until, self._timestamps[0] + 60.0)

            wait_for = wait_until - now
            if wait_for > 0:
                await asyncio.sleep(wait_for)
                continue

            granted_at = loop.time()
            self._timestamps.append(granted_at)
            self._next_request_at = granted_at + self._min_interval
            return

    def rate_limited(self, retry_after: str | None = None) -> float:
        """Activate global backoff and return the chosen delay in seconds."""
        explicit_delay = _retry_after_seconds(retry_after)
        if explicit_delay is not None:
            delay = explicit_delay
        else:
            delay = (
                DEX_RATE_LIMIT_BACKOFF_INITIAL_SECONDS
                if self._backoff_seconds <= 0
                else min(
                    self._backoff_seconds * 2,
                    DEX_RATE_LIMIT_BACKOFF_MAX_SECONDS,
                )
            )
        delay = min(max(delay, 0.0), DEX_RATE_LIMIT_BACKOFF_MAX_SECONDS)
        self._backoff_seconds = max(delay, DEX_RATE_LIMIT_BACKOFF_INITIAL_SECONDS)
        now = asyncio.get_running_loop().time()
        self._backoff_until = max(self._backoff_until, now + delay)
        return delay

    def succeeded(self) -> None:
        """Reset exponential backoff after a successful Dex response."""
        self._backoff_seconds = 0.0


def _retry_after_seconds(value: str | None) -> float | None:
    """Parse Retry-After seconds or an RFC HTTP-date into a non-negative delay."""
    if value is None:
        return None
    try:
        seconds = float(value.strip())
    except (AttributeError, TypeError, ValueError):
        try:
            retry_at = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        seconds = (
            retry_at.astimezone(timezone.utc) - datetime.now(timezone.utc)
        ).total_seconds()
        return max(0.0, seconds)
    return seconds if math.isfinite(seconds) and seconds >= 0 else None


class MarketRefreshScheduler:
    """Deduplicate queued token refreshes while preserving mid-flight reschedules."""

    def __init__(self) -> None:
        self._pending: set[str] = set()
        self._in_flight: set[str] = set()
        self._reschedule: set[str] = set()
        self._wake = asyncio.Event()

    def schedule(self, key: str, *, reschedule_if_in_flight: bool = True) -> bool:
        if not key:
            return False
        if key in self._in_flight:
            if not reschedule_if_in_flight:
                return False
            added = key not in self._reschedule
            self._reschedule.add(key)
            return added
        if key in self._pending:
            return False
        self._pending.add(key)
        self._wake.set()
        return True

    async def take(self) -> set[str]:
        while not self._pending:
            self._wake.clear()
            await self._wake.wait()
        keys = set(self._pending)
        self._pending.clear()
        self._in_flight.update(keys)
        if not self._pending:
            self._wake.clear()
        return keys

    def complete(self, keys: set[str]) -> None:
        for key in keys:
            self._in_flight.discard(key)
            if key in self._reschedule:
                self._reschedule.remove(key)
                self._pending.add(key)
        if self._pending:
            self._wake.set()

    @property
    def pending_count(self) -> int:
        return len(self._pending)


def _safe_float(value):
    if value is None:
        return None
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _pair_market_cap(pair: dict) -> float | None:
    market_cap = _safe_float(pair.get("marketCap"))
    return market_cap if market_cap is not None else _safe_float(pair.get("fdv"))


def _token_pairs(pairs: list[dict], token_address: str, network_id) -> list[dict]:
    """Return only pairs whose base token is the tracked token on its chain.

    DexScreener's pair-level marketCap/fdv describe the base token. Accepting a
    quote-only match can therefore attach another token's market cap to our card.
    """
    address = token_address.lower()
    expected_chain = DEX_CHAIN_IDS.get(str(network_id))
    if expected_chain is None:
        return []

    return [
        pair
        for pair in pairs
        if isinstance(pair, dict)
        and str(pair.get("chainId") or "").lower() == expected_chain
        and str(_mapping(pair.get("baseToken")).get("address") or "").lower()
        == address
    ]


def _mc_distance(pair: dict, reference_mc: float) -> float:
    """Symmetric log distance: 2x and 0.5x are equally far from Fomo."""
    pair_mc = _pair_market_cap(pair)
    if pair_mc is None or pair_mc <= 0 or reference_mc <= 0:
        return math.inf
    return abs(math.log(pair_mc / reference_mc))


def _is_mc_coherent_with_reference(pair: dict, reference_mc: float) -> bool:
    """Reject pools whose MC is implausibly far from a fresh Fomo trade MC."""
    pair_mc = _pair_market_cap(pair)
    if pair_mc is None or pair_mc <= 0 or reference_mc <= 0:
        return False
    ratio = max(pair_mc / reference_mc, reference_mc / pair_mc)
    return ratio <= DEX_REVALIDATION_MAX_MC_RATIO


def _pair_discovery_score(pair: dict, reference_mc: float | None, reference_price: float | None = None) -> float:
    """Score a coherent pool using Fomo proximity plus market credibility.

    Liquidity and 24h volume are logarithmic so large pools gain confidence
    without letting raw size overwhelm the Fomo price anchor. This specifically
    avoids selecting dust pools merely because their MC happens to match exactly.
    """
    mc_distance = _mc_distance(pair, reference_mc) if reference_mc is not None else math.inf
    pair_price = _safe_float(pair.get("priceUsd"))
    price_distance = (
        abs(math.log(pair_price / reference_price))
        if pair_price is not None and pair_price > 0 and reference_price is not None and reference_price > 0
        else math.inf
    )
    if not math.isfinite(mc_distance) and not math.isfinite(price_distance):
        return -math.inf
    # MC remains the primary anchor. Live `prices` adds an independent Fomo
    # discriminator when available, especially useful across multiple pools.
    evidence_distance = (mc_distance if math.isfinite(mc_distance) else 0.0)
    if math.isfinite(price_distance):
        evidence_distance += 0.75 * price_distance
    liquidity = _safe_float(_mapping(pair.get("liquidity")).get("usd")) or 0.0
    volume = _safe_float(_mapping(pair.get("volume")).get("h24")) or 0.0
    return (
        -evidence_distance
        + DEX_PAIR_LIQUIDITY_WEIGHT * math.log10(1.0 + max(0.0, liquidity))
        + DEX_PAIR_VOLUME_WEIGHT * math.log10(1.0 + max(0.0, volume))
    )


def _is_usd_stable_quote(pair: dict) -> bool:
    symbol = str(_mapping(pair.get("quoteToken")).get("symbol") or "").upper()
    return symbol in USD_STABLE_QUOTE_SYMBOLS


def _discover_pair(
    candidates: list[dict],
    reference_mc: float | None,
    reference_price: float | None = None,
) -> dict | None:
    """Choose the market used for MC, preferring direct USD/stable quotes.

    Fresh Fomo MC (trade or trending) is the primary anchor. When available,
    the live Fomo price is an additional discriminator. If at least one
    stable-quoted pool is coherent with the primary evidence, stable pools compete: a much deeper
    stock-token/ETH pool must not replace the direct USD market merely because
    it has more liquidity. If no stable pool is coherent, fall back to coherent
    chain-correct pools so non-standard tokens without a usable USD pool still work.

    Within the selected candidate class, liquidity and volume remain logarithmic
    tie-breakers so an accidentally exact dust pool does not win by MC proximity
    alone.
    """
    def coherent(pair: dict) -> bool:
        if reference_mc is not None and reference_mc > 0:
            return _is_mc_coherent_with_reference(pair, reference_mc)
        pair_price = _safe_float(pair.get("priceUsd"))
        if pair_price is None or pair_price <= 0 or reference_price is None or reference_price <= 0:
            return False
        ratio = max(pair_price / reference_price, reference_price / pair_price)
        return ratio <= DEX_REVALIDATION_MAX_MC_RATIO

    stable_candidates = [pair for pair in candidates if _is_usd_stable_quote(pair)]
    coherent_stable = [pair for pair in stable_candidates if coherent(pair)]
    if coherent_stable:
        return max(
            coherent_stable,
            key=lambda pair: _pair_discovery_score(pair, reference_mc, reference_price),
        )

    coherent_candidates = [pair for pair in candidates if coherent(pair)]
    if not coherent_candidates:
        return None
    return max(
        coherent_candidates,
        key=lambda pair: _pair_discovery_score(pair, reference_mc, reference_price),
    )


def _selected_pair(candidates: list[dict], selected_pair_address: str | None) -> dict | None:
    if not selected_pair_address:
        return None
    selected = selected_pair_address.lower()
    return next(
        (pair for pair in candidates if str(pair.get("pairAddress") or "").lower() == selected),
        None,
    )


def _oldest_pair_created_at(
    pairs: list[dict], token_address: str, network_id
) -> datetime | None:
    """Return token-age evidence independently from market-pair selection.

    Market-cap selection may deliberately reject every DexScreener pool when its
    MC is too far from a fresh Fomo trade. AGE must not disappear in that case:
    pairCreatedAt is still valid creation metadata for a chain-correct pool whose
    base token is the tracked token.
    """
    created_values = []
    for pair in _token_pairs(pairs, token_address, network_id):
        created_at_ms = _safe_float(pair.get("pairCreatedAt"))
        if created_at_ms is not None and created_at_ms > 0:
            created_values.append(created_at_ms)

    if not created_values:
        return None

    try:
        return datetime.fromtimestamp(min(created_values) / 1000, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def _pick_pair(
    pairs: list[dict],
    token_address: str,
    network_id,
    reference_mc: float | None,
    selected_pair_address: str | None,
    pair_confirmed: bool = False,
    revalidate_pair: bool = False,
    reference_price: float | None = None,
) -> tuple[dict | None, bool]:
    """Return the MC pair and whether successive Fomo evidence confirmed it.

    Discovery strongly prefers a direct USD/stable quote. The first selection is
    provisional; later independent Fomo evidence that re-discovers the same
    address confirms it. Once confirmed, that pair is locked and fresh signals no
    longer trigger pool hunting. A confirmed pair is reconsidered only if it
    disappears from DexScreener's current response.
    """
    candidates = _token_pairs(pairs, token_address, network_id)
    if not candidates:
        return None, pair_confirmed

    reference = _safe_float(reference_mc)
    selected = _selected_pair(candidates, selected_pair_address)

    # Confirmation is the end of discovery, not merely a UI flag. Once two
    # independent Fomo-guided selections agree, follow that exact market through
    # later BUY/SELLs and large price moves. If Dex stops returning the pair,
    # discovery is allowed again below instead of pinning a dead address.
    if pair_confirmed and selected is not None:
        return selected, True

    price_reference = _safe_float(reference_price)
    if revalidate_pair and ((reference is not None and reference > 0) or (price_reference is not None and price_reference > 0)):
        # While the pair is still provisional, fresh Fomo trade/trending/price
        # evidence may correct an initially wrong pool. Confirmed pairs have
        # already returned above and are intentionally not re-scored.
        discovered = _discover_pair(candidates, reference, _safe_float(reference_price))
        if discovered is not None:
            same_as_previous = (
                selected_pair_address is not None
                and str(discovered.get("pairAddress") or "").lower()
                == selected_pair_address.lower()
            )
            # Successive Fomo evidence confirms a pool only when re-discovery
            # independently selects the same address. A replacement remains
            # provisional until later Fomo evidence agrees with it.
            return discovered, bool(same_as_previous)
        return None, False

    # Quiet-period refresh: follow the selected market without comparing it to
    # old Fomo MC. Otherwise a real x2/x10 could incorrectly trigger switching.
    if selected is not None:
        return selected, pair_confirmed

    # Initial discovery is anchored to Fomo while liquidity and volume can
    # outweigh an accidentally exact MC from a dust pool.
    if reference is not None and reference > 0:
        return _discover_pair(candidates, reference), False

    # Last-resort fallback only when Fomo supplied no usable MC. It remains
    # provisional because there is no Fomo evidence to confirm the choice.
    return (
        max(
            candidates,
            key=lambda pair: _safe_float((pair.get("liquidity") or {}).get("usd")) or 0,
        ),
        False,
    )

def _group_batches(refs: list[MarketRef]) -> list[tuple[str, list[MarketRef]]]:
    """Group by DexScreener chain, then split into API-sized batches."""
    unique = {ref[0]: ref for ref in refs}
    by_chain: dict[str, list[MarketRef]] = defaultdict(list)

    for ref in unique.values():
        chain_id = DEX_CHAIN_IDS.get(str(ref[2]))
        if chain_id:
            by_chain[chain_id].append(ref)

    batches: list[tuple[str, list[MarketRef]]] = []
    for chain_id, chain_refs in by_chain.items():
        for index in range(0, len(chain_refs), DEX_BATCH_SIZE):
            batches.append((chain_id, chain_refs[index:index + DEX_BATCH_SIZE]))
    return batches


def _periodic_interval(refs: list[MarketRef]) -> float:
    """Choose an ALERTS refresh cadence that scales with its API batch count."""
    request_count = len(_group_batches(refs))
    if request_count == 0:
        return DEX_MIN_REFRESH_SECONDS

    seconds_for_target_rate = request_count * 60 / DEX_TARGET_REQUESTS_PER_MINUTE
    return max(DEX_MIN_REFRESH_SECONDS, seconds_for_target_rate)


async def _refresh_batch(
    session: aiohttp.ClientSession,
    governor: _DexRequestGovernor,
    store: DashboardStore,
    chain_id: str,
    refs: list[MarketRef],
) -> bool:
    if not refs:
        return True

    addresses = ",".join(address for _, address, _, _, _, _, _, _ in refs)
    url = DEXSCREENER_URL.format(chain_id=chain_id, addresses=addresses)

    data = None
    for attempt in range(DEX_RATE_LIMIT_MAX_RETRIES + 1):
        try:
            await governor.acquire()
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as response:
                if response.status == 429:
                    delay = governor.rate_limited(response.headers.get("Retry-After"))
                    logger.warning(
                        "DexScreener HTTP 429; global backoff %.1fs (attempt %s/%s)",
                        delay,
                        attempt + 1,
                        DEX_RATE_LIMIT_MAX_RETRIES + 1,
                    )
                    continue
                if response.status != 200:
                    logger.warning("DexScreener HTTP %s", response.status)
                    return False
                data = await response.json()
                governor.succeeded()
                break
        except Exception as exc:
            logger.warning("DexScreener request failed: %s", exc)
            return False

    if data is None:
        logger.warning(
            "DexScreener batch abandoned after %s rate-limit retries; "
            "later Fomo/periodic activity can retry it",
            DEX_RATE_LIMIT_MAX_RETRIES,
        )
        return False

    if not isinstance(data, list):
        logger.warning("DexScreener returned an unexpected non-list token payload")
        return False

    # /tokens/v1/{chainId}/{tokenAddresses} returns the pair array directly.
    pairs = [pair for pair in data if isinstance(pair, dict)]

    for key, address, network_id, reference_mc, reference_price, selected_pair_address, pair_confirmed, revalidate in refs:
        # A successful HTTP response completes TRENDING-only enrichment even if
        # Dex has no usable pair for this token. Repeated TRENDING ticks must not
        # retry the same lookup forever; a later ALERTS trade can still refresh it.
        await store.mark_market_enrichment_attempted(key)
        # AGE is independent metadata. Resolve it before MC pair selection so a
        # pool rejected for MC divergence (for example a stale/dust pool) can
        # still provide a valid pairCreatedAt for this exact token and chain.
        oldest_pair_created_at = _oldest_pair_created_at(pairs, address, network_id)

        pair, confirmed = _pick_pair(
            pairs,
            address,
            network_id,
            reference_mc,
            selected_pair_address,
            pair_confirmed,
            revalidate,
            reference_price,
        )
        if not pair:
            if oldest_pair_created_at is not None:
                await store.update_market_data(
                    key,
                    None,
                    None,
                    oldest_pair_created_at,
                    None,
                )
            continue

        market_cap = _pair_market_cap(pair)
        volume_24h = _safe_float(_mapping(pair.get("volume")).get("h24"))

        await store.update_market_data(
            key,
            market_cap,
            volume_24h,
            oldest_pair_created_at,
            pair.get("pairAddress"),
            pair_revalidated=revalidate,
            pair_confirmed=confirmed,
        )
    return True


async def _refresh_refs(
    session: aiohttp.ClientSession,
    governor: _DexRequestGovernor,
    store: DashboardStore,
    refs: list[MarketRef],
) -> bool:
    success = True
    for chain_id, batch in _group_batches(refs):
        success = await _refresh_batch(session, governor, store, chain_id, batch) and success
    return success


async def run_market_cap_refresher(
    store: DashboardStore,
    stop_event: asyncio.Event,
    refresh_scheduler: MarketRefreshScheduler,
) -> None:
    """Refresh ALERTS continuously and service targeted shared-token enrichment."""
    governor = _DexRequestGovernor(DEX_HARD_REQUESTS_PER_MINUTE)

    async with aiohttp.ClientSession(
        headers={"User-Agent": "FomoAlertDashboard/1.0"}
    ) as session:
        refs = await store.token_refs(include_trending_only=False)
        if await _refresh_refs(session, governor, store, refs):
            await runtime_health.refresh_success("dex")
        else:
            await runtime_health.refresh_error("dex", "one or more DexScreener batches failed")
        next_periodic = asyncio.get_running_loop().time() + _periodic_interval(refs)

        while not stop_event.is_set():
            now = asyncio.get_running_loop().time()
            timeout = max(0.0, next_periodic - now)

            try:
                keys = await asyncio.wait_for(refresh_scheduler.take(), timeout=timeout)
            except asyncio.TimeoutError:
                # TRENDING-only tokens use targeted one-time enrichment. The
                # periodic board refresh is reserved for ALERTS, avoiding a
                # second live Dex pipeline for the trending feed.
                refs = await store.token_refs(include_trending_only=False)
                if await _refresh_refs(session, governor, store, refs):
                    await runtime_health.refresh_success("dex")
                else:
                    await runtime_health.refresh_error("dex", "one or more DexScreener batches failed")
                next_periodic = (
                    asyncio.get_running_loop().time() + _periodic_interval(refs)
                )
                continue

            try:
                event_refs = await store.token_refs(keys, revalidate_pair=True)
                if await _refresh_refs(session, governor, store, event_refs):
                    await runtime_health.refresh_success("dex")
                else:
                    await runtime_health.refresh_error("dex", "one or more DexScreener batches failed")
            finally:
                # A signal received while these keys were in flight is queued
                # exactly once for the next pass.
                refresh_scheduler.complete(keys)
