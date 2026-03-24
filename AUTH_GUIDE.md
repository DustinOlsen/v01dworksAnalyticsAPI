# Authentication Guide

This API supports optional Ed25519 key-based authentication, configured per `site_id`.

- A site with **no registered key** is fully public — anyone can read its stats.
- Once a public key is registered for a `site_id`, all analytics read endpoints (`/stats`, `/page-stats`, `/forecast`, `/summary`, `/anomalies`, `/bots`, `/bot-stats`) for that site require a valid signed request.
- Auth is **not** required for write endpoints (`/track`, `/click`).

---

## How it Works

1. You hold an Ed25519 **private key** (never leaves your client).
2. You register the corresponding **public key** with the API once.
3. For every authenticated request you add two HTTP headers:
   - `X-Timestamp` — current Unix timestamp (integer, as a string header value)
   - `X-Signature` — `hex( Ed25519Sign(private_key, "{site_id}:{timestamp}") )`
4. The server verifies the signature. Requests where the timestamp differs from server time by more than **300 seconds** are rejected.

All auth failures return the same generic body (no information leaked):
```json
HTTP 401
{ "detail": "Unauthorized" }
```

---

## Setup Methods

### Method A — Browser Pairing (QR Code)

Navigate to `http://localhost:8011/pair/<your-site-id>` in a browser.

The server will:
1. Generate a new Ed25519 key pair.
2. Store the public key in the site's database.
3. Display an HTML page with a QR code.

The QR code encodes a JSON payload:
```json
{
  "base_url": "http://192.168.1.5:8011",
  "site_id": "my-secure-site",
  "private_key": "<64-char hex — keep this secret>"
}
```

Scan with the iOS companion app to configure it instantly. **Close the browser tab after scanning** — the page contains your raw private key.

To replace an existing key, add `?force=true`. This requires valid auth headers (`X-Timestamp` + `X-Signature`) to prove you hold the current private key.

### Method B — Manual / Programmatic Setup

1. Generate a key pair on your client (example below).
2. Register the public key via `POST /register-key`.
3. Sign every subsequent analytics request with the private key.

---

## Step 1 — Generate a Key Pair

```python
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

# Generate private key
private_key = Ed25519PrivateKey.generate()

# Derive public key
public_key = private_key.public_key()

# Hex-encode both (raw bytes, no PEM wrapping)
private_hex = private_key.private_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PrivateFormat.Raw,
    encryption_algorithm=serialization.NoEncryption()
).hex()

public_hex = public_key.public_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PublicFormat.Raw
).hex()

print(f"Private Key (keep secret): {private_hex}")
print(f"Public Key  (register this): {public_hex}")
```

> Save `private_hex` securely (environment variable, secret manager, etc.). You cannot recover it from the API.

---

## Step 2 — Register the Public Key

```python
import requests

requests.post("http://localhost:8011/register-key", json={
    "site_id": "my-secure-site",
    "public_key_hex": public_hex
}).raise_for_status()
```

This is a **one-time operation**. The endpoint returns `HTTP 400` if a key is already registered for the site.

---

## Step 3 — Sign Requests

```python
import time
import requests
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

BASE_URL       = "http://localhost:8011"
SITE_ID        = "my-secure-site"
PRIVATE_KEY_HEX = "..."  # your saved private_hex from Step 1

def auth_headers(site_id: str, private_key_hex: str) -> dict:
    """Returns X-Timestamp and X-Signature headers for one request."""
    private_key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_key_hex))
    timestamp   = int(time.time())
    message     = f"{site_id}:{timestamp}".encode()
    signature   = private_key.sign(message).hex()
    return {
        "X-Timestamp": str(timestamp),
        "X-Signature": signature
    }

# Fetch stats
response = requests.get(
    f"{BASE_URL}/stats",
    params={"site_id": SITE_ID},
    headers=auth_headers(SITE_ID, PRIVATE_KEY_HEX)
)
print(response.json())

# Fetch forecast (7 days)
response = requests.get(
    f"{BASE_URL}/forecast",
    params={"site_id": SITE_ID, "days": 7},
    headers=auth_headers(SITE_ID, PRIVATE_KEY_HEX)
)
print(response.json())
```

> `auth_headers()` must be called fresh for **each request** — the timestamp changes and a stale one will be rejected after 5 minutes.

---

## Key Rotation

To replace an existing key, call `/pair/{site_id}?force=true` with valid auth headers for the **current** key. The server verifies the existing key before deleting it and generating a new pair.

There is no programmatic key rotation endpoint — use the `/pair?force=true` browser flow or delete the site's `.db` file to start fresh.
