import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
JWT_FILE = BASE_DIR / "jwt.json"
TOPIC_FILE = BASE_DIR / "fomo_topic.json"

FOMO_WS_URL = "wss://prod-api.fomo.family/ws"
# Direct multi-chain portfolio refresh. Fomo only returns all supported networks
# when this header is supplied; without it the endpoint can return Solana only.
FOMO_SUPPORTED_CHAINS = "1,56,143,4663,8453,1399811149"
# trending_tokens uses the supported-chain list itself as its WS topicId.
FOMO_TRENDING_TOPIC_ID = FOMO_SUPPORTED_CHAINS
BALANCE_REFRESH_DEFAULT_SECONDS = 30
BALANCE_REFRESH_MIN_SECONDS = 10
BALANCE_SETTINGS_FILE = BASE_DIR / "fomo_balance_settings.json"
FOLLOWING_REFRESH_DEFAULT_SECONDS = 60
FOLLOWING_REFRESH_MIN_SECONDS = 10
FOLLOWING_SETTINGS_FILE = BASE_DIR / "fomo_following_settings.json"
WS_LOG_FILE = BASE_DIR / "fomo_ws_last_session.json"
DASHBOARD_SETTINGS_FILE = BASE_DIR / "fomo_dashboard_settings.json"

# Optional explicit account identity when no verified fomo_topic.json exists.
# Otherwise the first trading_activity topicId captured by the Chrome bridge is
# persisted and locked for the lifetime of the dashboard process.
FOMO_TOPIC_ID = os.environ.get("FOMO_TOPIC_ID", "")

# Current DexScreener token endpoint: up to 30 addresses from one chain per
# request, with a documented 300 requests/minute limit. Real-world 429s can
# occur below that headline limit, so the dashboard deliberately runs at a
# conservative 120 rpm and spaces requests instead of allowing short bursts.
DEXSCREENER_URL = "https://api.dexscreener.com/tokens/v1/{chain_id}/{addresses}"
DEX_BATCH_SIZE = 30
DEX_TARGET_REQUESTS_PER_MINUTE = 120
DEX_HARD_REQUESTS_PER_MINUTE = 120
DEX_MIN_REFRESH_SECONDS = 5
DEX_MIN_REQUEST_INTERVAL_SECONDS = 60 / DEX_HARD_REQUESTS_PER_MINUTE
DEX_RATE_LIMIT_BACKOFF_INITIAL_SECONDS = 2
DEX_RATE_LIMIT_BACKOFF_MAX_SECONDS = 30
DEX_RATE_LIMIT_MAX_RETRIES = 3

# TRENDING already supplies live Fomo MC/price. Dex is therefore enrichment for
# TRENDING-only tokens (not a second live-price feed). TRENDING and eligible
# held-ALERT price evidence may revalidate a provisional pair at most once per
# cooldown; BUY/SELL events remain immediate and are not throttled here.
FOMO_AUX_MARKET_REVALIDATION_COOLDOWN_SECONDS = 30

# Per-token `prices` subscriptions are reserved for tokens that are both held
# by the active Fomo account and still present in ALERTS. The pump adds at most
# one topic per interval; DexScreener handles general market refreshes.
FOMO_PRICE_SUBSCRIBE_INTERVAL_SECONDS = 1.0

# PONS is an append-only graduation log, not a live market-data feed. Polling
# matches the validated standalone watcher cadence. PONS Launchpad graduations
# tracked by this endpoint are Robinhood-chain tokens.
PONS_GRADUATIONS_POLL_SECONDS = 3.0
PONS_NETWORK_ID = 4663

# During pair discovery/revalidation, fresh Fomo MC provides a multiplicative
# sanity band. Coherent USD/stable pools are preferred; otherwise only coherent
# chain-correct pools compete. Incoherent pools never re-enter through scoring.
DEX_REVALIDATION_MAX_MC_RATIO = 2.0

# Within the chosen coherent candidate class (USD/stable first, otherwise
# chain-correct general pools), discovery balances Fomo-MC proximity with
# liquidity and trading activity.
DEX_PAIR_LIQUIDITY_WEIGHT = 0.35
DEX_PAIR_VOLUME_WEIGHT = 0.15

NEW_BADGE_SECONDS = 60

# Raw accepted Fomo BUY/SELL events are kept only for the live order-flow strip
# and velocity score. The buffer is in-memory and resets on process restart.
TRADE_EVENT_WINDOW_MINUTES = 60
TRADE_EVENT_DEDUP_TTL_SECONDS = 6 * 60 * 60
TRADE_EVENT_DEDUP_MAX_ENTRIES = 50_000
MAX_EVENT_FUTURE_SKEW_SECONDS = 24 * 60 * 60

DEFAULT_FIRST_ALERT_MC_CUTOFF = 2_000_000

# Automatic inactive-token removal is disabled until the user sets a duration
# in the dashboard. Inactivity is measured from the latest Fomo BUY or SELL.
DEFAULT_INACTIVE_TOKEN_HOURS = None

SOLD_COOLDOWN_SECONDS = 60

# A position with at most this fraction of its reconstructed token quantity
# remaining is treated as closed. This absorbs rounding, fees and deliberate
# wallet dust without removing meaningful partial positions.
POSITION_DUST_FRACTION = 0.05
PRIVY_APP_ID = "cm6h485o300n3zj9yl6vpedq7"
AUTH_RETRY_SECONDS = 60
WS_LOG_FLUSH_DELAY_SECONDS = 0.25
HEALTH_WS_STALE_SECONDS = 5 * 60

# Shared secret between the Chrome bridge extension and /api/auth/ingest.
# Change this to any random string and mirror it in the extension's background.js.
INGEST_TOKEN = "fomo-local-bridge"
