# API Documentation

Base URL: `http://localhost:8011` (default)

## Authentication

This API supports optional key-based Ed25519 authentication per site. See [AUTH_GUIDE.md](AUTH_GUIDE.md) for key generation and signing details.

**Endpoints marked 🔒 require signed requests once a public key is registered for the site.**  
Endpoints without 🔒 are always public (`/track`, `/click`, `/sites`).

### Signing a request
Add two headers to authenticated requests:

| Header | Value |
|--------|-------|
| `X-Timestamp` | Current Unix timestamp (integer) |
| `X-Signature` | `hex( Ed25519Sign(private_key, "{site_id}:{timestamp}") )` |

Requests where the timestamp differs from the server clock by more than 5 minutes are rejected.

## CORS

Allowed origins are configured via the `ALLOWED_ORIGINS` environment variable (comma-separated). Set this to your media site's domain(s) before deploying:

```bash
export ALLOWED_ORIGINS="https://yourmediasite.com,https://www.yourmediasite.com"
```

Defaults to `http://localhost:3000,http://localhost:8011` for local development.

## Rate Limiting

`/track` is rate-limited to **60 requests per minute per IP**. Exceeding this returns `HTTP 429`.
Request bodies larger than 64 KB are rejected with `HTTP 413`.

## Multi-Site Support

This API supports tracking multiple websites independently. Each site has its own isolated database.
To track a specific site, provide a unique `site_id` (e.g., `"my-blog"`, `"portfolio"`, `"client-site-1"`).
If no `site_id` is provided, data is stored in the `"default"` database.

## Endpoints

### 1. Register Public Key
Registers a public key for a site to enable authentication.

- **URL**: `/register-key`
- **Method**: `POST`
- **Body**:
  ```json
  {
    "site_id": "my-site",
    "public_key_hex": "..."
  }
  ```

### 2. Pair Device (QR Code)
Generates a new key pair and returns a QR code for easy setup with the iOS app.

- **URL**: `/pair/{site_id}`
- **Method**: `GET`
- **Query Parameters**:
  - `force` (optional, bool): Re-generate key even if one exists. **Requires valid auth headers** (`X-Timestamp` + `X-Signature`) when a key is already registered, to prevent unauthorized key replacement.
- **Response**: HTML page with QR Code.
- **QR Payload (JSON)**:
  ```json
  {
    "base_url": "http://...",
    "site_id": "...",
    "private_key": "..."
  }
  ```

### 3. Check API Status
Checks if the API is running.

- **URL**: `/`
- **Method**: `GET`
- **Response**:
  ```json
  {
    "message": "Privacy Visitor Tracker API is running"
  }
  ```

### 2. List All Sites
Returns a list of all site IDs that have data stored, along with their authentication status.

- **URL**: `/sites`
- **Method**: `GET`
- **Response**:
  ```json
  {
    "sites": [
      {
        "id": "default",
        "requiresAuth": false
      },
      {
        "id": "my-blog",
        "requiresAuth": true
      }
    ]
  }
  ```

### 3. Track a Visit
Records a new visit. Call this from your frontend when a page loads.

**Rate limit**: 60 requests/minute per IP.

- **URL**: `/track`
- **Method**: `POST`
- **Headers**:
  - `Content-Type: application/json`
- **Body** (JSON, optional):
  ```json
  {
    "path": "/current-page-path",
    "site_id": "my-website-name"  // Optional. Defaults to "default"
  }
  ```

- **Response**:
  ```json
  {
    "status": "ok",
    "country": "US",
    "unique": true,       // New unique visitor (ever)
    "unique_today": true, // New unique visitor (today)
    "page": "/current-page-path",
    "ua_info": {
        "device": "Desktop",
        "browser": "Chrome",
        "os": "Mac OS X"
    },
    "referrer": "Search Engine"
  }
  ```

- **Example (JavaScript/Fetch)**:
  ```javascript
  fetch('http://localhost:8011/track', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      path: window.location.pathname,
      site_id: 'my-portfolio' 
    }),
  });
  ```

### 4. Track an Outgoing Link
Records a click on an external link.

- **URL**: `/click`
- **Method**: `POST`
- **Headers**:
  - `Content-Type: application/json`
- **Body** (JSON):
  ```json
  {
    "url": "https://twitter.com/myprofile",
    "site_id": "my-website-name"  // Optional. Defaults to "default"
  }
  ```

- **Response**:
  ```json
  {
    "status": "ok",
    "url": "https://twitter.com/myprofile"
  }
  ```

- **Example (JavaScript)**:
  ```javascript
  fetch('http://localhost:8011/click', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      url: 'https://twitter.com/myprofile',
      site_id: 'my-portfolio'
    })
  });
  ```

### 5. Get Statistics 🔒
Retrieves aggregated visitor statistics for a specific site.

> **Requires auth headers if a public key is registered for the site.**

- **URL**: `/stats`
- **Method**: `GET`
- **Query Parameters**:
  - `site_id` (optional): The ID of the site to retrieve stats for. Defaults to "default".

- **Response**:
  ```json
  {
    "total_visits": 150,
    "unique_visitors": 42,
    "history": [
        {"date": "2023-10-27", "total_visits": 10, "unique_visitors": 5},
        {"date": "2023-10-26", "total_visits": 15, "unique_visitors": 8}
    ],
    "countries": {
      "US": 80,
      "CA": 20
    },
    "pages": {
      "/": 50,
      "/blog": 30
    },
    "devices": {
        "Desktop": 100,
        "Mobile": 50
    },
    "browsers": {
        "Chrome": 90,
        "Safari": 40
    },
    "os": {
        "Windows": 80,
        "Mac OS X": 40
    },
    "referrers": {
        "Search Engine": 60,
        "Direct": 40
    },
    "links": {
        "https://twitter.com/myprofile": 15,
        "https://github.com/myrepo": 8
    }
  }
  ```

- **Example (cURL)**:
  ```bash
  # Get stats for "my-portfolio"
  curl "http://localhost:8011/stats?site_id=my-portfolio"
  ```

### 6. Get Traffic Forecast (ML) 🔒
Predicts future visitor counts using Linear Regression.

> **Requires auth headers if a public key is registered for the site.**

- **URL**: `/forecast`
- **Method**: `GET`
- **Query Parameters**:
  - `site_id` (optional): Defaults to `"default"`.
  - `days` (optional): Number of days to predict. Range: 1–90. Defaults to `7`.

- **Response**:
  ```json
  {
    "can_forecast": true,
    "forecast": [
        {"date": "2023-12-07", "predicted_visits": 150},
        {"date": "2023-12-08", "predicted_visits": 160}
    ],
    "trend": "increasing",
    "slope": 10.5
  }
  ```

### 7. Get Summary Insights (ML) 🔒
Provides statistical summaries and growth metrics.

> **Requires auth headers if a public key is registered for the site.**

- **URL**: `/summary`
- **Method**: `GET`
- **Query Parameters**:
  - `site_id` (optional): Defaults to "default".

- **Response**:
  ```json
  {
    "average_daily_visits": 120.5,
    "average_daily_unique": 85.2,
    "busiest_day_of_week": "Wednesday",
    "weekly_growth": {
        "current_week_visits": 850,
        "previous_week_visits": 700,
        "growth_rate_percent": 21.4
    }
  }
  ```

### 8. Detect Anomalies (ML) 🔒
Identifies unusual traffic spikes or dips using Isolation Forest.

> **Requires auth headers if a public key is registered for the site.**

- **URL**: `/anomalies`
- **Method**: `GET`
- **Query Parameters**:
  - `site_id` (optional): Defaults to "default".

- **Response**:
  ```json
  {
    "has_anomalies": true,
    "anomalies": [
        {
            "date": "2023-12-01",
            "visits": 500,
            "type": "spike"
        }
    ]
  }
  ```

### 9. Detect Bots (ML) 🔒
Identifies potential bots based on request patterns and user agent scores.

> **Requires auth headers if a public key is registered for the site.**

- **URL**: `/bots`
- **Method**: `GET`
- **Query Parameters**:
  - `site_id` (optional): Defaults to "default".

- **Response**:
  ```json
  {
    "detected_bots_count": 2,
    "bots": [
        {
            "ip_hash": "a1b2c3...",
            "request_count": 500,
            "reason": "High Request Volume, Abnormal Request Rate"
        }
    ]
  }
  ```

## Interactive Documentation

Since this API is built with FastAPI, you can also access interactive documentation generated automatically:

- **Swagger UI**: [http://localhost:8011/docs](http://localhost:8011/docs) - Test endpoints directly in your browser.
- **ReDoc**: [http://localhost:8011/redoc](http://localhost:8011/redoc) - Alternative documentation view.
