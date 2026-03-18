# API Documentation

**Privacy Visitor Tracker API** — lightweight, privacy-respecting analytics with optional Ed25519 authentication.

- **Default base URL**: `http://localhost:8011`
- **Framework**: FastAPI (Python 3.11)
- **Storage**: SQLite (one `.db` file per `site_id` under `data/`)
- **Interactive docs**: `/docs` (Swagger UI) · `/redoc` (ReDoc)

---

## Table of Contents

1. [Setup & Environment Variables](#setup--environment-variables)
2. [Multi-Site Support](#multi-site-support)
3. [Authentication](#authentication)
4. [Rate Limiting & Request Constraints](#rate-limiting--request-constraints)
5. [Endpoints](#endpoints)
   - [GET /](#1-get--health-check)
   - [GET /sites](#2-get-sites)
   - [POST /register-key](#3-post-register-key)
   - [GET /pair/{site_id}](#4-get-pairsite_id)
   - [POST /track](#5-post-track)
   - [POST /click](#6-post-click)
   - [GET /stats 🔒](#7-get-stats-)
   - [GET /forecast 🔒](#8-get-forecast-)
   - [GET /summary 🔒](#9-get-summary-)
   - [GET /anomalies 🔒](#10-get-anomalies-)
   - [GET /bots 🔒](#11-get-bots-)
   - [GET /debug/auth-status/{site_id}](#12-get-debugauth-statussite_id)
6. [Field Value Reference](#field-value-reference)
7. [Error Response Reference](#error-response-reference)
8. [Complete Integration Examples](#complete-integration-examples)

---

## Setup & Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ALLOWED_ORIGINS` | `http://localhost:3000,http://localhost:8011` | Comma-separated list of allowed CORS origins. **Set this to your production domain(s).** |
| `ENABLE_DEBUG_ENDPOINTS` | `false` | Set to `true` to expose `/debug/auth-status/{site_id}`. Do not enable in production. |

**GeoLite2 database** — country lookups require a MaxMind GeoLite2 database file placed in the **project root**. The API checks for these filenames in order:
1. `GeoLite2-Country.mmdb`
2. `GeoLite2-City.mmdb`

If neither is present, country resolves to `"Unknown"` (the API still works for all other tracking).

**Data directory** — SQLite databases and the IP-hashing salt are stored in `data/`. This directory is created automatically on first run.

---

## Multi-Site Support

Every endpoint that writes or reads analytics data accepts an optional `site_id` parameter. Each site gets its own isolated SQLite database (`data/{site_id}.db`). Auth keys are also per-site.

**`site_id` format**: alphanumeric characters, hyphens `-`, underscores `_`, and dots `.` (suitable for domain names). Any other characters are stripped. If the result is empty, `"default"` is used. Defaults to `"default"` when omitted.

---

## Authentication

Auth is **optional and per-site**. A site with no registered public key is fully public. Once a public key is registered for a `site_id`, all 🔒 endpoints for that site require a valid signed request.

### How it works

1. You hold an **Ed25519 key pair** (private key stays on your client; public key is registered with the API).
2. For each authenticated request, attach two headers:

| Header | Type | Description |
|--------|------|-------------|
| `X-Timestamp` | Integer (as string) | Current Unix timestamp in seconds |
| `X-Signature` | Hex string | `Ed25519Sign(private_key, "{site_id}:{timestamp}")` — result hex-encoded |

3. The server looks up the public key for the requested `site_id`, verifies the signature, and rejects requests where the timestamp is more than **300 seconds** (5 minutes) from server time.

### Auth setup methods

**Method A — Browser pairing (recommended for iOS app):**  
Visit `http://localhost:8011/pair/{site_id}` in a browser. The server generates a key pair, stores the public key, and shows a QR code containing the private key and API URL.

**Method B — Manual / programmatic:**  
Generate a key pair client-side → POST the public key to `/register-key` → sign subsequent requests with the private key. See [AUTH_GUIDE.md](AUTH_GUIDE.md) for a full Python example.

### Auth error responses

All authentication failures return the same generic body to avoid leaking information:

```json
HTTP 401
{ "detail": "Unauthorized" }
```

---

## Rate Limiting & Request Constraints

| Constraint | Value |
|-----------|-------|
| `/track` rate limit | 60 requests / minute / IP |
| Max request body | 64 KB |

Exceeding the rate limit → `HTTP 429`  
Body exceeding the size limit → `HTTP 413`

---

## Endpoints

---

### 1. GET /  — Health Check

Confirms the API is running.

```
GET /
```

**Response `200`**
```json
{ "message": "Privacy Visitor Tracker API is running" }
```

---

### 2. GET /sites

Lists every site that has a database on disk, along with whether auth is required.

```
GET /sites
```

**Response `200`**
```json
{
  "sites": [
    { "id": "default",  "requiresAuth": false },
    { "id": "my-blog",  "requiresAuth": true  }
  ]
}
```

---

### 3. POST /register-key

Registers a client-generated public key for a site. One-time operation — the site becomes auth-locked after this call.

```
POST /register-key
Content-Type: application/json
```

**Request body**
```json
{
  "site_id": "my-site",
  "public_key_hex": "<64-char hex string — raw Ed25519 public key bytes>"
}
```

**Response `200`** — key registered
```json
{ "status": "ok", "message": "Public key registered" }
```

**Response `400`** — key already exists for this site
```json
{ "detail": "Public key already registered for this site" }
```

---

### 4. GET /pair/{site_id}

Server-side key generation. Returns an HTML page with a QR code containing the private key. Intended for browser use with the iOS companion app.

```
GET /pair/{site_id}
GET /pair/{site_id}?force=true   (requires auth headers if key already registered)
```

**Path parameter**
- `site_id` — site to pair

**Query parameter**
- `force` (bool, default `false`) — overwrite an existing key. If a key is already registered, `force=true` **requires** valid `X-Timestamp` + `X-Signature` headers to prove you hold the existing private key.

**Response `200`** — HTML page. The QR code encodes a JSON payload:
```json
{
  "base_url": "http://192.168.1.5:8011",
  "site_id": "my-site",
  "private_key": "<64-char hex — keep secret>"
}
```

**Response `403`** — key already registered and `force=false`  
**Response `401`** — `force=true` but auth headers are missing or invalid

> **Security note**: The QR page contains the raw private key. Close the browser tab after scanning.

---

### 5. POST /track

Records a page visit. Call this from your frontend on every page load. The IP is hashed immediately after use and never stored in plaintext.

```
POST /track
Content-Type: application/json
```

**Request body** (all fields optional)
```json
{
  "path": "/articles/my-post",
  "site_id": "my-media-site"
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `path` | string | `"/"` | Current page path |
| `site_id` | string | `"default"` | Site to record the visit under |

**Headers used automatically** (sent by the browser, no action needed):
- `User-Agent` — used for device / browser / OS classification
- `Referer` — used for referrer category classification
- `X-Forwarded-For` — used for IP resolution behind a proxy (first IP validated)

**Response `200`**
```json
{
  "status": "ok",
  "country": "US",
  "unique": true,
  "unique_today": true,
  "page": "/articles/my-post",
  "ua_info": {
    "device": "Desktop",
    "browser": "Chrome",
    "os": "Mac OS X"
  },
  "referrer": "Search Engine"
}
```

| Field | Description |
|-------|-------------|
| `unique` | `true` if this is the first ever visit from this hashed IP for this site |
| `unique_today` | `true` if this IP has not visited today (UTC) |
| `country` | ISO 3166-1 alpha-2 code, or `"Unknown"` if GeoLite2 DB is absent |
| `ua_info.device` | See [Device Types](#device-types) |
| `ua_info.browser` | Browser family string (e.g., `"Chrome"`, `"Mobile Safari"`) |
| `ua_info.os` | OS family string (e.g., `"Windows"`, `"iOS"`, `"Android"`) |
| `referrer` | See [Referrer Categories](#referrer-categories) |

**Response `429`** — rate limit exceeded  
**Response `413`** — body exceeds 64 KB

**JavaScript example**
```javascript
fetch('https://your-api.example.com/track', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    path: window.location.pathname,
    site_id: 'my-media-site'
  })
});
```

---

### 6. POST /click

Records a click on an outgoing external link.

```
POST /click
Content-Type: application/json
```

**Request body**
```json
{
  "url": "https://twitter.com/myprofile",
  "site_id": "my-media-site"
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `url` | string | required | Full URL of the outgoing link |
| `site_id` | string | `"default"` | Site to record the click under |

**Response `200`**
```json
{ "status": "ok", "url": "https://twitter.com/myprofile" }
```

**JavaScript example**
```javascript
document.querySelectorAll('a[href^="http"]').forEach(link => {
  link.addEventListener('click', () => {
    fetch('https://your-api.example.com/click', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: link.href, site_id: 'my-media-site' })
    });
  });
});
```

---

### 7. GET /stats 🔒

Returns all aggregated analytics for a site. History covers the **last 30 days**.

```
GET /stats?site_id=my-media-site
```

**Auth**: Required if a public key is registered for the site.

**Query parameters**

| Param | Default | Description |
|-------|---------|-------------|
| `site_id` | `"default"` | Site to fetch stats for |

**Response `200`**
```json
{
  "total_visits": 4820,
  "unique_visitors": 1340,
  "history": [
    { "date": "2026-03-18", "total_visits": 210, "unique_visitors": 88 },
    { "date": "2026-03-17", "total_visits": 195, "unique_visitors": 74 }
  ],
  "countries": { "US": 2100, "CA": 430, "GB": 210 },
  "pages":     { "/": 1200, "/articles/my-post": 840 },
  "devices":   { "Desktop": 2900, "Mobile": 1600, "Bot": 120 },
  "browsers":  { "Chrome": 2400, "Safari": 900 },
  "os":        { "Windows": 1800, "Mac OS X": 900, "iOS": 700 },
  "referrers": { "Search Engine": 1900, "Direct": 1100, "Social Media": 600 },
  "links":     { "https://github.com/myrepo": 42 }
}
```

**cURL example (unauthenticated site)**
```bash
curl "http://localhost:8011/stats?site_id=my-media-site"
```

**cURL example (authenticated site)**
```bash
TIMESTAMP=$(date +%s)
SITE_ID="my-media-site"
# Generate signature — see AUTH_GUIDE.md for the full Python helper
SIG=$(python3 sign.py "$SITE_ID" "$TIMESTAMP")

curl -H "X-Timestamp: $TIMESTAMP" \
     -H "X-Signature: $SIG" \
     "http://localhost:8011/stats?site_id=$SITE_ID"
```

---

### 8. GET /forecast 🔒

Predicts future daily visit counts using Linear Regression on historical data.

```
GET /forecast?site_id=my-media-site&days=14
```

**Auth**: Required if a public key is registered for the site.

**Query parameters**

| Param | Type | Default | Constraints | Description |
|-------|------|---------|-------------|-------------|
| `site_id` | string | `"default"` | — | Site to forecast |
| `days` | integer | `7` | 1 – 90 | Number of future days to predict |

**Response `200`** — sufficient data (≥ 3 days of history)
```json
{
  "can_forecast": true,
  "forecast": [
    { "date": "2026-03-19", "predicted_visits": 215 },
    { "date": "2026-03-20", "predicted_visits": 222 }
  ],
  "trend": "increasing",
  "slope": 7.3
}
```

**Response `200`** — insufficient data (< 3 days)
```json
{
  "can_forecast": false,
  "message": "Not enough data. Need at least 3 days of history."
}
```

| Field | Description |
|-------|-------------|
| `trend` | `"increasing"` / `"decreasing"` / `"stable"` (stable = slope between -0.5 and 0.5) |
| `slope` | Daily visit change rate (visits/day) |

---

### 9. GET /summary 🔒

Returns statistical summaries and week-over-week growth metrics.

```
GET /summary?site_id=my-media-site
```

**Auth**: Required if a public key is registered for the site.

**Query parameters**

| Param | Default | Description |
|-------|---------|-------------|
| `site_id` | `"default"` | Site to summarise |

**Response `200`** — data available
```json
{
  "average_daily_visits": 185.4,
  "average_daily_unique": 72.1,
  "busiest_day_of_week": "Wednesday",
  "weekly_growth": {
    "current_week_visits": 1340,
    "previous_week_visits": 1105,
    "growth_rate_percent": 21.3
  }
}
```

> `weekly_growth` requires ≥ 14 days of data; otherwise all three fields are `0`.

**Response `200`** — no data
```json
{ "error": "No data available" }
```

---

### 10. GET /anomalies 🔒

Detects unusual daily traffic patterns (spikes or dips) using Isolation Forest.

```
GET /anomalies?site_id=my-media-site
```

**Auth**: Required if a public key is registered for the site.

**Query parameters**

| Param | Default | Description |
|-------|---------|-------------|
| `site_id` | `"default"` | Site to analyse |

**Response `200`** — anomalies found
```json
{
  "has_anomalies": true,
  "anomalies": [
    { "date": "2026-03-10", "visits": 1840, "type": "spike" },
    { "date": "2026-02-28", "visits": 12,   "type": "dip"   }
  ]
}
```

**Response `200`** — insufficient data (< 5 days)
```json
{
  "has_anomalies": false,
  "message": "Not enough data. Need at least 5 days of history."
}
```

| Field | Description |
|-------|-------------|
| `type` | `"spike"` (above mean) or `"dip"` (below mean) |

---

### 11. GET /bots 🔒

Identifies suspected bot visitors using Isolation Forest on request count, request rate, and user-agent score.

```
GET /bots?site_id=my-media-site
```

**Auth**: Required if a public key is registered for the site.

**Query parameters**

| Param | Default | Description |
|-------|---------|-------------|
| `site_id` | `"default"` | Site to analyse |

**Response `200`** — analysis complete
```json
{
  "detected_bots_count": 2,
  "bots": [
    {
      "ip_hash": "a3f9c2...",
      "request_count": 840,
      "reason": "High Request Volume, Abnormal Request Rate"
    }
  ]
}
```

**Response `200`** — insufficient data (< 10 unique visitors tracked)
```json
{ "message": "Not enough data for bot detection (need > 10 visitors)" }
```

| `reason` value | Meaning |
|---------------|----------|
| `"High Request Volume"` | `request_count > 2× site average` |
| `"Abnormal Request Rate"` | requests/second `> 2× site average` |
| `"Suspicious User Agent"` | `ua_score > 0.8` (unknown or bot UA) |
| `"Unusual Pattern"` | Flagged by ML but no specific heuristic matched |

---

### 12. GET /debug/auth-status/{site_id}

Returns whether a public key is registered for the given site.

> **Only available when `ENABLE_DEBUG_ENDPOINTS=true`.** Returns `HTTP 404` otherwise.

```
GET /debug/auth-status/my-media-site
```

**Response `200`**
```json
{
  "site_id": "my-media-site",
  "is_locked": true
}
```

**Response `404`** — debug endpoints disabled (default)

---

## Field Value Reference

### Device Types

| Value | Description |
|-------|-------------|
| `"Desktop"` | Non-mobile PC |
| `"Mobile"` | Smartphone |
| `"Tablet"` | Tablet device |
| `"Bot"` | Identified crawler/bot by user-agent |
| `"Other"` | Unclassified |
| `"Unknown"` | Empty or absent User-Agent header |

### Referrer Categories

| Value | Description |
|-------|-------------|
| `"Direct"` | No Referer header (typed URL, bookmark) |
| `"Search Engine"` | Google, Bing, Yahoo, DuckDuckGo, Baidu, Yandex, etc. |
| `"Social Media"` | Facebook, Twitter/X, Instagram, LinkedIn, Reddit, TikTok, YouTube, Pinterest, WhatsApp |
| `"Other"` | Any other referring domain |
| `"Unknown"` | Referer header present but unparseable |

---

## Error Response Reference

All error responses use FastAPI's standard shape:
```json
{ "detail": "<message>" }
```

| Status | When |
|--------|------|
| `400` | Bad request — e.g. key already registered |
| `401` | Unauthorized — missing, expired, or invalid auth headers |
| `403` | Forbidden — e.g. `/pair` called without `force=true` when key exists |
| `404` | Not found — debug endpoint disabled, or unknown path |
| `413` | Request body exceeds 64 KB |
| `422` | Validation error — request body has wrong types or missing required fields |
| `429` | Rate limit exceeded (`/track`: 60 req/min/IP) |
| `500` | Internal server error |

Validation errors (`422`) include detail about which field failed:
```json
{
  "detail": [
    {
      "loc": ["body", "url"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

## Complete Integration Examples

### Minimal frontend (no auth)

```html
<script>
// Called on every page load
fetch('https://your-api.example.com/track', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    path: window.location.pathname,
    site_id: 'my-media-site'
  })
});

// Outgoing link tracking
document.querySelectorAll('a[href^="http"]').forEach(a => {
  a.addEventListener('click', () => {
    fetch('https://your-api.example.com/click', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: a.href, site_id: 'my-media-site' })
    });
  });
});
</script>
```

### Python — full authenticated client

```python
import time
import requests
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

BASE_URL = "http://localhost:8011"
SITE_ID  = "my-media-site"

# --- Step 1: generate key pair (run ONCE, then save private_hex securely) ---
private_key = Ed25519PrivateKey.generate()
private_hex = private_key.private_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PrivateFormat.Raw,
    encryption_algorithm=serialization.NoEncryption()
).hex()
public_hex = private_key.public_key().public_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PublicFormat.Raw
).hex()

# --- Step 2: register the public key (run ONCE) ---
resp = requests.post(f"{BASE_URL}/register-key", json={
    "site_id": SITE_ID,
    "public_key_hex": public_hex
})
resp.raise_for_status()
print("Registered:", resp.json())

# --- Step 3: build a signed request ---
def auth_headers(site_id: str, private_key_hex: str) -> dict:
    pk = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_key_hex))
    ts = int(time.time())
    sig = pk.sign(f"{site_id}:{ts}".encode()).hex()
    return {"X-Timestamp": str(ts), "X-Signature": sig}

# --- Step 4: fetch stats ---
headers = auth_headers(SITE_ID, private_hex)
stats = requests.get(
    f"{BASE_URL}/stats",
    params={"site_id": SITE_ID},
    headers=headers
).json()
print(stats["total_visits"], "total visits")

# --- Step 5: fetch forecast ---
forecast = requests.get(
    f"{BASE_URL}/forecast",
    params={"site_id": SITE_ID, "days": 7},
    headers=auth_headers(SITE_ID, private_hex)
).json()
if forecast["can_forecast"]:
    for day in forecast["forecast"]:
        print(day["date"], "→", day["predicted_visits"], "predicted visits")
```

### JavaScript — authenticated fetch helper

```javascript
// Requires the `@noble/ed25519` or equivalent WebCrypto-based library
async function signedHeaders(siteId, privateKeyHex) {
  const timestamp = Math.floor(Date.now() / 1000);
  const message   = new TextEncoder().encode(`${siteId}:${timestamp}`);
  // ... sign with your Ed25519 library of choice ...
  const signature = await ed25519.sign(message, privateKeyHex);
  return {
    'X-Timestamp': String(timestamp),
    'X-Signature': Buffer.from(signature).toString('hex')
  };
}

const headers = await signedHeaders('my-media-site', PRIVATE_KEY_HEX);
const stats = await fetch(
  'https://your-api.example.com/stats?site_id=my-media-site',
  { headers }
).then(r => r.json());
```

---

*For full authentication setup details see [AUTH_GUIDE.md](AUTH_GUIDE.md).*

