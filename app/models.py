from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class BuyerState:
    user_id: str
    handle: str
    display_name: str
    bought_at: datetime
    mc_at_alert: float | None
    usd_amount: float | None
    # USD / market-cap is proportional to token quantity while supply is
    # unchanged. Summing that ratio lets us estimate remaining position without
    # needing the token supply or raw token amount from Fomo.
    gross_buy_proxy: float = 0.0
    gross_sell_proxy: float = 0.0

    @property
    def remaining_proxy(self) -> float:
        return max(0.0, self.gross_buy_proxy - self.gross_sell_proxy)

    @property
    def position_left_fraction(self) -> float | None:
        if self.gross_buy_proxy <= 0:
            return None
        return min(1.0, self.remaining_proxy / self.gross_buy_proxy)

    @property
    def is_partial(self) -> bool:
        return self.gross_sell_proxy > 0 and self.remaining_proxy > 0


@dataclass
class SoldBuyerState:
    user_id: str
    handle: str
    display_name: str
    bought_at: datetime
    mc_at_alert: float | None
    usd_amount: float | None
    sell_mc: float | None
    sell_usd_amount: float | None
    sold_at: datetime
    expires_at: datetime


@dataclass
class TradeEventState:
    """One accepted Fomo BUY/SELL kept briefly for live order-flow UI."""

    event_type: str
    user_id: str
    handle: str
    display_name: str
    occurred_at: datetime
    market_cap: float | None
    usd_amount: float | None


@dataclass
class TokenState:
    key: str
    token_address: str
    network_id: int | str | None
    ticker: str
    token_image_url: str | None
    token_name: str | None = None
    # Shared Fomo market evidence. The same TokenState backs ALERTS and TRENDING
    # so DexScreener enrichment is never duplicated for a token seen in both.
    fomo_trending_mc: float | None = None
    fomo_trending_price: float | None = None
    fomo_price: float | None = None
    holders: int | None = None
    trending_index: int | None = None
    trending_updated_at: datetime | None = None
    is_trending: bool = False
    buyers: dict[str, BuyerState] = field(default_factory=dict)
    sold_buyers: dict[str, SoldBuyerState] = field(default_factory=dict)
    # Ephemeral order-flow buffer. It is pruned to TRADE_EVENT_WINDOW_MINUTES
    # and intentionally disappears on process restart.
    trade_events: list[TradeEventState] = field(default_factory=list)
    first_signal_mc: float | None = None
    last_trade_mc: float | None = None
    current_mc: float | None = None
    volume_24h: float | None = None
    oldest_pair_created_at: datetime | None = None
    last_mc_update: datetime | None = None
    dex_pair_address: str | None = None
    # Discovery chooses a credible pair from Fomo market evidence. BUY/SELLs
    # always request revalidation while the pair is provisional; throttled
    # TRENDING and optional held-ALERT prices evidence can also correct it.
    # Successive agreement on the same pair confirms and locks that market.
    # Held-ALERT `prices` evidence is
    # optional; DexScreener remains the general market-data source.
    dex_pair_confirmed: bool = False
    # True after fresh Fomo evidence has requested pair revalidation. BUY/SELL
    # signals set it immediately; auxiliary TRENDING/held-prices evidence is
    # throttled so high-frequency updates cannot turn into high-frequency Dex
    # requests. Confirmed pairs remain locked by market_data.py.
    dex_pair_needs_revalidation: bool = False
    # TRENDING-only tokens need Dex once for shared metadata such as AGE. A
    # successful Dex response marks that enrichment attempted even when no
    # coherent MC pair exists, preventing every trending tick from retrying it.
    dex_enrichment_attempted: bool = False
    # Monotonic timestamp of the last auxiliary (TRENDING/held-prices) request for a
    # provisional ALERTS pair. This is runtime-only state by design.
    last_aux_market_refresh_requested_at: float | None = None
    last_activity_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    new_until: datetime | None = None

    @property
    def alert_count(self) -> int:
        return len(self.buyers)
