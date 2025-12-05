# API Documentation

Base URL: `http://localhost:8011` (default)

## Multi-Site Support

This API supports tracking multiple websites independently. Each site has its own isolated database.
To track a specific site, simply provide a unique `site_id` (e.g., "my-blog", "portfolio", "client-site-1") when calling the endpoints.
If no `site_id` is provided, data is stored in the "default" database.

## Endpoints

### 1. Check API Status
Checks if the API is running.

- **URL**: `/`
- **Method**: `GET`
- **Response**:
  ```json
  {
    "message": "Privacy Visitor Tracker API is running"
  }
  ```

### 2. Track a Visit
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

### 3. Track an Outgoing Link
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

### 4. Get Statistics
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

## Interactive Documentation

Since this API is built with FastAPI, you can also access interactive documentation generated automatically:

- **Swagger UI**: [http://localhost:8011/docs](http://localhost:8011/docs) - Test endpoints directly in your browser.
- **ReDoc**: [http://localhost:8011/redoc](http://localhost:8011/redoc) - Alternative documentation view.
