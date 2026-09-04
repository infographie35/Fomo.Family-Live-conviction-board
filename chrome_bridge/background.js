// Fomo Browser Bridge v14.1 — DevTools-protocol capture for JWT and account topicId.
//
// Python owns BALANCE and FOLLOWING refreshes. This extension has only two data
// responsibilities: mirror the browser-authenticated JWT and bind the account
// topicId observed in Fomo's trading_activity WebSocket subscription.

const BASE = "http://127.0.0.1:8002";
const INGEST_TOKEN = "fomo-local-bridge"; // must match INGEST_TOKEN in app/config.py
const PROTOCOL = "1.3";
const FOMO_PRIVY_APP_ID = "cm6h485o300n3zj9yl6vpedq7";

const attached = new Set();
const sessionReqs = new Map();
let lastJwtPosted = null;
let pendingJwtPosted = null;

function log() {
  try { console.log.apply(console, ["[fomo-bridge]"].concat([].slice.call(arguments))); }
  catch (e) {}
}
function isFomoUrl(url) {
  try {
    var hostname = new URL(url).hostname.toLowerCase();
    return hostname === "fomo.family" || hostname.endsWith(".fomo.family");
  } catch (e) { return false; }
}
function decodeJwtClaims(jwt) {
  try {
    var parts = jwt.split(".");
    if (parts.length !== 3) return null;
    var payload = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    while (payload.length % 4) payload += "=";
    return JSON.parse(atob(payload));
  } catch (e) {
    return null;
  }
}

function fomoJwtsIn(text) {
  if (typeof text !== "string") return [];
  var matches = text.match(/eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+/g) || [];

  // Session responses can contain multiple JWT-like values. Mirror only the
  // same Fomo user-session class accepted by Python so unrelated tokens never
  // generate noisy /api/auth/ingest 400 responses.
  return matches.filter(function (jwt) {
    var claims = decodeJwtClaims(jwt);
    return claims && claims.aud === FOMO_PRIVY_APP_ID && claims.att !== "pat";
  });
}
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function post(path, body, label) {
  return fetch(BASE + path, {
    method: "POST",
    headers: { "content-type": "application/json", "x-ingest-token": INGEST_TOKEN },
    body: JSON.stringify(body),
  })
    .then(function (response) {
      log(label, "status", response.status);
      return response.ok;
    })
    .catch(function (error) {
      log(label, "failed", String(error));
      return false;
    });
}

function postJwts(jwts, source) {
  if (!jwts.length) return;
  var key = jwts.join("|");
  if (key === lastJwtPosted || key === pendingJwtPosted) return;

  var candidates = {};
  jwts.forEach(function (jwt, index) { candidates["debugger:" + source + ":" + index] = jwt; });
  pendingJwtPosted = key;
  post("/api/auth/ingest", { candidates: candidates }, "auth ingest (" + source + ")")
    .then(function (ok) {
      if (pendingJwtPosted === key) pendingJwtPosted = null;
      if (ok) lastJwtPosted = key;
    });
}

function postTopic(topicId) {
  if (!topicId) return;

  // A Fomo page refresh emits a fresh trading_activity subscription. Forward
  // every such frame: the Python process may have restarted while this service
  // worker stayed alive, so browser-side topic deduplication would prevent a
  // missing fomo_topic.json from being recreated. Python owns the process-wide
  // account lock and decides whether this topic matches the current account.
  log("trading_activity topicId captured:", topicId);
  post("/api/topic/ingest", { topicId: topicId }, "topic ingest");
}

function handleSentFrame(payload) {
  if (typeof payload !== "string") return;
  if (payload.indexOf("eyJ") !== -1) postJwts(fomoJwtsIn(payload), "ws");

  if (payload.indexOf("subscribe") === -1 || payload.indexOf("trading_activity") === -1) return;
  try {
    var message = JSON.parse(payload);
    if (
      message && message.type === "subscribe" &&
      message.topicType === "trading_activity" && UUID_RE.test(message.topicId || "")
    ) {
      postTopic(message.topicId);
    }
  } catch (e) {}
}

async function attach(tabId) {
  if (attached.has(tabId)) return;
  try {
    await chrome.debugger.attach({ tabId }, PROTOCOL);
    try {
      await chrome.debugger.sendCommand({ tabId }, "Network.enable");
    } catch (enableError) {
      try { await chrome.debugger.detach({ tabId }); } catch (detachError) {}
      throw enableError;
    }
    attached.add(tabId);
    log("attached + Network.enable on tab", tabId);
  } catch (e) {
    var msg = String((e && e.message) || e);
    if (msg.indexOf("Another debugger") !== -1 || msg.indexOf("Cannot access") !== -1) {
      log("ATTACH BLOCKED on tab", tabId, "— close DevTools on the Fomo tab, then reload the extension");
    } else {
      log("attach failed on tab", tabId, msg);
    }
  }
}

async function ensureAttached() {
  try {
    var tabs = await chrome.tabs.query({ url: ["https://fomo.family/*", "https://*.fomo.family/*"] });
    for (const tab of tabs) if (tab.id != null) await attach(tab.id);
  } catch (e) { log("tabs.query failed", String(e)); }
}

chrome.debugger.onEvent.addListener(async (source, method, params) => {
  const tabId = source.tabId;

  if (method === "Network.webSocketFrameSent") {
    handleSentFrame(params && params.response && params.response.payloadData);
    return;
  }

  if (method === "Network.responseReceived") {
    var url = (params && params.response && params.response.url) || "";
    if (url.indexOf("/api/v1/sessions") !== -1 && params.requestId) {
      if (!sessionReqs.has(tabId)) sessionReqs.set(tabId, new Set());
      sessionReqs.get(tabId).add(params.requestId);
    }
    return;
  }

  if (method === "Network.loadingFinished") {
    var sessions = sessionReqs.get(tabId);
    if (sessions && sessions.has(params.requestId)) {
      sessions.delete(params.requestId);
      try {
        var sessionRes = await chrome.debugger.sendCommand(
          { tabId }, "Network.getResponseBody", { requestId: params.requestId }
        );
        if (sessionRes) {
          var sessionBody = sessionRes.base64Encoded ? atob(sessionRes.body) : sessionRes.body;
          postJwts(fomoJwtsIn(sessionBody), "sessions");
        }
      } catch (e) {}
    }
  }

  if (method === "Network.loadingFailed") {
    var failedSessions = sessionReqs.get(tabId);
    if (failedSessions) failedSessions.delete(params.requestId);
  }
});

chrome.debugger.onDetach.addListener((source) => {
  if (source.tabId != null) {
    attached.delete(source.tabId);
    sessionReqs.delete(source.tabId);
  }
});
chrome.tabs.onUpdated.addListener((tabId, info, tab) => {
  if (info.status === "loading" && tab && isFomoUrl(tab.url || "")) attach(tabId);
});
chrome.tabs.onRemoved.addListener((tabId) => {
  attached.delete(tabId);
  sessionReqs.delete(tabId);
});
chrome.runtime.onStartup.addListener(ensureAttached);
chrome.runtime.onInstalled.addListener(ensureAttached);
chrome.alarms.create("ensure", { periodInMinutes: 1 });
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "ensure") ensureAttached();
});
ensureAttached();
