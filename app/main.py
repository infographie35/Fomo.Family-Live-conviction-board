import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import INGEST_TOKEN
from .services.auth import auth_manager
from .services.topic import TopicMismatchError, topic_manager
from .services.fomo_ws import run_fomo_listener
from .services.market_data import MarketRefreshScheduler, run_market_cap_refresher
from .services.following import following_manager
from .services.following_refresh import following_refresh_service
from .services.watchlist import watchlist_manager
from .services.balances import balance_manager
from .services.balance_refresh import balance_refresh_service
from .services.ws_event_log import ws_event_log
from .services.runtime_health import runtime_health
from .store import store


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


class CutoffUpdate(BaseModel):
    value: float


class InactiveTokenUpdate(BaseModel):
    hours: float | None = None


class ForgetTokenPayload(BaseModel):
    key: str


class IngestPayload(BaseModel):
    candidates: dict


class TopicPayload(BaseModel):
    topicId: str


class FavoritePayload(BaseModel):
    userId: str


class WatchlistPayload(BaseModel):
    key: str


class BalanceRefreshUpdate(BaseModel):
    seconds: int


class FollowingRefreshUpdate(BaseModel):
    seconds: int


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop_event = asyncio.Event()
    market_refresh_scheduler = MarketRefreshScheduler()
    await ws_event_log.flush()

    async def maintenance_loop():
        # WATCHLIST keeps a last-known card payload on disk so it is populated
        # immediately after restart. Refresh that cache periodically rather than
        # writing on every one-second dashboard poll.
        last_watchlist_sync = 0.0
        loop = asyncio.get_running_loop()
        while not stop_event.is_set():
            await store.cleanup()
            now = loop.time()
            if now - last_watchlist_sync >= 30:
                state = await store.snapshot()
                await watchlist_manager.sync_live(state["tokens"])
                last_watchlist_sync = now
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=1)
            except asyncio.TimeoutError:
                pass

    named_tasks = {
        "fomoListener": asyncio.create_task(
            run_fomo_listener(store, stop_event, market_refresh_scheduler)
        ),
        "marketRefresher": asyncio.create_task(
            run_market_cap_refresher(store, stop_event, market_refresh_scheduler)
        ),
        "maintenance": asyncio.create_task(maintenance_loop()),
        "balanceRefresher": asyncio.create_task(balance_refresh_service.run(stop_event)),
        "followingRefresher": asyncio.create_task(following_refresh_service.run(stop_event)),
    }
    tasks = list(named_tasks.values())
    for name, task in named_tasks.items():
        runtime_health.register_task(name, task)

    app.state.stop_event = stop_event
    app.state.tasks = tasks

    try:
        yield
    finally:
        stop_event.set()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await ws_event_log.close()


app = FastAPI(title="Fomo Alert Dashboard", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def dashboard():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/state")
async def api_state():
    state = await store.snapshot()
    # Membership is small and stable, so include it with live state. The browser
    # can route watched tokens away from ALERTS without an extra request/tick.
    state["watchlistKeys"] = await watchlist_manager.keys()
    state["balanceRefreshSeconds"] = balance_refresh_service.get_interval()
    state["balanceRefreshRemainingSeconds"] = balance_refresh_service.get_remaining_seconds()
    state["followingRefreshSeconds"] = following_refresh_service.get_interval()
    state["followingRefreshRemainingSeconds"] = following_refresh_service.get_remaining_seconds()
    state["favoriteFollowingIds"] = await following_manager.favorite_ids()
    state["health"] = await runtime_health.snapshot()
    return state


@app.get("/api/watchlist")
async def api_watchlist():
    state = await store.snapshot()
    return await watchlist_manager.snapshot(state["tokens"])


@app.post("/api/watchlist/toggle")
async def toggle_watchlist(payload: WatchlistPayload):
    key = payload.key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="key is required")

    state = await store.snapshot()
    live_token = next((token for token in state["tokens"] if token["key"] == key), None)
    try:
        watched = await watchlist_manager.toggle(key, live_token)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Token is no longer available to watch.") from exc

    return {"ok": True, "key": key, "watchlisted": watched, "token": live_token if watched else None}


@app.get("/api/balances")
async def api_balances():
    return await balance_manager.snapshot(topic_manager.resolve())


@app.get("/api/following")
async def api_following():
    return await following_manager.snapshot()


@app.get("/api/log")
async def api_log():
    return await ws_event_log.snapshot()


@app.post("/api/following/favorite")
async def toggle_following_favorite(payload: FavoritePayload):
    if not payload.userId.strip():
        raise HTTPException(status_code=400, detail="userId is required")
    favorite = await following_manager.toggle_favorite(payload.userId.strip())
    return {"ok": True, "userId": payload.userId.strip(), "favorite": favorite}


@app.get("/health")
async def health():
    return await runtime_health.snapshot()


@app.get("/api/settings")
async def api_settings():
    return {
        "firstAlertMcCutoff": await store.get_first_alert_mc_cutoff(),
        "inactiveTokenHours": await store.get_inactive_token_hours(),
        "balanceRefreshSeconds": balance_refresh_service.get_interval(),
        "followingRefreshSeconds": following_refresh_service.get_interval(),
    }


@app.post("/api/settings/first-alert-mc-cutoff")
async def update_first_alert_mc_cutoff(payload: CutoffUpdate):
    try:
        await store.set_first_alert_mc_cutoff(payload.value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "ok": True,
        "firstAlertMcCutoff": await store.get_first_alert_mc_cutoff(),
    }


@app.post("/api/settings/balance-refresh-seconds")
async def update_balance_refresh_seconds(payload: BalanceRefreshUpdate):
    try:
        seconds = balance_refresh_service.set_interval(payload.seconds)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "balanceRefreshSeconds": seconds}


@app.post("/api/settings/following-refresh-seconds")
async def update_following_refresh_seconds(payload: FollowingRefreshUpdate):
    try:
        seconds = following_refresh_service.set_interval(payload.seconds)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "followingRefreshSeconds": seconds}


@app.post("/api/settings/inactive-token-hours")
async def update_inactive_token_hours(payload: InactiveTokenUpdate):
    try:
        await store.set_inactive_token_hours(payload.hours)
        # Apply a newly shortened duration immediately instead of waiting for the
        # next one-second maintenance tick.
        await store.cleanup()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "ok": True,
        "inactiveTokenHours": await store.get_inactive_token_hours(),
    }


@app.post("/api/tokens/forget")
async def forget_token(payload: ForgetTokenPayload):
    if not await store.forget_token(payload.key):
        raise HTTPException(status_code=404, detail="Token is no longer on the dashboard.")
    return {"ok": True}


@app.get("/api/auth/status")
async def auth_status():
    status = await auth_manager.status()
    return {
        "hasCredentials": status.has_credentials,
        "expiresAt": status.expires_at,
        "expiresInSeconds": status.expires_in_seconds,
        "lastRefreshAt": status.last_refresh_at,
        "lastError": status.last_error,
    }


@app.post("/api/auth/ingest")
async def auth_ingest(payload: IngestPayload, request: Request):
    client = request.client.host if request.client else ""
    if client not in ("127.0.0.1", "::1", "localhost"):
        raise HTTPException(status_code=403, detail="localhost only")

    if INGEST_TOKEN and request.headers.get("x-ingest-token", "") != INGEST_TOKEN:
        raise HTTPException(status_code=401, detail="bad ingest token")

    try:
        status = await auth_manager.ingest_credentials(payload.candidates)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "ok": True,
        "hasCredentials": status.has_credentials,
        "expiresInSeconds": status.expires_in_seconds,
    }


@app.post("/api/topic/ingest")
async def topic_ingest(payload: TopicPayload, request: Request):
    client = request.client.host if request.client else ""
    if client not in ("127.0.0.1", "::1", "localhost"):
        raise HTTPException(status_code=403, detail="localhost only")
    if INGEST_TOKEN and request.headers.get("x-ingest-token", "") != INGEST_TOKEN:
        raise HTTPException(status_code=401, detail="bad ingest token")
    had_topic = topic_manager.resolve() is not None
    try:
        topic_id = topic_manager.ingest(payload.topicId)
    except TopicMismatchError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not had_topic:
        # First safe account binding: do not wait for the normal 30s/60s
        # cadences before populating account-scoped BALANCE and FOLLOWING.
        balance_refresh_service.request_refresh()
        following_refresh_service.request_refresh()

    return {"ok": True, "topicId": topic_id}
