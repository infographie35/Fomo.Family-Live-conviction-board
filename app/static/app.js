const board = document.getElementById("board");
const template = document.getElementById("tokenCardTemplate");
const activeTokens = document.getElementById("activeTokens");
const activeBuyers = document.getElementById("activeBuyers");
const multiBuyerTokens = document.getElementById("multiBuyerTokens");
const updatedAt = document.getElementById("updatedAt");
const connectionLabel = document.getElementById("connectionLabel");
const cutoffForm = document.getElementById("cutoffForm");
const cutoffInput = document.getElementById("cutoffInput");
const cutoffStatus = document.getElementById("cutoffStatus");
const authStatus = document.getElementById("authStatus");
const chainFilter = document.getElementById("chainFilter");
const tokenAgeFilter = document.getElementById("tokenAgeFilter");
const inactiveForm = document.getElementById("inactiveForm");
const inactiveInput = document.getElementById("inactiveInput");
const inactiveStatus = document.getElementById("inactiveStatus");
const balanceRefreshForm = document.getElementById("balanceRefreshForm");
const balanceRefreshInput = document.getElementById("balanceRefreshInput");
const balanceRefreshStatus = document.getElementById("balanceRefreshStatus");
const followingRefreshForm = document.getElementById("followingRefreshForm");
const followingRefreshInput = document.getElementById("followingRefreshInput");
const followingRefreshStatus = document.getElementById("followingRefreshStatus");
const layoutToggle = document.getElementById("layoutToggle");
const shell = document.querySelector(".shell");
const alertsTab = document.getElementById("alertsTab");
const trendingTab = document.getElementById("trendingTab");
const trendingTabCount = document.getElementById("trendingTabCount");
const ponsTab = document.getElementById("ponsTab");
const ponsTabCount = document.getElementById("ponsTabCount");
const followingTab = document.getElementById("followingTab");
const watchlistTab = document.getElementById("watchlistTab");
const balanceTab = document.getElementById("balanceTab");
const logTab = document.getElementById("logTab");
const favAlertsTab = document.getElementById("favAlertsTab");
const alertsView = document.getElementById("alertsView");
const trendingView = document.getElementById("trendingView");
const trendingBoard = document.getElementById("trendingBoard");
const trendingEmpty = document.getElementById("trendingEmpty");
const trendingUpdated = document.getElementById("trendingUpdated");
const trendingCount = document.getElementById("trendingCount");
const trendingFilterStatus = document.getElementById("trendingFilterStatus");
const trendingSearch = document.getElementById("trendingSearch");
const trendingChain = document.getElementById("trendingChain");
const trendingMcMin = document.getElementById("trendingMcMin");
const trendingMcMax = document.getElementById("trendingMcMax");
const trendingAge = document.getElementById("trendingAge");
const trendingSort = document.getElementById("trendingSort");
const trendingClear = document.getElementById("trendingClear");
const ponsView = document.getElementById("ponsView");
const ponsBody = document.getElementById("ponsBody");
const ponsEmpty = document.getElementById("ponsEmpty");
const ponsUpdated = document.getElementById("ponsUpdated");
const ponsRetentionForm = document.getElementById("ponsRetentionForm");
const ponsRetentionInput = document.getElementById("ponsRetentionInput");
const ponsRetentionStatus = document.getElementById("ponsRetentionStatus");
const followingView = document.getElementById("followingView");
const watchlistView = document.getElementById("watchlistView");
const balanceView = document.getElementById("balanceView");
const logView = document.getElementById("logView");
const favAlertsView = document.getElementById("favAlertsView");
const logFeed = document.getElementById("logFeed");
const logEmpty = document.getElementById("logEmpty");
const logCount = document.getElementById("logCount");
const logTabCount = document.getElementById("logTabCount");
const logSession = document.getElementById("logSession");
const logUpdated = document.getElementById("logUpdated");
const logSearch = document.getElementById("logSearch");
const logSideFilter = document.getElementById("logSideFilter");
const logChainFilter = document.getElementById("logChainFilter");
const logOutcomeFilter = document.getElementById("logOutcomeFilter");
const logTimeFilter = document.getElementById("logTimeFilter");
const logFavoriteFilter = document.getElementById("logFavoriteFilter");
const logUsdMin = document.getElementById("logUsdMin");
const logUsdMax = document.getElementById("logUsdMax");
const logMcMin = document.getElementById("logMcMin");
const logMcMax = document.getElementById("logMcMax");
const logFiltersClear = document.getElementById("logFiltersClear");
const logFilterStatus = document.getElementById("logFilterStatus");
const favAlertsFeed = document.getElementById("favAlertsFeed");
const favAlertsEmpty = document.getElementById("favAlertsEmpty");
const favAlertsCount = document.getElementById("favAlertsCount");
const favAlertsTokenCount = document.getElementById("favAlertsTokenCount");
const favAlertsTabCount = document.getElementById("favAlertsTabCount");
const favAlertsUpdated = document.getElementById("favAlertsUpdated");
const favAlertsRetentionForm = document.getElementById("favAlertsRetentionForm");
const favAlertsRetentionInput = document.getElementById("favAlertsRetentionInput");
const favAlertsRetentionStatus = document.getElementById("favAlertsRetentionStatus");
const balanceBody = document.getElementById("balanceBody");
const balanceEmpty = document.getElementById("balanceEmpty");
const balanceUpdated = document.getElementById("balanceUpdated");
const balanceTotalValue = document.getElementById("balanceTotalValue");
const balancePositionCount = document.getElementById("balancePositionCount");
const balanceChainSummary = document.getElementById("balanceChainSummary");
const watchlistBoard = document.getElementById("watchlistBoard");
const watchlistEmpty = document.getElementById("watchlistEmpty");
const watchlistUpdated = document.getElementById("watchlistUpdated");
const followingBody = document.getElementById("followingBody");
const followingEmpty = document.getElementById("followingEmpty");
const followingUpdated = document.getElementById("followingUpdated");
let followingProfiles = [];
let followingById = new Map();
let favoriteFollowingIds = new Set();
let followingSort = { key: "favorite", desc: true };
let watchlistKeys = new Set();
let watchlistTokens = [];
let balanceItems = [];
let balanceByKey = new Map();
let ponsItems = [];
let currentView = "alerts";
let lastLogData = { startedAt: null, count: 0, events: [] };
let logPollInFlight = false;
let renderedLogSignature = "";
let renderedFavAlertsSignature = "";
let logFavoriteOnly = false;
let favAlertsSessionId = "";
let favAlertsSeenIds = new Set();
let favAlertTimeNodes = [];
let followingUpdatedAtMs = NaN;
let followingUpdatedCount = 0;
let followingUpdatedFallback = "Waiting for Fomo profile data";
let balanceUpdatedAtMs = NaN;
let balanceUpdatedCount = 0;
let balanceUpdatedFallback = "Waiting for Fomo balance data";
let ponsUpdatedAtMs = NaN;
let ponsUpdatedCount = 0;
let ponsUpdatedFallback = "Waiting for PONS graduation data";

const refreshClocks = {
  balance: { interval: null, deadlineMs: null, scanning: true },
  following: { interval: null, deadlineMs: null, scanning: true },
};

let selectedNetwork = "all";
const TOKEN_AGE_STORAGE_KEY = "fomo-dashboard-token-age";
const TOKEN_AGE_RANGES_MINUTES = Object.freeze({
  "5": [0, 5],
  "10": [0, 10],
  "30": [0, 30],
  "60": [0, 60],
  "60-480": [60, 480],
  "480-1440": [480, 1440],
  "1440+": [1440, null],
});
const TOKEN_AGE_OPTIONS = new Set(["all", ...Object.keys(TOKEN_AGE_RANGES_MINUTES)]);
const savedTokenAge = localStorage.getItem(TOKEN_AGE_STORAGE_KEY);
let selectedTokenAge = TOKEN_AGE_OPTIONS.has(savedTokenAge) ? savedTokenAge : "all";
const BUYER_COLUMNS_STORAGE_KEY = "fomo-dashboard-buyer-columns-v36";
const LEGACY_BUYER_COLUMNS_STORAGE_KEY = "fomo-dashboard-buyer-columns";
const FAVORITE_LANE_FILTER_STORAGE_KEY = "fomo-dashboard-favorite-lane-filters";
const FAV_ALERTS_SEEN_STORAGE_KEY = "fomo-dashboard-fav-alerts-seen-v36-2";
const FAV_ALERTS_RETENTION_STORAGE_KEY = "fomo-dashboard-fav-alerts-retention-minutes-v36-4";
const PONS_RETENTION_STORAGE_KEY = "fomo-dashboard-pons-retention-minutes-v36-13";
const DEFAULT_RETENTION_MINUTES = 60;
const MIN_RETENTION_MINUTES = 1;
const MAX_RETENTION_MINUTES = 10080;
let favAlertsRetentionMinutes = loadStoredRetentionMinutes(FAV_ALERTS_RETENTION_STORAGE_KEY);
let ponsRetentionMinutes = loadStoredRetentionMinutes(PONS_RETENTION_STORAGE_KEY);
const ALERT_BUYER_SECTION_KEYS = Object.freeze(["1", "2", "3plus"]);
const DEFAULT_BUYER_COLUMNS = Object.freeze({
  "1": { min: 1, max: 1 },
  "2": { min: 2, max: 2 },
  "3plus": { min: 3, max: null },
});

function validBuyerRange(range) {
  const min = Number(range?.min);
  const rawMax = range?.max;
  const max = rawMax === null || rawMax === "" || rawMax === undefined ? null : Number(rawMax);
  return Number.isInteger(min) && min >= 1 && min <= 999
    && (max === null || (Number.isInteger(max) && max >= min && max <= 999));
}

function loadBuyerColumnBounds() {
  try {
    const saved = JSON.parse(localStorage.getItem(BUYER_COLUMNS_STORAGE_KEY) || "null");
    if (saved && ALERT_BUYER_SECTION_KEYS.every(key => validBuyerRange(saved[key]))) {
      return Object.fromEntries(ALERT_BUYER_SECTION_KEYS.map(key => [key, {
        min: Number(saved[key].min),
        max: saved[key].max === null || saved[key].max === "" ? null : Number(saved[key].max),
      }]));
    }
  } catch {
    // Invalid current storage is ignored; legacy/default migration below is safe.
  }

  // Migrate the old contiguous two-threshold layout once, preserving the user's
  // existing column boundaries while making all three ranges independent.
  try {
    const legacy = JSON.parse(localStorage.getItem(LEGACY_BUYER_COLUMNS_STORAGE_KEY) || "null");
    const firstMax = Number(legacy?.firstMax);
    const secondMax = Number(legacy?.secondMax);
    if (Number.isInteger(firstMax) && Number.isInteger(secondMax)
        && firstMax >= 1 && secondMax > firstMax && secondMax <= 999) {
      return {
        "1": { min: 1, max: firstMax },
        "2": { min: firstMax + 1, max: secondMax },
        "3plus": { min: secondMax + 1, max: null },
      };
    }
  } catch {
    // Invalid legacy storage falls through to canonical defaults.
  }
  return structuredClone(DEFAULT_BUYER_COLUMNS);
}

function loadSectionKeySet(storageKey, defaultKeys = []) {
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey) || "null");
    if (Array.isArray(saved)) {
      return new Set(saved.filter(key => ALERT_BUYER_SECTION_KEYS.includes(key)));
    }
  } catch {
    // Invalid browser storage falls back to the requested defaults.
  }
  return new Set(defaultKeys);
}

let buyerColumnBounds = loadBuyerColumnBounds();
let favoriteOnlySections = loadSectionKeySet(FAVORITE_LANE_FILTER_STORAGE_KEY);
const LAYOUT_STORAGE_KEY = "fomo-dashboard-layout";
let layoutMode = localStorage.getItem(LAYOUT_STORAGE_KEY) === "lanes" ? "lanes" : "classic";

// Keep cards compact in both layouts. Users can expand a card explicitly.
const BUYERS_CAP = 4;
// Amber outline lifetime on a card that just took a BUY or a SELL.
const FRESH_MS = 120_000;
// Order-flow strip window.
const SPARK_WINDOW_MS = 60 * 60 * 1000;
// Half-life-ish constant for the velocity score used to order cards.
const HEAT_TAU_MIN = 20;
// Lanes grow naturally through ten cards. Only additional cards use the lane's own scrollbar; normal browser scrolling reaches cards below the viewport.
const LANE_CARD_CAP = 10;

const NETWORK_NAMES = {
  "1399811149": "Solana",
  "4663": "Robinhood",
  "56": "BNB",
  "8453": "Base",
  "1": "ETH",
  "143": "Monad",
};

const NETWORK_CLASSES = {
  "1399811149": "chain-solana",
  "4663": "chain-robinhood",
  "56": "chain-bnb",
  "8453": "chain-base",
  "1": "chain-eth",
  "143": "chain-monad",
};

// Path segment used by fomo.family. Unknown chains get no link rather than a
// fabricated one.
const NETWORK_SLUGS = {
  "1399811149": "solana",
  "4663": "robinhood",
  "56": "bnb",
  "8453": "base",
  "1": "ethereum",
};

// Each ALERTS column owns an independent inclusive buyer range. A blank MAX
// means no upper bound; overlapping or gapped ranges are intentional user choices.
function buyerSectionSpecs() {
  const rangeSpec = key => {
    const { min, max } = buyerColumnBounds[key];
    return {
      key,
      title: max === null ? `${min}+ BUYERS` : (min === max ? `${min} BUYERS` : `${min}–${max} BUYERS`),
      isAlertLane: true,
      match: t => t.alertCount >= min && (max === null || t.alertCount <= max),
    };
  };

  return [
    rangeSpec("3plus"),
    rangeSpec("2"),
    rangeSpec("1"),
    {
      key: "exits",
      title: "RECENT EXITS",
      isAlertLane: false,
      match: t => t.alertCount === 0 && (t.soldBuyers || []).length > 0,
    },
  ];
}

const CLASSIC_SECTION_ORDER = ["3plus", "2", "1", "exits"];
const LANE_SECTION_ORDER = ["1", "2", "3plus", "exits"];

// Persistent view state, kept outside the DOM so reconciliation never loses it.
const cards = new Map();
const watchlistCards = new Map();
const trendingCards = new Map();
const sections = new Map();
const expandedKeys = new Set();
const lastActivity = new Map();
const freshUntil = new Map();
let bootstrapped = false;

function formatCompactUsd(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  const n = Number(value);
  const abs = Math.abs(n);

  if (abs >= 1_000_000_000) {
    const v = n / 1_000_000_000;
    return `$${v >= 10 ? v.toFixed(0) : v.toFixed(1)}B`;
  }
  if (abs >= 1_000_000) {
    const v = n / 1_000_000;
    return `$${v >= 10 ? v.toFixed(0) : v.toFixed(1)}M`;
  }
  if (abs >= 1_000) {
    const v = n / 1_000;
    return `$${v >= 100 ? v.toFixed(0) : v.toFixed(1)}K`;
  }
  return `$${n.toFixed(0)}`;
}

function formatCompactNumber(value) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "—";
  const n = Number(value), abs = Math.abs(n);
  if (abs >= 1_000_000) return `${(n / 1_000_000).toFixed(abs >= 10_000_000 ? 0 : 1)}M`;
  if (abs >= 1_000) return `${(n / 1_000).toFixed(abs >= 100_000 ? 0 : 1)}K`;
  return n.toFixed(0);
}

function formatBalanceAmount(value) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "—";
  const n = Number(value), abs = Math.abs(n);
  if (abs >= 1000) return new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(n);
  if (abs >= 1) return n.toLocaleString("en-US", { maximumFractionDigits: 6 });
  return n.toPrecision(4);
}

function formatBalanceUsd(value) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "—";
  const n = Number(value), abs = Math.abs(n);
  if (abs >= 1000) return formatCompactUsd(n);
  if (abs >= 1) return `$${n.toFixed(2)}`;
  return `$${n.toFixed(4)}`;
}

function formatEntryPrice(value) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "—";
  const n = Number(value);
  if (Math.abs(n) >= 1) return `$${n.toFixed(4)}`;
  if (Math.abs(n) >= 0.001) return `$${n.toFixed(6)}`;
  return `$${n.toPrecision(5)}`;
}

function formatSignedUsd(value) {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return "—";
  const n = Number(value);
  const base = formatCompactUsd(Math.abs(n));
  return `${n > 0 ? "+" : n < 0 ? "-" : ""}${base}`;
}

function parseCompactNumber(raw) {
  const value = String(raw ?? "").trim().replaceAll(",", "").toUpperCase();
  const match = value.match(/^([0-9]+(?:\.[0-9]+)?)\s*([KMB])?$/);
  if (!match) return null;

  const base = Number(match[1]);
  if (!Number.isFinite(base) || base <= 0) return null;

  const multiplier = match[2] === "B"
    ? 1_000_000_000
    : match[2] === "M"
      ? 1_000_000
      : match[2] === "K"
        ? 1_000
        : 1;

  return base * multiplier;
}

function formatCutoff(value) {
  const n = Number(value);
  if (!Number.isFinite(n) || n <= 0) return "";

  if (n >= 1_000_000_000) {
    const v = n / 1_000_000_000;
    return `${Number.isInteger(v) ? v.toFixed(0) : v.toFixed(1)}B`;
  }
  if (n >= 1_000_000) {
    const v = n / 1_000_000;
    return `${Number.isInteger(v) ? v.toFixed(0) : v.toFixed(1)}M`;
  }
  if (n >= 1_000) {
    const v = n / 1_000;
    return `${Number.isInteger(v) ? v.toFixed(0) : v.toFixed(1)}K`;
  }
  return String(Math.round(n));
}

function marketCapPerformance(currentMc, firstSignalMc) {
  const current = Number(currentMc);
  const first = Number(firstSignalMc);

  if (!Number.isFinite(current) || !Number.isFinite(first) || first <= 0) {
    return null;
  }

  return ((current - first) / first) * 100;
}

function formatPerformance(value) {
  if (value === null || !Number.isFinite(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(1)}%`;
}

function formatClock(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

// Recency is the point of the board, so rows carry an age, not a wall clock.
// The absolute timestamp stays available on hover.
function relativeAge(ms) {
  if (!Number.isFinite(ms)) return "—";
  const seconds = Math.max(0, Math.floor((Date.now() - ms) / 1000));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h${String(minutes % 60).padStart(2, "0")}`;
  return `${Math.floor(hours / 24)}j`;
}

function shortAddress(address) {
  if (!address) return "—";
  if (address.length <= 18) return address;
  return `${address.slice(0, 8)}…${address.slice(-6)}`;
}

function ageLabel(iso) {
  if (!iso) return "MC waiting";
  return `MC ${relativeAge(Date.parse(iso))} ago`;
}

function tokenAgeLabel(iso) {
  if (!iso) return "—";
  let seconds = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  const days = Math.floor(seconds / 86400);
  seconds %= 86400;
  const hours = Math.floor(seconds / 3600);
  seconds %= 3600;
  const minutes = Math.floor(seconds / 60);
  const secs = seconds % 60;

  if (days > 0) return `${days}j ${hours}h ${minutes}m`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m ${secs}s`;
  return `${secs}s`;
}

// TOKEN AGE is display-only. Fresh-token choices stay cumulative through <1H;
// older-token choices are exclusive ranges so the filter remains useful without
// adding overlapping long-duration buckets. Missing/invalid creation timestamps
// remain visible while market metadata is still being enriched.
function passesTokenAgeFilter(token, now) {
  if (selectedTokenAge === "all") return true;

  const createdAt = Date.parse(token.tokenCreatedAt);
  if (!Number.isFinite(createdAt)) return true;

  const range = TOKEN_AGE_RANGES_MINUTES[selectedTokenAge];
  if (!range) return true;

  const ageMinutes = Math.max(0, now - createdAt) / 60000;
  const [minMinutes, maxMinutes] = range;
  return ageMinutes >= minMinutes && (maxMinutes === null || ageMinutes < maxMinutes);
}

function passesAgeRange(createdAtValue, rangeKey, now = Date.now()) {
  if (rangeKey === "all") return true;
  const createdAt = Date.parse(createdAtValue);
  // Match ALERTS semantics: age is enrichment, so an unknown age must not hide
  // a live Fomo token while DexScreener is still resolving it.
  if (!Number.isFinite(createdAt)) return true;
  const range = TOKEN_AGE_RANGES_MINUTES[rangeKey];
  if (!range) return true;
  const ageMinutes = Math.max(0, now - createdAt) / 60000;
  const [minMinutes, maxMinutes] = range;
  return ageMinutes >= minMinutes && (maxMinutes === null || ageMinutes < maxMinutes);
}

function networkName(networkId) {
  return NETWORK_NAMES[String(networkId)] || `Chain ${networkId ?? "?"}`;
}

function tokenUrl(token) {
  const slug = NETWORK_SLUGS[String(token.networkId)];
  if (!slug || !token.tokenAddress) return null;
  return `https://fomo.family/tokens/${slug}/${encodeURIComponent(token.tokenAddress)}`;
}

function eventTokenKey(event) {
  if (!event?.tokenAddress) return "";
  return `${event.networkId ?? "unknown"}:${String(event.tokenAddress).toLowerCase()}`;
}

function loadStoredRetentionMinutes(storageKey) {
  const saved = Number(localStorage.getItem(storageKey));
  if (Number.isInteger(saved) && saved >= MIN_RETENTION_MINUTES && saved <= MAX_RETENTION_MINUTES) {
    return saved;
  }
  return DEFAULT_RETENTION_MINUTES;
}

function favoriteAlertIsFresh(event, now = Date.now()) {
  const createdAt = Date.parse(event?.createdAt);
  if (!Number.isFinite(createdAt)) return false;
  return now - createdAt < favAlertsRetentionMinutes * 60 * 1000;
}

function favoriteAlertId(event) {
  return String(
    event.tradeId
    || event.id
    || `${event.createdAt || ""}|${event.userId || ""}|${eventTokenKey(event)}|${event.usdAmount ?? ""}`
  );
}

function loadFavoriteSeenState(sessionId) {
  try {
    const saved = JSON.parse(localStorage.getItem(FAV_ALERTS_SEEN_STORAGE_KEY) || "null");
    if (saved?.sessionId === sessionId && Array.isArray(saved.seenIds)) {
      return new Set(saved.seenIds.map(String));
    }
  } catch {
    // Corrupt browser state must never block favorite alerts.
  }
  return new Set();
}

function persistFavoriteSeenState() {
  if (!favAlertsSessionId) return;
  localStorage.setItem(FAV_ALERTS_SEEN_STORAGE_KEY, JSON.stringify({
    sessionId: favAlertsSessionId,
    seenIds: [...favAlertsSeenIds],
  }));
}

function ensureFavoriteAlertsSession(sessionId) {
  const next = String(sessionId || "");
  if (next === favAlertsSessionId) return;
  favAlertsSessionId = next;
  favAlertsSeenIds = next ? loadFavoriteSeenState(next) : new Set();
}

// Fixed log scale ($10 -> $50K) so bar widths are comparable across every card.
function sizeWeight(usd) {
  const n = Number(usd);
  if (!Number.isFinite(n) || n <= 0) return 0.03;
  const lo = Math.log10(10);
  const hi = Math.log10(50_000);
  const w = (Math.log10(Math.max(n, 10)) - lo) / (hi - lo);
  return Math.min(1, Math.max(0.03, w));
}

function amountTier(usd) {
  const n = Number(usd);
  if (!Number.isFinite(n)) return "";
  if (n < 300) return "amt-lo";
  if (n >= 3000) return "amt-hi";
  return "";
}

// Current position rows: one active row per trader plus completed exits still in cooldown.
function buildPositionEvents(token) {
  const out = [];

  for (const buyer of token.buyers || []) {
    const pct = buyer.isPartial && Number.isFinite(Number(buyer.positionLeftPct))
      ? Math.max(0, Number(buyer.positionLeftPct))
      : null;
    out.push({
      id: `b:${buyer.userId}:${buyer.boughtAt}`,
      type: "buy",
      at: Date.parse(buyer.boughtAt),
      iso: buyer.boughtAt,
      userId: buyer.userId,
      name: buyer.handle || buyer.displayName || "?",
      usd: buyer.usdAmount,
      mc: buyer.mcAtAlert,
      pct,
    });
  }

  for (const sold of token.soldBuyers || []) {
    out.push({
      id: `s:${sold.userId}:${sold.soldAt}`,
      type: "sell",
      at: Date.parse(sold.soldAt),
      iso: sold.soldAt,
      userId: sold.userId,
      name: sold.handle || sold.displayName || "?",
      usd: sold.sellUsdAmount,
      // SELL rows price the exit, not the entry.
      mc: sold.sellMc,
      pct: null,
    });
  }

  out.sort((a, b) => b.at - a.at);
  return out;
}

// Raw 60-minute Fomo fill buffer. Unlike the position rows above, this contains
// every accepted BUY and SELL, including repeated BUYs and partial exits.
function buildTradeEvents(token) {
  const out = [];
  for (const [index, event] of (token.tradeEvents || []).entries()) {
    const at = Date.parse(event.occurredAt);
    if (!Number.isFinite(at)) continue;
    out.push({
      id: `f:${index}:${event.type}:${event.userId}:${event.occurredAt}`,
      type: event.type,
      at,
      iso: event.occurredAt,
      name: event.handle || event.displayName || "?",
      usd: event.usdAmount,
      mc: event.marketCap,
      pct: null,
    });
  }
  out.sort((a, b) => b.at - a.at);
  return out;
}

// Every BUY fill in the real 60-minute buffer contributes to velocity. Repeated
// BUYs by the same trader therefore add heat instead of being collapsed into the
// trader's latest position row. Sections remain driven by alertCount.
function heatScore(token, now) {
  let score = 0;
  for (const event of token.tradeEvents || []) {
    if (event.type !== "buy") continue;
    const minutes = (now - Date.parse(event.occurredAt)) / 60000;
    if (Number.isFinite(minutes) && minutes >= 0 && minutes <= 60) {
      score += Math.exp(-minutes / HEAT_TAU_MIN);
    }
  }
  return score;
}

function sparkSvg(events, now) {
  const W = 300;
  const H = 26;
  const MID = 18;
  const parts = [
    `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">`,
    `<line x1="0" y1="${MID}" x2="${W}" y2="${MID}" stroke="#262d35" stroke-width="1"/>`,
  ];

  let drawn = 0;
  for (const event of events) {
    const age = now - event.at;
    if (!Number.isFinite(age) || age < 0 || age > SPARK_WINDOW_MS) continue;
    const x = (1 - age / SPARK_WINDOW_MS) * (W - 4);
    const w = sizeWeight(event.usd);
    if (event.type === "buy") {
      const h = 2 + 15 * w;
      parts.push(`<rect x="${x.toFixed(1)}" y="${(MID - h).toFixed(1)}" width="3" height="${h.toFixed(1)}" fill="#76e7a0" opacity="0.85"/>`);
    } else {
      const h = 2 + 6 * w;
      parts.push(`<rect x="${x.toFixed(1)}" y="${MID.toFixed(1)}" width="3" height="${h.toFixed(1)}" fill="#ff7f8a" opacity="0.8"/>`);
    }
    drawn++;
  }

  if (!drawn) {
    parts.push(`<text x="2" y="${MID - 4}" fill="#4d5761" font-size="8" font-family="Inter, sans-serif">RIEN SUR 60m</text>`);
  }

  parts.push("</svg>");
  return parts.join("");
}

function setText(el, value) {
  if (el.textContent !== value) el.textContent = value;
}

function syncChainFilter(tokens) {
  const networks = new Map();
  for (const token of tokens) {
    const key = String(token.networkId ?? "unknown");
    networks.set(key, networkName(token.networkId));
  }

  const available = [...networks.entries()].sort((a, b) => a[1].localeCompare(b[1]));
  const signature = available.map(([id, label]) => `${id}:${label}`).join("|");
  if (signature !== chainFilter.dataset.signature) {
    chainFilter.dataset.signature = signature;
    chainFilter.replaceChildren();
    const all = document.createElement("option");
    all.value = "all";
    all.textContent = "ALL";
    chainFilter.appendChild(all);

    for (const [id, label] of available) {
      const option = document.createElement("option");
      option.value = id;
      option.textContent = label;
      chainFilter.appendChild(option);
    }
  }

  if (selectedNetwork !== "all" && !networks.has(selectedNetwork)) {
    selectedNetwork = "all";
  }
  if (chainFilter.value !== selectedNetwork) chainFilter.value = selectedNetwork;
}

async function copyAddress(address, button) {
  try {
    await navigator.clipboard.writeText(address);
    const icon = button.querySelector(".copy-icon");
    const old = icon.textContent;
    icon.textContent = "✓";
    setTimeout(() => { icon.textContent = old; }, 900);
  } catch {
    const input = document.createElement("textarea");
    input.value = address;
    document.body.appendChild(input);
    input.select();
    document.execCommand("copy");
    input.remove();
  }
}

function sectionSpec(key) {
  return buyerSectionSpecs().find(spec => spec.key === key);
}

function saveSectionKeySet(storageKey, values) {
  localStorage.setItem(storageKey, JSON.stringify(ALERT_BUYER_SECTION_KEYS.filter(key => values.has(key))));
}

function tokenHasFavoriteBuyer(token) {
  return [...(token.buyers || []), ...(token.soldBuyers || [])].some(
    buyer => favoriteFollowingIds.has(String(buyer.userId || ""))
  );
}

function applyLayoutMode() {
  const lanes = layoutMode === "lanes";
  board.classList.toggle("layout-lanes", lanes);
  shell.classList.toggle("shell-lanes", lanes);
  layoutToggle.checked = lanes;

  // Reorder only the section containers. Cards keep the same DOM nodes and
  // therefore retain expansion state and independent lane scroll positions.
  const order = lanes ? LANE_SECTION_ORDER : CLASSIC_SECTION_ORDER;
  for (const key of order) {
    const spec = sectionSpec(key);
    if (!spec) continue;
    const entry = ensureSection(spec);
    board.appendChild(entry.section);
  }
}

function saveBuyerColumnBounds() {
  localStorage.setItem(BUYER_COLUMNS_STORAGE_KEY, JSON.stringify(buyerColumnBounds));
}

function restoreBuyerRangeInputs(entry, key) {
  const range = buyerColumnBounds[key];
  if (!range || !entry.minInput || !entry.maxInput) return;
  entry.minInput.value = String(range.min);
  entry.maxInput.value = range.max === null ? "" : String(range.max);
}

function commitBuyerSectionRange(key, entry) {
  const min = Number(entry.minInput.value);
  const maxText = entry.maxInput.value.trim();
  const max = maxText === "" ? null : Number(maxText);
  const candidate = { min, max };

  if (!validBuyerRange(candidate)) {
    restoreBuyerRangeInputs(entry, key);
    entry.minInput.classList.add("is-error");
    entry.maxInput.classList.add("is-error");
    window.setTimeout(() => {
      entry.minInput.classList.remove("is-error");
      entry.maxInput.classList.remove("is-error");
    }, 900);
    return;
  }

  buyerColumnBounds = { ...buyerColumnBounds, [key]: candidate };
  saveBuyerColumnBounds();
  render(lastState);
}

function syncBuyerSectionHeader(entry, spec) {
  if (!spec.isAlertLane) {
    setText(entry.titleLabel, spec.title);
  } else {
    const range = buyerColumnBounds[spec.key];
    if (document.activeElement !== entry.minInput) entry.minInput.value = String(range.min);
    if (document.activeElement !== entry.maxInput) entry.maxInput.value = range.max === null ? "" : String(range.max);
  }

  if (entry.favoriteFilter) {
    const active = favoriteOnlySections.has(spec.key);
    entry.favoriteFilter.classList.toggle("active", active);
    entry.favoriteFilter.setAttribute("aria-pressed", String(active));
    entry.favoriteFilter.title = active
      ? "Show all tokens in this buyer range"
      : "Show only tokens bought by favorite Following profiles";
  }
}

function ensureSection(spec) {
  let entry = sections.get(spec.key);
  if (entry) {
    syncBuyerSectionHeader(entry, spec);
    return entry;
  }

  const section = document.createElement("section");
  section.className = `section section-${spec.key}${spec.isAlertLane ? " alert-lane" : ""}`;

  const header = document.createElement("div");
  header.className = "section-header";

  const leftRule = document.createElement("div");
  leftRule.className = "section-rule";

  const title = document.createElement("div");
  title.className = "section-title";

  const titleLabel = document.createElement("span");
  titleLabel.className = "section-title-label";

  let minInput = null;
  let maxInput = null;
  if (spec.isAlertLane) {
    titleLabel.classList.add("buyer-range-editor");
    const minLabel = document.createElement("span");
    minLabel.textContent = "MIN:";
    minInput = document.createElement("input");
    minInput.className = "buyer-range-input";
    minInput.type = "number";
    minInput.inputMode = "numeric";
    minInput.min = "1";
    minInput.max = "999";
    minInput.step = "1";
    minInput.setAttribute("aria-label", `Minimum buyers in ${spec.key} column`);

    const separator = document.createElement("span");
    separator.textContent = "|";
    const maxLabel = document.createElement("span");
    maxLabel.textContent = "MAX:";
    maxInput = document.createElement("input");
    maxInput.className = "buyer-range-input";
    maxInput.type = "number";
    maxInput.inputMode = "numeric";
    maxInput.min = "1";
    maxInput.max = "999";
    maxInput.step = "1";
    maxInput.placeholder = "…";
    maxInput.setAttribute("aria-label", `Maximum buyers in ${spec.key} column; leave blank for no maximum`);
    const suffix = document.createElement("span");
    suffix.textContent = "BUYERS";
    titleLabel.append(minLabel, minInput, separator, maxLabel, maxInput, suffix);

    for (const input of [minInput, maxInput]) {
      input.addEventListener("change", () => commitBuyerSectionRange(spec.key, { minInput, maxInput }));
      input.addEventListener("keydown", event => {
        if (event.key === "Enter") {
          event.preventDefault();
          input.blur();
        }
        if (event.key === "Escape") {
          restoreBuyerRangeInputs({ minInput, maxInput }, spec.key);
          input.blur();
        }
      });
    }
  }

  const count = document.createElement("span");
  count.className = "section-count";

  const favoriteFilter = spec.isAlertLane ? document.createElement("button") : null;
  if (favoriteFilter) {
    favoriteFilter.type = "button";
    favoriteFilter.className = "lane-favorite-filter";
    favoriteFilter.textContent = "★";
    favoriteFilter.setAttribute("aria-label", `Favorite Following filter for ${spec.title}`);
    favoriteFilter.addEventListener("click", () => {
      if (favoriteOnlySections.has(spec.key)) favoriteOnlySections.delete(spec.key);
      else favoriteOnlySections.add(spec.key);
      saveSectionKeySet(FAVORITE_LANE_FILTER_STORAGE_KEY, favoriteOnlySections);
      render(lastState);
    });
  }

  // Alert lanes can contain hundreds of cards. Keep a lane-local shortcut in
  // the sticky header so returning to the first card never affects the other
  // independently scrolled buyer columns.
  const backToTop = spec.isAlertLane ? document.createElement("button") : null;
  if (backToTop) {
    backToTop.type = "button";
    backToTop.className = "lane-back-to-top";
    backToTop.textContent = "↑ Back to Top";
    backToTop.setAttribute("aria-label", `Back to top of ${spec.title}`);
    title.append(titleLabel, favoriteFilter, backToTop, count);
  } else {
    title.append(titleLabel, count);
  }

  const rightRule = document.createElement("div");
  rightRule.className = "section-rule";

  header.append(leftRule, title, rightRule);

  const cardsEl = document.createElement("div");
  cardsEl.className = "cards";
  if (backToTop) {
    backToTop.addEventListener("click", () => {
      cardsEl.scrollTo({ top: 0, behavior: "smooth" });
    });
  }

  section.append(header, cardsEl);
  board.appendChild(section);

  entry = { section, cardsEl, count, titleLabel, minInput, maxInput, favoriteFilter };
  sections.set(spec.key, entry);
  syncBuyerSectionHeader(entry, spec);
  return entry;
}

function createCard(token, registry = cards) {
  const node = template.content.cloneNode(true).querySelector(".token-card");

  const refs = {
    tickerLink: node.querySelector(".ticker-link"),
    watchlist: node.querySelector(".token-watchlist-toggle"),
    newBadge: node.querySelector(".new-badge"),
    cachedBadge: node.querySelector(".cached-badge"),
    holdingBadge: node.querySelector(".holding-badge"),
    avatar: node.querySelector(".token-avatar"),
    copyButton: node.querySelector(".copy-address"),
    addressLabel: node.querySelector(".address-label"),
    mcBox: node.querySelector(".current-mc"),
    mcValue: node.querySelector(".current-mc-value"),
    mcChange: node.querySelector(".current-mc-change"),
    volume: node.querySelector(".volume-24h"),
    tokenAge: node.querySelector(".token-age"),
    network: node.querySelector(".network"),
    mcAge: node.querySelector(".mc-age"),
    spark: node.querySelector(".conviction-spark"),
    buyers: node.querySelector(".buyers"),
    toggle: node.querySelector(".buyers-toggle"),
    forget: node.querySelector(".forget-token"),
  };

  const entry = { node, refs, key: token.key, listSig: "", sparkSig: "", timeNodes: [], address: token.tokenAddress, isAlertCard: registry === cards };

  refs.copyButton.addEventListener("click", () => copyAddress(entry.address, refs.copyButton));
  refs.watchlist.addEventListener("click", () => toggleTokenWatchlist(entry.key));

  refs.toggle.addEventListener("click", () => {
    if (expandedKeys.has(entry.key)) expandedKeys.delete(entry.key);
    else expandedKeys.add(entry.key);
    entry.listSig = "";
    render(lastState);
  });

  refs.forget.addEventListener("click", async () => {
    refs.forget.disabled = true;
    refs.forget.textContent = "…";
    try {
      const response = await fetch("/api/tokens/forget", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key: entry.key }),
      });
      if (!response.ok && response.status !== 404) throw new Error(`HTTP ${response.status}`);
      await refresh();
    } catch (error) {
      refs.forget.disabled = false;
      refs.forget.textContent = "FORGET";
      console.error(error);
    }
  });

  registry.set(token.key, entry);
  return entry;
}

function buildRow(event) {
  const row = document.createElement("div");
  row.className = event.type === "sell" ? "buyer-row sold-row" : "buyer-row";

  const main = document.createElement("div");
  main.className = "buyer-main";

  const name = document.createElement("span");
  name.className = "buyer-name";
  const profile = followingById.get(String(event.userId || ""));
  name.textContent = `${event.name}${profile?.favorite ? " ⭐" : ""}`;
  name.classList.toggle("favorite-trader", Boolean(profile?.favorite));

  const amount = document.createElement("span");
  amount.className = "buyer-amount";
  const tier = amountTier(event.usd);
  if (tier) amount.classList.add(tier);
  amount.textContent = formatCompactUsd(event.usd);

  main.append(name, amount);

  const meta = document.createElement("div");
  meta.className = "buyer-meta";

  const time = document.createElement("span");
  time.className = "buyer-time";
  time.title = formatClock(event.iso);
  time.textContent = relativeAge(event.at);

  const sep = document.createElement("span");
  sep.className = "sep";
  sep.textContent = "·";

  const mc = document.createElement("span");
  mc.className = "buyer-mc";
  const mcStrong = document.createElement("strong");
  mcStrong.textContent = formatCompactUsd(event.mc);
  mc.append("@ ", mcStrong);

  meta.append(time, sep, mc);

  if (profile) {
    const stats = document.createElement("span");
    stats.className = "trader-stats";
    const followers = formatCompactNumber(profile.followers);
    const volume = formatCompactUsd(profile.volume);
    const pnl = formatSignedUsd(profile.pnl24h);
    stats.textContent = `F: ${followers} · Vol: ${volume} · PNL24h: ${pnl}`;
    stats.classList.toggle("pnl-positive", Number(profile.pnl24h) > 0);
    stats.classList.toggle("pnl-negative", Number(profile.pnl24h) < 0);
    meta.append(stats);
  }

  if (event.type === "sell") {
    const sep2 = document.createElement("span");
    sep2.className = "sep";
    sep2.textContent = "·";
    const tag = document.createElement("span");
    tag.className = "sold-pill";
    tag.textContent = "SOLD";
    meta.append(sep2, tag);
  } else if (event.pct !== null) {
    const sep2 = document.createElement("span");
    sep2.className = "sep";
    sep2.textContent = "·";
    const left = document.createElement("span");
    left.className = "position-left";
    left.textContent = `${event.pct.toFixed(0)}% LEFT`;
    meta.append(sep2, left);
  }

  const weight = document.createElement("div");
  weight.className = "buyer-weight";
  const fill = document.createElement("i");
  fill.style.width = `${(sizeWeight(event.usd) * 100).toFixed(1)}%`;
  weight.appendChild(fill);

  row.append(main, meta, weight);
  return { row, time, at: event.at };
}

function updateCard(entry, token, now, sparkGen) {
  const { refs } = entry;
  entry.address = token.tokenAddress;

  setText(refs.tickerLink, token.ticker || "?");
  const favoriteBuyerBought = entry.isAlertCard && tokenHasFavoriteBuyer(token);
  refs.tickerLink.classList.toggle("favorite-buyer-token", favoriteBuyerBought);
  refs.tickerLink.title = favoriteBuyerBought ? "A favorite followed trader bought this token" : "";
  const url = tokenUrl(token);
  if (url) {
    if (refs.tickerLink.getAttribute("href") !== url) refs.tickerLink.setAttribute("href", url);
    refs.tickerLink.title = favoriteBuyerBought
      ? "A favorite followed trader bought this token · Open on fomo.family"
      : "Open on fomo.family";
  } else {
    refs.tickerLink.removeAttribute("href");
  }

  const watched = watchlistKeys.has(token.key);
  refs.watchlist.textContent = watched ? "⭐" : "☆";
  refs.watchlist.classList.toggle("is-watched", watched);
  refs.watchlist.title = watched ? "Remove token from Watchlist" : "Add token to Watchlist";
  refs.watchlist.setAttribute("aria-label", refs.watchlist.title);
  refs.newBadge.hidden = !token.isNew || Boolean(token.watchlistCached);
  refs.cachedBadge.hidden = !token.watchlistCached;
  const holding = balanceByKey.get(String(token.key));
  const holdingValue = Number(holding?.valueUsd);
  refs.holdingBadge.hidden = !(Number.isFinite(holdingValue) && holdingValue > 2);
  if (!refs.holdingBadge.hidden) refs.holdingBadge.title = `You hold ${formatCompactUsd(holdingValue)}`;
  // A cached-only card has no live DashboardStore entry to forget. It stays
  // removable via the star, which is the persistent WATCHLIST action.
  refs.forget.hidden = Boolean(token.watchlistCached);

  const image = token.tokenImageUrl
    ? `url("${token.tokenImageUrl.replaceAll('"', "%22")}")`
    : "";
  if (refs.avatar.style.backgroundImage !== image) refs.avatar.style.backgroundImage = image;

  setText(refs.addressLabel, shortAddress(token.tokenAddress));
  setText(refs.mcValue, formatCompactUsd(token.currentMc));

  const performance = marketCapPerformance(token.currentMc, token.firstSignalMc);
  setText(refs.mcChange, formatPerformance(performance));
  refs.mcBox.classList.remove("is-up", "is-down", "is-flat");
  if (performance === null || Math.abs(performance) < 0.0001) refs.mcBox.classList.add("is-flat");
  else if (performance > 0) refs.mcBox.classList.add("is-up");
  else refs.mcBox.classList.add("is-down");

  setText(refs.volume, formatCompactUsd(token.volume24h));
  setText(refs.tokenAge, tokenAgeLabel(token.tokenCreatedAt));
  setText(refs.mcAge, ageLabel(token.lastMcUpdate));

  const chainClass = NETWORK_CLASSES[String(token.networkId)];
  const chainSig = `${token.networkId}`;
  if (refs.network.dataset.chain !== chainSig) {
    refs.network.dataset.chain = chainSig;
    refs.network.className = "network chain-badge";
    if (chainClass) refs.network.classList.add(chainClass);
    refs.network.textContent = networkName(token.networkId);
  }

  const flowEvents = buildTradeEvents(token);
  const positionEvents = buildPositionEvents(token);

  const sparkSig = `${sparkGen}|${flowEvents.length}|${flowEvents.length ? flowEvents[0].id : ""}`;
  if (sparkSig !== entry.sparkSig) {
    entry.sparkSig = sparkSig;
    refs.spark.innerHTML = sparkSvg(flowEvents, now);
  }

  const expanded = expandedKeys.has(token.key);
  const visible = expanded ? positionEvents : positionEvents.slice(0, BUYERS_CAP);
  const listSig = `${expanded}|${positionEvents.length}|${visible.map(e => { const p = followingById.get(String(e.userId || "")); return `${e.id}~${e.pct ?? ""}~${e.usd ?? ""}~${p?.followers ?? ""}~${p?.volume ?? ""}~${p?.pnl24h ?? ""}~${p?.favorite ?? ""}`; }).join("|")}`;

  if (listSig !== entry.listSig) {
    entry.listSig = listSig;
    entry.timeNodes = [];
    const frag = document.createDocumentFragment();
    for (const event of visible) {
      const built = buildRow(event);
      entry.timeNodes.push(built);
      frag.appendChild(built.row);
    }
    refs.buyers.replaceChildren(frag);

    const hidden = positionEvents.length - visible.length;
    refs.toggle.hidden = positionEvents.length <= BUYERS_CAP;
    refs.toggle.textContent = expanded ? "▲ COLLAPSE" : `▼ +${hidden} OTHERS`;
  }

  for (const built of entry.timeNodes) setText(built.time, relativeAge(built.at));

  entry.node.classList.toggle("is-fresh", (freshUntil.get(token.key) ?? 0) > now);
}

function trendingFilteredTokens(items) {
  const query = trendingSearch.value.trim().toLowerCase();
  const chain = trendingChain.value;
  const minMc = parseLogMetric(trendingMcMin.value);
  const maxMc = parseLogMetric(trendingMcMax.value);
  const now = Date.now();

  return items.filter(token => {
    if (query) {
      const haystack = `${token.ticker || ""} ${token.name || ""} ${token.tokenAddress || ""}`.toLowerCase();
      if (!haystack.includes(query)) return false;
    }
    if (chain !== "all" && String(token.networkId ?? "") !== chain) return false;
    const mc = Number(token.marketCap);
    if (Number.isFinite(minMc) && (!Number.isFinite(mc) || mc < minMc)) return false;
    if (Number.isFinite(maxMc) && (!Number.isFinite(mc) || mc > maxMc)) return false;
    return passesAgeRange(token.tokenCreatedAt, trendingAge.value, now);
  }).sort((a, b) => {
    const aMc = Number(a.marketCap);
    const bMc = Number(b.marketCap);
    const av = Number.isFinite(aMc) ? aMc : -Infinity;
    const bv = Number.isFinite(bMc) ? bMc : -Infinity;
    const delta = trendingSort.value === "asc" ? av - bv : bv - av;
    if (delta !== 0) return delta;
    return (Number(a.index) || 0) - (Number(b.index) || 0);
  });
}

function createTrendingCard(token) {
  const node = document.createElement("article");
  node.className = "token-card trending-card";
  node.innerHTML = `
    <div class="card-head">
      <div class="token-identity">
        <div class="token-avatar"></div>
        <div class="token-title-wrap">
          <div class="token-title-row"><h3 class="ticker"><a class="ticker-link" target="_blank" rel="noopener noreferrer"></a></h3></div>
          <a class="trending-name" target="_blank" rel="noopener noreferrer"></a>
          <button type="button" class="copy-address" title="Copy token address"><span class="address-label"></span><span class="copy-icon">⧉</span></button>
        </div>
      </div>
      <div class="market-stats">
        <div class="current-mc"><span>MC NOW</span><div class="current-mc-line"><strong class="current-mc-value">—</strong></div></div>
        <div class="secondary-market-stats"><span>AGE <strong class="token-age">—</strong></span></div>
      </div>
    </div>
    <div class="trending-meta"><span>HOLDERS <strong class="trending-holders">—</strong></span><span>FOMO TRENDING</span></div>
    <footer class="card-foot"><span class="network chain-badge"></span><span class="mc-age"></span></footer>`;
  const entry = {
    node,
    address: token.tokenAddress,
    tickerLink: node.querySelector(".ticker-link"),
    avatar: node.querySelector(".token-avatar"),
    name: node.querySelector(".trending-name"),
    copy: node.querySelector(".copy-address"),
    addressLabel: node.querySelector(".address-label"),
    mc: node.querySelector(".current-mc-value"),
    age: node.querySelector(".token-age"),
    holders: node.querySelector(".trending-holders"),
    network: node.querySelector(".network"),
    updated: node.querySelector(".mc-age"),
  };
  entry.copy.addEventListener("click", () => copyAddress(entry.address, entry.copy));
  trendingCards.set(token.key, entry);
  return entry;
}

function updateTrendingCard(entry, token) {
  entry.address = token.tokenAddress;
  setText(entry.tickerLink, token.ticker || "?");
  setText(entry.name, token.name || "");
  const url = tokenUrl(token);
  if (url) {
    entry.tickerLink.setAttribute("href", url);
    entry.name.setAttribute("href", url);
  } else {
    entry.tickerLink.removeAttribute("href");
    entry.name.removeAttribute("href");
  }
  const image = token.tokenImageUrl ? `url("${String(token.tokenImageUrl).replaceAll('"', "%22")}")` : "";
  if (entry.avatar.style.backgroundImage !== image) entry.avatar.style.backgroundImage = image;
  setText(entry.addressLabel, shortAddress(token.tokenAddress));
  setText(entry.mc, formatCompactUsd(token.marketCap));
  setText(entry.age, tokenAgeLabel(token.tokenCreatedAt));
  setText(entry.holders, Number.isFinite(Number(token.holders)) ? Number(token.holders).toLocaleString() : "—");
  setText(entry.updated, token.updatedAt ? `Fomo · ${relativeAge(Date.parse(token.updatedAt))} ago` : "Fomo live");
  entry.network.className = "network chain-badge";
  const chainClass = NETWORK_CLASSES[String(token.networkId)];
  if (chainClass) entry.network.classList.add(chainClass);
  setText(entry.network, networkName(token.networkId));
}

function renderTrending(state) {
  const all = Array.isArray(state.trending) ? state.trending : [];
  const items = trendingFilteredTokens(all);
  const rendered = new Set();

  items.forEach((token, index) => {
    const entry = trendingCards.get(token.key) || createTrendingCard(token);
    updateTrendingCard(entry, token);
    const current = trendingBoard.children[index];
    if (current !== entry.node) trendingBoard.insertBefore(entry.node, current || null);
    rendered.add(String(token.key));
  });
  for (const [key, entry] of [...trendingCards]) {
    if (!rendered.has(String(key))) { entry.node.remove(); trendingCards.delete(key); }
  }

  setText(trendingCount, String(items.length));
  setText(trendingTabCount, String(all.length));
  setText(trendingFilterStatus, items.length === all.length ? `SHOWING ALL ${all.length}` : `SHOWING ${items.length} / ${all.length}`);
  setText(trendingUpdated, all.length ? "Fomo WS live" : "Waiting for trending_tokens");
  trendingEmpty.hidden = items.length > 0;
  trendingEmpty.textContent = all.length && !items.length ? "No trending tokens match these filters." : "Waiting for Fomo trending_tokens…";
}

function renderFollowing() {
  const rows = [...followingProfiles];
  const { key, desc } = followingSort;
  rows.sort((a, b) => {
    let av, bv;
    if (key === "name") { av = (a.userHandle || a.displayName || "").toLowerCase(); bv = (b.userHandle || b.displayName || "").toLowerCase(); }
    else { av = key === "favorite" ? Number(Boolean(a.favorite)) : Number(a[key] ?? -Infinity); bv = key === "favorite" ? Number(Boolean(b.favorite)) : Number(b[key] ?? -Infinity); }
    const cmp = typeof av === "string" ? av.localeCompare(bv) : av - bv;
    if (cmp) return desc ? -cmp : cmp;
    return (a.userHandle || a.displayName || "").localeCompare(b.userHandle || b.displayName || "");
  });
  const frag = document.createDocumentFragment();
  for (const profile of rows) {
    const tr = document.createElement("tr");
    if (profile.favorite) tr.classList.add("favorite-profile");
    const trader = document.createElement("td"); trader.className = "following-trader";
    if (profile.profilePicture) { const img = document.createElement("img"); img.src = profile.profilePicture; img.alt = ""; trader.appendChild(img); }
    const identity = document.createElement("span");
    const strong = document.createElement("strong"); strong.textContent = profile.displayName || profile.userHandle || "?";
    const handle = document.createElement("small"); handle.textContent = profile.userHandle ? `@${profile.userHandle}` : "";
    identity.append(strong, handle); trader.append(identity);
    const values = [formatCompactNumber(profile.followers), formatCompactNumber(profile.trades), formatCompactUsd(profile.volume), formatSignedUsd(profile.pnl24h)];
    tr.appendChild(trader);
    values.forEach((value, i) => { const td = document.createElement("td"); td.textContent = value; if (i === 3) td.className = Number(profile.pnl24h) > 0 ? "pnl-positive" : Number(profile.pnl24h) < 0 ? "pnl-negative" : ""; tr.appendChild(td); });
    const fav = document.createElement("td"); const btn = document.createElement("button"); btn.className = "favorite-toggle"; btn.textContent = profile.favorite ? "⭐" : "☆"; btn.title = profile.favorite ? "Remove favorite" : "Add favorite";
    btn.addEventListener("click", () => toggleFavorite(profile.id)); fav.appendChild(btn); tr.appendChild(fav); frag.appendChild(tr);
  }
  followingBody.replaceChildren(frag);
  followingEmpty.hidden = rows.length > 0;
}

async function loadFollowing() {
  try {
    const response = await fetch("/api/following", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    followingProfiles = data.profiles || [];
    followingById = new Map(followingProfiles.map(p => [String(p.id), p]));
    followingUpdatedAtMs = Date.parse(data.updatedAt);
    followingUpdatedCount = followingProfiles.length;
    followingUpdatedFallback = data.lastError || "Waiting for Fomo profile data";
    updateFollowingUpdatedLabel();
    renderFollowing();
    for (const entry of [...cards.values(), ...watchlistCards.values()]) entry.listSig = "";
    render(lastState);
  } catch (error) { console.error("following", error); }
}

async function toggleFavorite(userId) {
  const response = await fetch("/api/following/favorite", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ userId }) });
  if (!response.ok) return;
  const data = await response.json();
  const profile = followingProfiles.find(p => String(p.id) === String(userId));
  if (profile) profile.favorite = data.favorite;
  if (data.favorite) favoriteFollowingIds.add(String(userId));
  else favoriteFollowingIds.delete(String(userId));
  followingById = new Map(followingProfiles.map(p => [String(p.id), p]));
  renderFollowing();
  if (lastState) render(lastState);
  for (const entry of [...cards.values(), ...watchlistCards.values()]) entry.listSig = "";
  render(lastState);
  renderWatchlist();
}

async function loadWatchlist() {
  try {
    const response = await fetch("/api/watchlist", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    watchlistKeys = new Set((data.keys || []).map(String));
    watchlistTokens = data.tokens || [];
    const live = Number(data.liveCount || 0);
    const saved = data.updatedAt ? ` · saved ${relativeAge(Date.parse(data.updatedAt))} ago` : "";
    watchlistUpdated.textContent = `${watchlistKeys.size} tokens · ${live} live${saved}`;
    render(lastState);
    renderWatchlist();
  } catch (error) {
    console.error("watchlist", error);
  }
}

async function toggleTokenWatchlist(key) {
  try {
    const response = await fetch("/api/watchlist/toggle", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key }),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();

    if (data.watchlisted) {
      watchlistKeys.add(String(key));
      if (data.token) {
        const next = watchlistTokens.filter(token => String(token.key) !== String(key));
        next.push({ ...data.token, watchlistCached: false });
        watchlistTokens = next;
      }
    } else {
      watchlistKeys.delete(String(key));
      watchlistTokens = watchlistTokens.filter(token => String(token.key) !== String(key));
    }

    render(lastState);
    renderWatchlist();
    await loadWatchlist();
  } catch (error) {
    console.error("watchlist toggle", error);
  }
}

function renderBalance() {
  const rows = [...balanceItems].sort((a, b) => (Number(b.valueUsd) || 0) - (Number(a.valueUsd) || 0));
  const total = rows.reduce((sum, item) => sum + (Number(item.valueUsd) || 0), 0);
  balanceTotalValue.textContent = formatBalanceUsd(total);
  balancePositionCount.textContent = String(rows.length);

  const chainCounts = new Map();
  for (const item of rows) {
    const key = String(item.networkId ?? "unknown");
    chainCounts.set(key, (chainCounts.get(key) || 0) + 1);
  }
  const chainOrder = ["56", "4663", "1399811149", "8453", "1", "143"];
  const visibleChains = [...chainCounts.entries()].sort((a, b) => {
    const ai = chainOrder.indexOf(a[0]);
    const bi = chainOrder.indexOf(b[0]);
    if (ai !== -1 || bi !== -1) return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi);
    return networkName(a[0]).localeCompare(networkName(b[0]));
  });
  const chainFrag = document.createDocumentFragment();
  visibleChains.forEach(([networkId, count], index) => {
    if (index) {
      const separator = document.createElement("span");
      separator.className = "balance-chain-separator";
      separator.textContent = "|";
      chainFrag.appendChild(separator);
    }
    const badge = document.createElement("span");
    badge.className = "balance-chain-count";
    const chainClass = NETWORK_CLASSES[networkId];
    if (chainClass) badge.classList.add(chainClass);
    badge.textContent = `${networkName(networkId)}: ${count}`;
    chainFrag.appendChild(badge);
  });
  balanceChainSummary.replaceChildren(chainFrag);

  const frag = document.createDocumentFragment();
  for (const item of rows) {
    const tr = document.createElement("tr");
    const token = document.createElement("td");
    token.className = "balance-token";
    if (item.image) {
      const img = document.createElement("img"); img.src = item.image; img.alt = ""; token.appendChild(img);
    }
    const names = document.createElement("span");
    const strong = document.createElement("strong"); strong.textContent = item.symbol || "?";
    const small = document.createElement("small"); small.textContent = item.name || shortAddress(item.tokenAddress);
    names.append(strong, small); token.appendChild(names);
    tr.appendChild(token);

    const values = [
      networkName(item.networkId),
      formatBalanceAmount(item.amount),
      formatBalanceUsd(item.valueUsd),
      formatEntryPrice(item.averageEntryPriceUsd),
      formatSignedUsd(item.unrealizedPnlUsd),
    ];
    values.forEach((value, index) => {
      const td = document.createElement("td"); td.textContent = value;
      if (index === 4) {
        const pnl = Number(item.unrealizedPnlUsd);
        if (Number.isFinite(pnl)) td.className = pnl >= 0 ? "pnl-positive" : "pnl-negative";
      }
      tr.appendChild(td);
    });
    frag.appendChild(tr);
  }
  balanceBody.replaceChildren(frag);
  balanceEmpty.hidden = rows.length > 0;
}

async function loadBalances() {
  try {
    const response = await fetch("/api/balances", { cache: "no-store" });
    if (!response.ok) throw new Error(`balances HTTP ${response.status}`);
    const data = await response.json();
    balanceItems = data.balances || [];
    balanceByKey = new Map(balanceItems.map(item => [String(item.key), item]));
    balanceUpdatedAtMs = Date.parse(data.updatedAt);
    balanceUpdatedCount = balanceItems.length;
    balanceUpdatedFallback = data.lastError || "Waiting for Fomo balance data";
    updateBalanceUpdatedLabel();
    renderBalance();
    render(lastState);
    renderWatchlist();
  } catch (error) { console.error("balances", error); }
}

function ponsGraduationIsFresh(item, now = Date.now()) {
  const graduatedAt = Date.parse(item?.graduatedAt);
  if (!Number.isFinite(graduatedAt)) return false;
  return now - graduatedAt < ponsRetentionMinutes * 60 * 1000;
}

function renderPonsGraduations() {
  const now = Date.now();
  const rows = [...ponsItems]
    .filter(item => ponsGraduationIsFresh(item, now))
    .sort((a, b) => Date.parse(b.graduatedAt || "") - Date.parse(a.graduatedAt || ""));
  const frag = document.createDocumentFragment();

  for (const item of rows) {
    const tr = document.createElement("tr");

    const when = document.createElement("td");
    when.textContent = item.graduatedAtLocal || "—";
    tr.appendChild(when);

    const url = tokenUrl(item);
    for (const value of [item.symbol || "?", item.name || "?"]) {
      const td = document.createElement("td");
      const link = document.createElement("a");
      link.className = "pons-token-link";
      link.textContent = value;
      if (url) {
        link.href = url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
      }
      td.appendChild(link);
      tr.appendChild(td);
    }

    const pair = document.createElement("td");
    pair.textContent = item.pair || "?";
    tr.appendChild(pair);

    const mc = document.createElement("td");
    mc.textContent = formatCompactUsd(item.marketCapUsd);
    tr.appendChild(mc);

    const duration = document.createElement("td");
    duration.textContent = item.duration || "?";
    tr.appendChild(duration);

    const contract = document.createElement("td");
    const copy = document.createElement("button");
    copy.type = "button";
    copy.className = "pons-contract-copy";
    copy.title = `Copy ${item.contract || "contract"}`;
    const label = document.createElement("span");
    label.className = "contract-label";
    label.textContent = shortAddress(item.contract);
    const icon = document.createElement("span");
    icon.className = "copy-icon";
    icon.textContent = "⧉";
    copy.append(label, icon);
    copy.addEventListener("click", () => copyAddress(item.contract || "", copy));
    contract.appendChild(copy);
    tr.appendChild(contract);

    frag.appendChild(tr);
  }

  ponsBody.replaceChildren(frag);
  ponsEmpty.textContent = ponsItems.length
    ? `No PONS graduations in the last ${ponsRetentionMinutes} min.`
    : "Waiting for new PONS graduations…";
  ponsEmpty.hidden = rows.length > 0;
  ponsUpdatedCount = rows.length;
  setText(ponsTabCount, String(rows.length));
  updatePonsUpdatedLabel();
}

async function loadPonsGraduations() {
  try {
    const response = await fetch("/api/pons/graduations", { cache: "no-store" });
    if (!response.ok) throw new Error(`PONS HTTP ${response.status}`);
    const data = await response.json();
    ponsItems = Array.isArray(data.graduations) ? data.graduations : [];
    ponsUpdatedAtMs = Date.parse(data.updatedAt);
    ponsUpdatedFallback = data.lastError || "Waiting for new PONS graduations";
    renderPonsGraduations();
  } catch (error) {
    console.error("PONS graduations", error);
  }
}

function formatLogTime(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function parseLogMetric(value) {
  const raw = String(value || "").trim().toLowerCase().replace(/[$,\s]/g, "");
  if (!raw) return null;
  const match = raw.match(/^([0-9]+(?:\.[0-9]+)?)([kmb])?$/);
  if (!match) return NaN;
  const multipliers = { k: 1e3, m: 1e6, b: 1e9 };
  return Number(match[1]) * (match[2] ? multipliers[match[2]] : 1);
}

function logMetricInRange(value, minInput, maxInput) {
  const min = parseLogMetric(minInput.value);
  const max = parseLogMetric(maxInput.value);
  const numeric = Number(value);
  if (Number.isFinite(min) && (!Number.isFinite(numeric) || numeric < min)) return false;
  if (Number.isFinite(max) && (!Number.isFinite(numeric) || numeric > max)) return false;
  return true;
}

function filteredLogEvents(data) {
  const events = Array.isArray(data.events) ? data.events : [];
  const query = logSearch.value.trim().toLowerCase();
  const side = logSideFilter.value;
  const chain = logChainFilter.value;
  const outcome = logOutcomeFilter.value;
  const minutes = logTimeFilter.value === "all" ? null : Number(logTimeFilter.value);
  const cutoff = Number.isFinite(minutes) ? Date.now() - minutes * 60_000 : null;

  return events.filter(event => {
    if (query) {
      const trader = String(event.userHandle || event.displayName || event.userId || "").toLowerCase();
      const token = String(event.ticker || "").toLowerCase();
      if (!trader.includes(query) && !token.includes(query)) return false;
    }
    if (side === "buy" && event.type !== "swap_buy") return false;
    if (side === "sell" && event.type !== "swap_sell") return false;
    if (chain !== "all" && String(event.networkId ?? "") !== chain) return false;
    if (outcome === "accepted" && !event.accepted) return false;
    if (outcome === "ignored" && event.accepted) return false;
    if (logFavoriteOnly && !event.favorite) return false;
    if (!logMetricInRange(event.usdAmount, logUsdMin, logUsdMax)) return false;
    if (!logMetricInRange(event.marketCap, logMcMin, logMcMax)) return false;
    if (cutoff !== null) {
      const createdAt = Date.parse(event.createdAt || "");
      if (!Number.isFinite(createdAt) || createdAt < cutoff) return false;
    }
    return true;
  });
}

function logFiltersAreActive() {
  return Boolean(
    logSearch.value.trim()
    || logSideFilter.value !== "all"
    || logChainFilter.value !== "all"
    || logOutcomeFilter.value !== "all"
    || logTimeFilter.value !== "all"
    || logFavoriteOnly
    || logUsdMin.value.trim()
    || logUsdMax.value.trim()
    || logMcMin.value.trim()
    || logMcMax.value.trim()
  );
}

function renderLog(data) {
  const allEvents = Array.isArray(data.events) ? data.events : [];
  const events = filteredLogEvents(data);
  const frag = document.createDocumentFragment();
  for (const event of events) {
    const row = document.createElement("div"); row.className = "log-row";
    const trader = document.createElement("div"); trader.className = "log-trader"; trader.textContent = event.userHandle || event.displayName || event.userId || "?";
    const side = document.createElement("div"); side.className = `log-side ${event.type === "swap_buy" ? "buy" : "sell"}`; side.textContent = event.type === "swap_buy" ? "BUY" : "SELL";
    const token = document.createElement("div"); token.className = "log-token"; token.textContent = event.ticker || "?"; token.title = event.tokenAddress || "";
    const usd = document.createElement("div"); usd.textContent = formatCompactUsd(event.usdAmount);
    const mc = document.createElement("div"); mc.textContent = `@ ${formatCompactUsd(event.marketCap)} MC`;
    const match = document.createElement("div"); match.className = "log-match";
    if (event.following) { const badge = document.createElement("span"); badge.className = "log-badge following"; badge.textContent = "FOLLOWING"; match.appendChild(badge); }
    if (event.favorite) { const badge = document.createElement("span"); badge.className = "log-badge favorite"; badge.textContent = "★ FAVORITE"; match.appendChild(badge); }
    if (!event.following) { const badge = document.createElement("span"); badge.className = "log-badge"; badge.textContent = "NO MATCH"; match.appendChild(badge); }
    const result = document.createElement("span"); result.className = `log-outcome ${event.accepted ? "accepted" : "ignored"}`; result.textContent = event.accepted ? "ACCEPTED" : "IGNORED"; match.appendChild(result);
    const time = document.createElement("div"); time.className = "log-time"; time.textContent = formatLogTime(event.createdAt);
    row.title = `tradeId: ${event.tradeId || "?"}\nuserId: ${event.userId || "?"}\ntoken: ${event.tokenAddress || "?"}\nnetworkId: ${event.networkId ?? "?"}`;
    row.append(trader, side, token, usd, mc, match, time); frag.appendChild(row);
  }
  logFeed.replaceChildren(frag);
  logEmpty.hidden = events.length > 0;
  logEmpty.textContent = allEvents.length > 0 && events.length === 0 ? "No events match these filters." : "No WS BUY/SELL received yet.";
  setText(logCount, String(data.count ?? allEvents.length));
  setText(logTabCount, String(data.count ?? allEvents.length));
  setText(logFilterStatus, logFiltersAreActive() ? `SHOWING ${events.length} / ${allEvents.length}` : `SHOWING ALL ${allEvents.length}`);
  setText(logSession, data.startedAt ? `Session ${formatLogTime(data.startedAt)}` : "");
  setText(logUpdated, `· ${formatClock(new Date().toISOString())}`);
  renderedLogSignature = logDataSignature(data);
}

function renderCurrentLogFilters() {
  // Filters only affect the current browser view. The WS log continues to be
  // collected and polled unchanged in the background.
  renderLog(lastLogData);
}

function logDataSignature(data) {
  const version = Number.isFinite(Number(data.version)) ? Number(data.version) : data.count;
  return `${data.startedAt || ""}|${version ?? 0}`;
}

function favoriteBuyEvents(data) {
  const now = Date.now();
  return (Array.isArray(data.events) ? data.events : []).filter(event =>
    event.type === "swap_buy"
    && event.accepted
    && event.favorite
    && event.tokenAddress
    && favoriteAlertIsFresh(event, now)
  );
}

function favoriteBuyerStatus(event) {
  const key = eventTokenKey(event);
  const token = (lastState.tokens || []).find(item => String(item.key) === key);
  if (!token) return "";

  const userId = String(event.userId || "");
  const buyer = (token.buyers || []).find(item => String(item.userId || "") === userId);
  if (buyer?.isPartial && Number.isFinite(Number(buyer.positionLeftPct))) {
    return `${Math.max(0, Number(buyer.positionLeftPct)).toFixed(0)}% LEFT`;
  }

  const sold = (token.soldBuyers || []).find(item => String(item.userId || "") === userId);
  return sold ? "SOLD" : "";
}

function markFavoriteAlertsSeen(events) {
  let changed = false;
  for (const event of events) {
    const id = favoriteAlertId(event);
    if (!favAlertsSeenIds.has(id)) {
      favAlertsSeenIds.add(id);
      changed = true;
    }
  }
  if (changed) persistFavoriteSeenState();
}

function syncFavoriteAlertsUnread(events) {
  const currentIds = new Set(events.map(favoriteAlertId));
  const prunedSeenIds = new Set([...favAlertsSeenIds].filter(id => currentIds.has(id)));
  if (prunedSeenIds.size !== favAlertsSeenIds.size) {
    favAlertsSeenIds = prunedSeenIds;
    persistFavoriteSeenState();
  }

  if (currentView === "favAlerts") markFavoriteAlertsSeen(events);
  const unreadTokenKeys = new Set(
    events
      .filter(event => !favAlertsSeenIds.has(favoriteAlertId(event)))
      .map(eventTokenKey)
      .filter(Boolean)
  );
  const unread = unreadTokenKeys.size;

  setText(favAlertsTabCount, String(unread));
  favAlertsTabCount.hidden = unread === 0;
  favAlertsTab.classList.toggle("has-unread", unread > 0 && currentView !== "favAlerts");
}

function renderFavoriteAlerts(data) {
  ensureFavoriteAlertsSession(data.startedAt);
  const events = favoriteBuyEvents(data);
  syncFavoriteAlertsUnread(events);

  const groups = new Map();
  for (const event of events) {
    const key = eventTokenKey(event);
    if (!key) continue;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(event);
  }

  favAlertTimeNodes = [];
  const frag = document.createDocumentFragment();
  for (const buys of groups.values()) {
    const newest = buys[0];
    const card = document.createElement("article");
    card.className = "fav-alert-card";

    const head = document.createElement("div");
    head.className = "fav-alert-head";
    const identity = document.createElement("div");
    identity.className = "fav-alert-identity";
    const ticker = document.createElement("a");
    ticker.className = "fav-alert-ticker";
    ticker.textContent = newest.ticker || "?";
    const tickerUrl = tokenUrl(newest);
    if (tickerUrl) {
      ticker.href = tickerUrl;
      ticker.target = "_blank";
      ticker.rel = "noopener noreferrer";
      ticker.title = "Open token on Fomo";
    }
    const network = document.createElement("span");
    network.className = "chain-badge";
    const chainClass = NETWORK_CLASSES[String(newest.networkId)];
    if (chainClass) network.classList.add(chainClass);
    network.textContent = networkName(newest.networkId);
    identity.append(ticker, network);
    head.appendChild(identity);

    const copy = document.createElement("button");
    copy.type = "button";
    copy.className = "fav-contract-copy";
    copy.title = "Copy token contract";
    const address = document.createElement("span");
    address.textContent = newest.tokenAddress || "—";
    const copyIcon = document.createElement("span");
    copyIcon.className = "copy-icon";
    copyIcon.textContent = "⧉";
    copy.append(address, copyIcon);
    copy.addEventListener("click", () => copyAddress(newest.tokenAddress, copy));

    const buysWrap = document.createElement("div");
    buysWrap.className = "fav-buy-list";
    for (const event of buys) {
      const row = document.createElement("div");
      row.className = "fav-buy-row";

      const trader = document.createElement("div");
      trader.className = "fav-buy-trader";
      trader.textContent = `★ ${event.userHandle || event.displayName || event.userId || "?"}`;

      const buyLink = document.createElement("a");
      buyLink.className = "fav-buy-link";
      const url = tokenUrl(event);
      if (url) {
        buyLink.href = url;
        buyLink.target = "_blank";
        buyLink.rel = "noopener noreferrer";
      } else {
        buyLink.removeAttribute("href");
      }
      const buyLabel = document.createElement("span");
      buyLabel.textContent = "BUY · ";
      const age = document.createElement("span");
      const at = Date.parse(event.createdAt);
      age.textContent = relativeAge(at);
      age.title = formatClock(event.createdAt);
      favAlertTimeNodes.push({ node: age, at });
      const suffix = document.createElement("span");
      suffix.textContent = url ? " ↗ FOMO" : "";
      buyLink.append(buyLabel, age, suffix);

      const amount = document.createElement("div");
      amount.className = "fav-buy-amount";
      amount.textContent = formatCompactUsd(event.usdAmount);
      const mc = document.createElement("div");
      mc.className = "fav-buy-mc";
      mc.textContent = `MC ${formatCompactUsd(event.marketCap)}`;

      const statusText = favoriteBuyerStatus(event);
      const status = document.createElement("div");
      status.className = "fav-buy-status";
      status.textContent = statusText;
      status.hidden = !statusText;
      if (statusText === "SOLD") status.classList.add("sold");

      row.append(trader, buyLink, amount, mc, status);
      buysWrap.appendChild(row);
    }

    card.append(head, copy, buysWrap);
    frag.appendChild(card);
  }

  favAlertsFeed.replaceChildren(frag);
  favAlertsEmpty.hidden = events.length > 0;
  setText(favAlertsCount, String(events.length));
  setText(favAlertsTokenCount, String(groups.size));
  setText(favAlertsUpdated, data.startedAt ? `Session ${formatLogTime(data.startedAt)}` : "");
  renderedFavAlertsSignature = `${logDataSignature(data)}|${events.map(favoriteAlertId).join("|")}`;
}

async function loadLog() {
  if (logPollInFlight) return;
  logPollInFlight = true;
  try {
    const response = await fetch("/api/log", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    lastLogData = await response.json();
    const signature = logDataSignature(lastLogData);
    const favoriteEvents = favoriteBuyEvents(lastLogData);
    ensureFavoriteAlertsSession(lastLogData.startedAt);
    syncFavoriteAlertsUnread(favoriteEvents);
    const count = lastLogData.count ?? lastLogData.events?.length ?? 0;
    setText(logCount, String(count));
    setText(logTabCount, String(count));

    if (
      currentView === "log"
      && (renderedLogSignature !== signature || logTimeFilter.value !== "all")
    ) {
      renderLog(lastLogData);
    }
    if (currentView === "favAlerts") {
      const favoriteSignature = `${signature}|${favoriteEvents.map(favoriteAlertId).join("|")}`;
      if (renderedFavAlertsSignature !== favoriteSignature) {
        renderFavoriteAlerts(lastLogData);
      }
    }
  } catch (error) {
    console.error("LOG/FAV ALERTS refresh failed", error);
  } finally {
    logPollInFlight = false;
  }
}

function showView(view) {
  currentView = view;
  alertsView.hidden = view !== "alerts";
  trendingView.hidden = view !== "trending";
  ponsView.hidden = view !== "pons";
  followingView.hidden = view !== "following";
  watchlistView.hidden = view !== "watchlist";
  balanceView.hidden = view !== "balance";
  logView.hidden = view !== "log";
  favAlertsView.hidden = view !== "favAlerts";
  alertsTab.classList.toggle("active", view === "alerts");
  trendingTab.classList.toggle("active", view === "trending");
  ponsTab.classList.toggle("active", view === "pons");
  followingTab.classList.toggle("active", view === "following");
  watchlistTab.classList.toggle("active", view === "watchlist");
  balanceTab.classList.toggle("active", view === "balance");
  logTab.classList.toggle("active", view === "log");
  favAlertsTab.classList.toggle("active", view === "favAlerts");

  if (view === "log") renderLog(lastLogData);
  if (view === "favAlerts") renderFavoriteAlerts(lastLogData);
  if (view === "following") loadFollowing();
  if (view === "pons") loadPonsGraduations();
  if (view === "watchlist") loadWatchlist();
  if (view === "balance") loadBalances();
  if (view === "log" || view === "favAlerts") loadLog();
}

let lastState = { tokens: [] };

function render(state) {
  lastState = state;
  const all = state.tokens || [];
  const now = Date.now();
  favoriteFollowingIds = new Set((state.favoriteFollowingIds || []).map(String));
  renderTrending(state);

  const alertPool = all.filter(token => !watchlistKeys.has(String(token.key)));
  syncChainFilter(alertPool);

  // A change in lastActivityAt is a fill. First paint after load must not flag
  // the whole board as fresh.
  const liveKeys = new Set();
  for (const token of all) {
    liveKeys.add(token.key);
    const previous = lastActivity.get(token.key);
    if (bootstrapped && previous !== token.lastActivityAt) {
      freshUntil.set(token.key, now + FRESH_MS);
    }
    lastActivity.set(token.key, token.lastActivityAt);
  }
  bootstrapped = true;

  for (const key of [...lastActivity.keys()]) {
    if (!liveKeys.has(key)) {
      lastActivity.delete(key);
      freshUntil.delete(key);
      expandedKeys.delete(key);
    }
  }

  // Blockchain and token-age filters are presentation-only. Backend tracking
  // and market-data enrichment continue for every admitted token. Unknown token
  // age remains visible until tokenCreatedAt is available.
  const tokens = alertPool.filter(token => {
    const networkMatches = selectedNetwork === "all"
      || String(token.networkId ?? "unknown") === selectedNetwork;
    return networkMatches && passesTokenAgeFilter(token, now);
  });

  setText(activeTokens, String(tokens.length));
  setText(activeBuyers, String(tokens.reduce((sum, token) => sum + token.alertCount, 0)));
  setText(multiBuyerTokens, String(tokens.filter(token => token.alertCount >= 2).length));
  setText(updatedAt, `· ${formatClock(state.generatedAt)}`);

  if (document.activeElement !== cutoffInput && state.firstAlertMcCutoff) {
    cutoffInput.value = formatCutoff(state.firstAlertMcCutoff);
  }
  if (document.activeElement !== inactiveInput) {
    inactiveInput.value = state.inactiveTokenHours ?? "";
  }
  if (document.activeElement !== balanceRefreshInput && state.balanceRefreshSeconds) {
    balanceRefreshInput.value = state.balanceRefreshSeconds;
  }
  if (document.activeElement !== followingRefreshInput && state.followingRefreshSeconds) {
    followingRefreshInput.value = state.followingRefreshSeconds;
  }
  syncRefreshCountdowns(state);

  const heat = new Map();
  for (const token of tokens) heat.set(token.key, heatScore(token, now));

  const latestEventAt = token => {
    const events = token.tradeEvents || [];
    const last = events.length ? Date.parse(events[events.length - 1].occurredAt) : NaN;
    if (Number.isFinite(last)) return last;
    const fallback = Date.parse(token.lastActivityAt);
    return Number.isFinite(fallback) ? fallback : 0;
  };

  const sparkGen = Math.floor(now / 5000);
  const rendered = new Set();

  for (const spec of buyerSectionSpecs()) {
    const favoriteOnly = spec.isAlertLane && favoriteOnlySections.has(spec.key);
    const items = tokens.filter(spec.match)
      .filter(token => !favoriteOnly || tokenHasFavoriteBuyer(token))
      .sort((a, b) => {
      // In Lanes, the first two configured buyer ranges follow the latest
      // accepted Fomo BUY/SELL. The highest-conviction range keeps heat order.
      if (layoutMode === "lanes" && ["1", "2"].includes(spec.key)) {
        return latestEventAt(b) - latestEventAt(a);
      }
      const delta = (heat.get(b.key) ?? 0) - (heat.get(a.key) ?? 0);
      if (Math.abs(delta) > 1e-6) return delta;
      return latestEventAt(b) - latestEventAt(a);
    });

    const sectionEntry = ensureSection(spec);
    // Lanes are structural: all three buyer columns stay visible even when
    // empty. Classic mode keeps the compact hide-empty behavior.
    sectionEntry.section.hidden = items.length === 0 && !(layoutMode === "lanes" && spec.isAlertLane);
    setText(sectionEntry.count, ` ${items.length}`);

    let index = 0;
    for (const token of items) {
      const entry = cards.get(token.key) || createCard(token);
      updateCard(entry, token, now, sparkGen);
      const current = sectionEntry.cardsEl.children[index];
      if (current !== entry.node) sectionEntry.cardsEl.insertBefore(entry.node, current || null);
      index++;
      rendered.add(token.key);
    }
  }

  for (const [key, entry] of [...cards]) {
    if (!rendered.has(key)) {
      entry.node.remove();
      cards.delete(key);
    }
  }
  scheduleLaneSizing();
  renderWatchlist();
}

function renderWatchlist() {
  const liveByKey = new Map(
    (lastState.tokens || [])
      .filter(token => watchlistKeys.has(String(token.key)))
      .map(token => [String(token.key), { ...token, watchlistCached: false }])
  );
  const combined = new Map();

  for (const token of watchlistTokens) {
    if (watchlistKeys.has(String(token.key))) combined.set(String(token.key), token);
  }
  for (const [key, token] of liveByKey) combined.set(key, token);

  const tokens = [...combined.values()].sort((a, b) => {
    const aTime = Date.parse(a.lastActivityAt || "") || 0;
    const bTime = Date.parse(b.lastActivityAt || "") || 0;
    return bTime - aTime;
  });
  const now = Date.now();
  const sparkGen = Math.floor(now / 5000);
  const rendered = new Set();

  tokens.forEach((token, index) => {
    const entry = watchlistCards.get(token.key) || createCard(token, watchlistCards);
    updateCard(entry, token, now, sparkGen);
    const current = watchlistBoard.children[index];
    if (current !== entry.node) watchlistBoard.insertBefore(entry.node, current || null);
    rendered.add(String(token.key));
  });

  for (const [key, entry] of [...watchlistCards]) {
    if (!rendered.has(String(key))) {
      entry.node.remove();
      watchlistCards.delete(key);
    }
  }

  watchlistEmpty.hidden = tokens.length > 0;
}

function sizeLaneScrollports() {
  if (layoutMode !== "lanes") return;

  for (const section of board.querySelectorAll(".alert-lane")) {
    const cardsEl = section.querySelector(".cards");
    if (!cardsEl) continue;
    const children = [...cardsEl.children];

    cardsEl.classList.toggle("lane-can-pan", children.length >= 2);
    if (children.length < 2) {
      cardsEl.style.removeProperty("--lane-visible-height");
      cardsEl.style.removeProperty("--lane-pan-tail");
      cardsEl.scrollTop = 0;
      continue;
    }

    // A lane keeps the natural height of up to ten cards. The extra tail is
    // scroll runway only: it lets the user move a 2-10 card stack vertically
    // without shrinking the lane. Card 11+ naturally overflows the same cap.
    const visibleCards = children.slice(0, LANE_CARD_CAP);
    const styles = getComputedStyle(cardsEl);
    const gap = Number.parseFloat(styles.rowGap || styles.gap) || 0;
    const paddingTop = Number.parseFloat(styles.paddingTop) || 0;
    const paddingBottom = Number.parseFloat(styles.paddingBottom) || 0;
    const stackHeight = visibleCards.reduce((sum, card) => sum + card.getBoundingClientRect().height, 0)
      + gap * Math.max(0, visibleCards.length - 1)
      + paddingTop + paddingBottom;
    const lastCardHeight = visibleCards.at(-1)?.getBoundingClientRect().height || 0;
    const panTail = Math.max(0, stackHeight - lastCardHeight - paddingTop - paddingBottom);

    cardsEl.style.setProperty("--lane-visible-height", `${stackHeight}px`);
    cardsEl.style.setProperty("--lane-pan-tail", `${panTail}px`);
  }
}

function scheduleLaneSizing() {
  requestAnimationFrame(sizeLaneScrollports);
}

function formatAuthCountdown(seconds) {
  const n = Number(seconds);
  if (!Number.isFinite(n)) return "expiry unknown";
  if (n <= 0) return "expired";
  if (n < 60) return `${Math.floor(n)}s`;
  if (n < 3600) return `${Math.floor(n / 60)}m`;
  const hours = Math.floor(n / 3600);
  const minutes = Math.floor((n % 3600) / 60);
  return `${hours}h ${minutes}m`;
}

function captureRefreshClock(clock, intervalValue, remainingValue) {
  const interval = Number(intervalValue);
  const remaining = Number(remainingValue);
  if (!Number.isFinite(interval) || interval < 1) return;

  clock.interval = interval;
  clock.scanning = !Number.isFinite(remaining) || remaining <= 0;
  clock.deadlineMs = clock.scanning ? null : Date.now() + Math.max(0, remaining) * 1000;
}

function renderRefreshClock(statusEl, clock) {
  if (!Number.isFinite(clock.interval) || clock.interval < 1) return;
  statusEl.classList.remove("is-error", "is-ok");

  if (clock.scanning || !Number.isFinite(clock.deadlineMs)) {
    statusEl.textContent = `Scanning now · every ${clock.interval}s`;
    return;
  }

  const remaining = Math.max(0, Math.ceil((clock.deadlineMs - Date.now()) / 1000));
  statusEl.textContent = remaining <= 0
    ? `Scanning now · every ${clock.interval}s`
    : `Next scan in ${remaining}s · every ${clock.interval}s`;
}

function syncRefreshCountdowns(state) {
  captureRefreshClock(refreshClocks.balance, state.balanceRefreshSeconds, state.balanceRefreshRemainingSeconds);
  captureRefreshClock(refreshClocks.following, state.followingRefreshSeconds, state.followingRefreshRemainingSeconds);
  renderRefreshClock(balanceRefreshStatus, refreshClocks.balance);
  renderRefreshClock(followingRefreshStatus, refreshClocks.following);
}

function updateFollowingUpdatedLabel() {
  followingUpdated.textContent = Number.isFinite(followingUpdatedAtMs)
    ? `${followingUpdatedCount} profiles · Updated ${relativeAge(followingUpdatedAtMs)} ago`
    : followingUpdatedFallback;
}

function updateBalanceUpdatedLabel() {
  balanceUpdated.textContent = Number.isFinite(balanceUpdatedAtMs)
    ? `${balanceUpdatedCount} balances · Updated ${relativeAge(balanceUpdatedAtMs)} ago`
    : balanceUpdatedFallback;
}

function updatePonsUpdatedLabel() {
  ponsUpdated.textContent = Number.isFinite(ponsUpdatedAtMs)
    ? `${ponsUpdatedCount} graduations · Updated ${relativeAge(ponsUpdatedAtMs)} ago`
    : ponsUpdatedFallback;
}

function tickLiveUi() {
  renderRefreshClock(balanceRefreshStatus, refreshClocks.balance);
  renderRefreshClock(followingRefreshStatus, refreshClocks.following);
  updateFollowingUpdatedLabel();
  updateBalanceUpdatedLabel();
  updatePonsUpdatedLabel();
  for (const item of favAlertTimeNodes) setText(item.node, relativeAge(item.at));
}

async function refreshAuthStatus() {
  try {
    const response = await fetch("/api/auth/status", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();

    authStatus.classList.remove("is-ok", "is-error");

    if (!data.hasCredentials || Number(data.expiresInSeconds) <= 0) {
      authStatus.textContent = "AUTH · WAITING FOR FOMO";
      authStatus.classList.add("is-error");
      return;
    }

    if (data.lastError) {
      authStatus.textContent = `AUTH · ${data.lastError}`;
      authStatus.classList.add("is-error");
      return;
    }

    authStatus.textContent = `AUTH · ${formatAuthCountdown(data.expiresInSeconds)}`;
    authStatus.classList.add("is-ok");
  } catch (error) {
    authStatus.classList.remove("is-ok");
    authStatus.classList.add("is-error");
    authStatus.textContent = "AUTH · unavailable";
  }
}

async function refresh() {
  try {
    const response = await fetch("/api/state", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const state = await response.json();
    if (Array.isArray(state.watchlistKeys)) {
      watchlistKeys = new Set(state.watchlistKeys.map(String));
    }
    const wsHealth = state.health?.components?.websocket;
    connectionLabel.textContent = wsHealth?.connected && !state.health?.degraded
      ? "LIVE"
      : "DEGRADED";
    // Reconciliation makes a full pass cheap, so ages, spark and the fresh
    // outline stay accurate every tick without rebuilding the board.
    render(state);
  } catch (error) {
    connectionLabel.textContent = "OFFLINE";
    console.error(error);
  }
}

cutoffForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const value = parseCompactNumber(cutoffInput.value);
  cutoffStatus.classList.remove("is-error", "is-ok");

  if (value === null) {
    cutoffStatus.textContent = "Use values like 121K, 2M or 8.5M";
    cutoffStatus.classList.add("is-error");
    return;
  }

  try {
    const response = await fetch("/api/settings/first-alert-mc-cutoff", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ value }),
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const data = await response.json();
    cutoffInput.value = formatCutoff(data.firstAlertMcCutoff);
    cutoffStatus.textContent = "Saved · applies only to new tokens";
    cutoffStatus.classList.add("is-ok");
    await refresh();
  } catch (error) {
    cutoffStatus.textContent = "Could not save cutoff";
    cutoffStatus.classList.add("is-error");
    console.error(error);
  }
});

balanceRefreshForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const seconds = Number(balanceRefreshInput.value);
  balanceRefreshStatus.classList.remove("is-error", "is-ok");
  if (!Number.isInteger(seconds) || seconds < 10) {
    balanceRefreshStatus.textContent = "Enter a whole number of at least 10 seconds";
    balanceRefreshStatus.classList.add("is-error");
    return;
  }
  try {
    const response = await fetch("/api/settings/balance-refresh-seconds", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ seconds }),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    balanceRefreshInput.value = data.balanceRefreshSeconds;
    balanceRefreshStatus.textContent = `Saved · rescan every ${data.balanceRefreshSeconds}s`;
    balanceRefreshStatus.classList.add("is-ok");
    await refresh();
  } catch (error) {
    balanceRefreshStatus.textContent = "Could not save balance rescan interval";
    balanceRefreshStatus.classList.add("is-error");
    console.error(error);
  }
});

followingRefreshForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const seconds = Number(followingRefreshInput.value);
  followingRefreshStatus.classList.remove("is-error", "is-ok");
  if (!Number.isInteger(seconds) || seconds < 10) {
    followingRefreshStatus.textContent = "Enter a whole number of at least 10 seconds";
    followingRefreshStatus.classList.add("is-error");
    return;
  }
  try {
    const response = await fetch("/api/settings/following-refresh-seconds", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ seconds }),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    followingRefreshInput.value = data.followingRefreshSeconds;
    followingRefreshStatus.textContent = `Saved · rescan every ${data.followingRefreshSeconds}s`;
    followingRefreshStatus.classList.add("is-ok");
    await loadFollowing();
  } catch (error) {
    followingRefreshStatus.textContent = "Could not save Following rescan interval";
    followingRefreshStatus.classList.add("is-error");
    console.error(error);
  }
});

inactiveForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const raw = inactiveInput.value.trim();
  const hours = raw === "" ? null : Number(raw);
  inactiveStatus.classList.remove("is-error", "is-ok");

  if (hours !== null && (!Number.isFinite(hours) || hours <= 0)) {
    inactiveStatus.textContent = "Enter hours above 0, or leave empty to disable";
    inactiveStatus.classList.add("is-error");
    return;
  }

  try {
    const response = await fetch("/api/settings/inactive-token-hours", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ hours }),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const data = await response.json();
    inactiveInput.value = data.inactiveTokenHours ?? "";
    inactiveStatus.textContent = data.inactiveTokenHours == null
      ? "Off · inactive tokens are kept"
      : `Saved · removes after ${data.inactiveTokenHours}h without BUY/SELL`;
    inactiveStatus.classList.add("is-ok");
    await refresh();
  } catch (error) {
    inactiveStatus.textContent = "Could not save inactivity setting";
    inactiveStatus.classList.add("is-error");
    console.error(error);
  }
});

ponsRetentionInput.value = String(ponsRetentionMinutes);
ponsRetentionStatus.textContent = `Saved · removes after ${ponsRetentionMinutes} min`;
ponsRetentionForm.addEventListener("submit", event => {
  event.preventDefault();
  ponsRetentionStatus.classList.remove("is-ok", "is-error");
  const value = Number(ponsRetentionInput.value);
  if (!Number.isInteger(value) || value < MIN_RETENTION_MINUTES || value > MAX_RETENTION_MINUTES) {
    ponsRetentionStatus.textContent = `Enter ${MIN_RETENTION_MINUTES}–${MAX_RETENTION_MINUTES} min`;
    ponsRetentionStatus.classList.add("is-error");
    return;
  }
  ponsRetentionMinutes = value;
  localStorage.setItem(PONS_RETENTION_STORAGE_KEY, String(value));
  ponsRetentionStatus.textContent = `Saved · removes after ${value} min`;
  ponsRetentionStatus.classList.add("is-ok");
  renderPonsGraduations();
});

favAlertsRetentionInput.value = String(favAlertsRetentionMinutes);
favAlertsRetentionStatus.textContent = `Saved · removes after ${favAlertsRetentionMinutes} min`;
favAlertsRetentionForm.addEventListener("submit", event => {
  event.preventDefault();
  favAlertsRetentionStatus.classList.remove("is-ok", "is-error");
  const value = Number(favAlertsRetentionInput.value);
  if (!Number.isInteger(value) || value < MIN_RETENTION_MINUTES || value > MAX_RETENTION_MINUTES) {
    favAlertsRetentionStatus.textContent = `Enter ${MIN_RETENTION_MINUTES}–${MAX_RETENTION_MINUTES} min`;
    favAlertsRetentionStatus.classList.add("is-error");
    return;
  }
  favAlertsRetentionMinutes = value;
  localStorage.setItem(FAV_ALERTS_RETENTION_STORAGE_KEY, String(value));
  favAlertsRetentionStatus.textContent = `Saved · removes after ${value} min`;
  favAlertsRetentionStatus.classList.add("is-ok");
  renderFavoriteAlerts(lastLogData);
});

layoutToggle.addEventListener("change", () => {
  layoutMode = layoutToggle.checked ? "lanes" : "classic";
  localStorage.setItem(LAYOUT_STORAGE_KEY, layoutMode);
  applyLayoutMode();
  render(lastState);
});

chainFilter.addEventListener("change", () => {
  selectedNetwork = chainFilter.value;
  render(lastState);
});

tokenAgeFilter.value = selectedTokenAge;
tokenAgeFilter.addEventListener("change", () => {
  selectedTokenAge = TOKEN_AGE_OPTIONS.has(tokenAgeFilter.value) ? tokenAgeFilter.value : "all";
  tokenAgeFilter.value = selectedTokenAge;
  localStorage.setItem(TOKEN_AGE_STORAGE_KEY, selectedTokenAge);
  render(lastState);
});

for (const control of [trendingSearch, trendingMcMin, trendingMcMax]) {
  control.addEventListener("input", () => renderTrending(lastState));
}
for (const control of [trendingChain, trendingAge, trendingSort]) {
  control.addEventListener("change", () => renderTrending(lastState));
}
trendingClear.addEventListener("click", () => {
  trendingSearch.value = "";
  trendingChain.value = "all";
  trendingMcMin.value = "";
  trendingMcMax.value = "";
  trendingAge.value = "all";
  trendingSort.value = "desc";
  renderTrending(lastState);
  trendingSearch.focus();
});

for (const control of [logSearch, logUsdMin, logUsdMax, logMcMin, logMcMax]) {
  control.addEventListener("input", renderCurrentLogFilters);
}
for (const control of [logSideFilter, logChainFilter, logOutcomeFilter, logTimeFilter]) {
  control.addEventListener("change", renderCurrentLogFilters);
}
logFavoriteFilter.addEventListener("click", () => {
  logFavoriteOnly = !logFavoriteOnly;
  logFavoriteFilter.setAttribute("aria-pressed", String(logFavoriteOnly));
  logFavoriteFilter.classList.toggle("active", logFavoriteOnly);
  renderCurrentLogFilters();
});
logFiltersClear.addEventListener("click", () => {
  logSearch.value = "";
  logSideFilter.value = "all";
  logChainFilter.value = "all";
  logOutcomeFilter.value = "all";
  logTimeFilter.value = "all";
  logFavoriteOnly = false;
  logFavoriteFilter.setAttribute("aria-pressed", "false");
  logFavoriteFilter.classList.remove("active");
  logUsdMin.value = "";
  logUsdMax.value = "";
  logMcMin.value = "";
  logMcMax.value = "";
  renderCurrentLogFilters();
  logSearch.focus();
});

applyLayoutMode();
refresh();
refreshAuthStatus();
tickLiveUi();
setInterval(() => {
  refresh();
  tickLiveUi();
}, 1000);
setInterval(refreshAuthStatus, 15000);

alertsTab.addEventListener("click", () => showView("alerts"));
trendingTab.addEventListener("click", () => showView("trending"));
ponsTab.addEventListener("click", () => showView("pons"));
followingTab.addEventListener("click", () => showView("following"));
watchlistTab.addEventListener("click", () => showView("watchlist"));
balanceTab.addEventListener("click", () => showView("balance"));
logTab.addEventListener("click", () => showView("log"));
favAlertsTab.addEventListener("click", () => showView("favAlerts"));
for (const th of document.querySelectorAll(".following-table th[data-sort]")) { th.addEventListener("click", () => { const key = th.dataset.sort; followingSort = followingSort.key === key ? { key, desc: !followingSort.desc } : { key, desc: key !== "name" }; renderFollowing(); }); }
loadFollowing();
loadWatchlist();
loadBalances();
loadPonsGraduations();
setInterval(loadFollowing, 60_000);
setInterval(loadWatchlist, 60_000);
setInterval(loadBalances, 5_000);
setInterval(loadPonsGraduations, 3_000);
loadLog();
setInterval(loadLog, 2_000);
