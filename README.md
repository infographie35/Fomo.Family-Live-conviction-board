# Fomo.Family-Live-conviction-board
How it should be - Real-time Fomo.Family conviction dashboard with live alerts, trending tokens, shared market data, DexScreener enrichment, watchlists, favorites and advanced filtering.



# Fomo Alert Dashboard

Local real-time dashboard for Fomo.Family trading activity, trending tokens, balances, following, favorites and market data.

## Main features

- Live BUY/SELL alerts from Fomo `trading_activity`
- TRENDING board from Fomo `trending_tokens`
- Shared token state across ALERTS and TRENDING
- DexScreener enrichment for token age, pair selection and market data
- Watchlist, Following, Balance and Favorite Alerts
- Persistent WS session log with combinable filters
- Configurable buyer lanes and token-age filters
- Dark UI with consistent blockchain color coding
- One-click contract copy and direct Fomo token links

## How tracking works

- One trader counts once per token.
- Repeated BUYs from the same trader update the reconstructed position without increasing the unique-buyer count.
- Partial SELLs reduce the reconstructed position and show `% LEFT`.
- A position is considered closed when only dust remains.
- Closed traders remain visible briefly as `SOLD`.
- Tokens move automatically between the configured buyer-count columns.
- The first accepted Fomo BUY market cap is kept as the reference for performance.
- Every accepted BUY/SELL immediately updates `MC NOW`; DexScreener refreshes in the background.
- `FIRST ALERT MC CUTOFF` is applied only to the first usable Fomo BUY for ALERTS.
- `FORGET` removes a token from ALERTS for the current process without removing its independent TRENDING membership.

## TRENDING

TRENDING uses Fomo's `trending_tokens` feed on the same authenticated WebSocket connection as ALERTS.

Cards use Fomo's live market cap for display and sorting. DexScreener is reused only for shared enrichment such as token age and pair metadata.

Available filters:

- Search by ticker, name or contract
- Blockchain
- Market cap min/max
- Token age
- Market cap ascending/descending

ALERTS and TRENDING share the same token and Dex market state, so a token known in both views is not enriched twice.

## Market data

DexScreener requests are grouped by blockchain and batched up to 30 token addresses per request.

The dashboard uses one shared Dex request governor:

- Maximum 120 requests/minute
- Minimum 500 ms between requests
- Global backoff on HTTP 429
- `Retry-After` is honored when available

Pair selection requires the tracked token to be the base token on the correct blockchain.

When a coherent direct USD/stable pool exists, it is preferred over stock-token or ETH quote pools. Supported stable quotes include:

`USDC`, `USDT`, `USDG`, `USDS`, `DAI`, `PYUSD`, `FDUSD`, `USDE`

Fresh Fomo market-cap evidence is used to validate provisional pair selection. Once the same pair is confirmed on successive Fomo-guided discoveries, it is locked until DexScreener stops returning that pair.

TRENDING-only tokens are enriched once for token age and do not become a second periodic Dex refresh board.

## Fomo WebSocket

The dashboard uses one authenticated Fomo WebSocket connection with multiple topics:

- `trading_activity` — live BUY/SELL activity
- `trending_tokens` — TRENDING board
- `prices` — optional extra price evidence for active ALERTS tokens

`prices` subscriptions are deduplicated and intentionally limited. If Fomo rejects a price subscription because too many topics are active, ALERTS and TRENDING remain connected and new price-topic subscriptions stop for that WebSocket session.

## LOG

The LOG tab keeps raw Fomo BUY/SELL events for the current dashboard session.

Filters can be combined:

- Search trader/token
- BUY / SELL
- Blockchain
- Favorite only
- Accepted / Ignored
- Recent time window
- USD min/max
- Market cap min/max

Filtering is display-only and never suppresses incoming events.

## Following, Balance and Favorites

FOLLOWING and BALANCE are refreshed directly by Python using the authenticated Fomo JWT and the captured account ID.

Favorites are local and persistent. Favorite traders are highlighted in the dashboard and their accepted BUYs also appear in `★ FAV ALERTS`.

Balance snapshots are tied to the captured account ID so data from another viewed Fomo profile cannot be mistaken for the logged-in account.

## Install

From the project folder:

```bat
python -m pip install -r requirements.txt
```

## Chrome Bridge

The `chrome_bridge/` extension has two responsibilities only:

1. Mirror the current Fomo access JWT to the local dashboard.
2. Capture the logged-in account `topicId` from Fomo's outgoing `trading_activity` WebSocket subscription.

It does not fetch Balance, Following, TRENDING or market data.

Install once:

1. Open `chrome://extensions`
2. Enable **Developer mode**
3. Click **Load unpacked**
4. Select the `chrome_bridge/` folder
5. Keep a logged-in Fomo tab open

Close DevTools on the Fomo tab while the bridge is active because Chrome does not allow both debuggers to attach at the same time.

If `fomo_topic.json` does not exist, refresh the Fomo tab once after starting the dashboard so the account topic can be captured.

To intentionally switch Fomo accounts:

1. Stop the dashboard.
2. Delete `fomo_topic.json`.
3. Restart the dashboard.
4. Refresh Fomo once.

## Run

Make sure you are logged in to Fomo.Family and keep a Fomo tab open in Chrome.


Then start the dashboard:

```bat
python run.py
```

Open:

```text
http://127.0.0.1:8002
```

## Security and runtime files

This dashboard is intended to run locally.

`jwt.json` contains a live Fomo session credential and must not be committed or shared.

Runtime-generated JSON files such as JWT, account binding, balances, watchlist, favorites, settings and WS session logs are excluded from Git.

## Health

`/health` and `/api/state` expose the health of the Fomo feed and background tasks.

The dashboard shows `DEGRADED` instead of `LIVE` when the local HTTP server is reachable but the live feed is unhealthy.
