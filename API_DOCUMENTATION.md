# API Documentation

Base URL: `http://localhost:8011` (default)

## Authentication

This API supports optional key-based authentication. See [AUTH_GUIDE.md](AUTH_GUIDE.md) for details on generating keys and signing requests.

## Multi-Site Support

This API supports tracking multiple websites independently. Each site has its own isolated database.
To track a specific site, simply provide a unique `site_id` (e.g., "my-blog", "portfolio", "client-site-1") when calling the endpoints.
If no `site_id` is provided, data is stored in the "default" database.

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
**Note**: This only works if no key is currently registered for the site.

- **URL**: `/pair/{site_id}`
- **Method**: `GET`
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
Returns a list of all site IDs that have data stored.

- **URL**: `/sites`
- **Method**: `GET`
- **Response**:
  ```json
  {
    "sites": [
      "default",
      "my-blog",
      "portfolio"
    ]
  }
  ```

### 3. Track a Visit
Records a new visit. Call this endpoint from your frontend application when a page loads.

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

### 5. Get Statistics
Retrieves the aggregated visitor statistics for a specific site.

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

### 6. Get Traffic Forecast (ML)
Predicts future visitor counts using Linear Regression.

- **URL**: `/forecast`
- **Method**: `GET`
- **Query Parameters**:
  - `site_id` (optional): Defaults to "default".
  - `days` (optional): Number of days to predict (default: 7).

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

### 7. Get Summary Insights (ML)
Provides statistical summaries and growth metrics.

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

### 8. Detect Anomalies (ML)
Identifies unusual traffic spikes or dips using Isolation Forest.

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

### 9. Detect Bots (ML)
Identifies potential bots based on request patterns and user agent scores.

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
