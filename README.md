# Privacy-Focused Visitor Tracker API

A lightweight, privacy-respecting analytics API built with Python (FastAPI) and SQLite. It provides visitor tracking, multi-site support, machine learning insights, and optional cryptographic authentication.

## 🚀 Features

### 🔒 Privacy & Security
- **No PII Storage**: IP addresses are hashed with a persistent salt using SHA-256.
- **Ed25519 Authentication**: Optional key-based authentication to secure your analytics data.
- **QR Code Pairing**: Instantly pair with the companion iOS app via QR code.

### 📊 Analytics & Tracking
- **Multi-Site Support**: Track unlimited websites with isolated databases per `site_id`.
- **Visitor Stats**: Unique visitors, total page views, and daily history.
- **Geo-Location**: Country-level breakdown using local GeoLite2 database.
- **Device Fingerprinting**: Tracks Browser, OS, and Device Type (Mobile/Desktop/Bot).
- **Referrer Tracking**: Categorizes traffic sources (Search, Social, Direct, etc.).
- **Outgoing Links**: Track clicks on external links.

### 🤖 Machine Learning Insights
- **Traffic Forecasting**: Predicts future traffic trends using Linear Regression.
- **Anomaly Detection**: Identifies unusual traffic patterns using Isolation Forest.
- **Bot Detection**: Advanced heuristic and ML-based bot classification.

## 🛠 Requirements

- **Docker** (Recommended) OR **Python 3.11+**
- **GeoLite2 City Database** (`GeoLite2-City.mmdb`)
  - *Required for country statistics. Download from MaxMind and place in the project root.*

## 📦 Installation

### Option 1: Docker (Recommended)

1.  **Setup**:
    ```bash
    # Clone repository
    git clone <repo-url>
    cd v01dworksAnalyticsAPI

    # Place GeoLite2-City.mmdb in the root folder
    ```

2.  **Run**:
    ```bash
    docker-compose up -d --build
    ```
    The API will be available at `http://localhost:8011`.

### Option 2: Local Python

1.  **Environment**:
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # Windows: .venv\Scripts\activate
    pip install -r requirements.txt
    ```

2.  **Run**:
    ```bash
    # Set your site's domain before starting (no wildcard CORS in production)
    export ALLOWED_ORIGINS="https://yourmediasite.com,https://www.yourmediasite.com"
    uvicorn main:app --reload --port 8011
    ```

## 📖 Usage Guide

### 1. Tracking a Visit
Send a POST request from your frontend when a page loads.

**JavaScript Example:**
```javascript
fetch('http://localhost:8011/track', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    path: window.location.pathname,
    site_id: 'my-awesome-site' // Optional: defaults to 'default'
  })
});
```

### 2. Viewing Statistics
- **Public Access**: By default, stats are public.
  - `GET /stats?site_id=my-awesome-site`
- **Authenticated Access**: If you register a key, you must sign requests.

### 3. Authentication & Pairing
Secure your data so only you can view it.

- **iOS App Pairing**:
  *This feature is designed for the upcoming iOS companion app.*
  1. Go to `http://localhost:8011/pair/my-awesome-site` in your browser.
  2. Scan the QR code to pair (once the app is released).
  3. The site is now locked and paired.

- **Manual Setup**:
  See [AUTH_GUIDE.md](AUTH_GUIDE.md) for details on generating keys and signing requests manually.

## 📚 Documentation

- **[API_DOCUMENTATION.md](API_DOCUMENTATION.md)**: Full API reference including all endpoints and parameters.
- **[AUTH_GUIDE.md](AUTH_GUIDE.md)**: Technical guide for implementing the Ed25519 authentication scheme.

## 🏗 Project Structure

```
├── app/
│   ├── api.py          # API Routes & Logic
│   ├── auth.py         # Cryptography & Signature Verification
│   ├── database.py     # SQLite Connection & Schema
│   ├── ml.py           # Machine Learning Models
│   └── utils.py        # IP Hashing & GeoIP Helpers
├── data/               # SQLite Databases (*.db) & Salt
├── main.py             # FastAPI Entrypoint
├── Dockerfile          # Container Config
└── requirements.txt    # Python Dependencies
```

## 🛡 Privacy Architecture

1.  **Salt Generation**: On first run, a random salt is generated in `data/.salt`.
2.  **Hashing**: `SHA256(IP + Salt)` is used as the unique identifier.
3.  **Storage**: Only the hash is stored. The original IP is discarded immediately after processing location data.
4.  **Isolation**: Each `site_id` gets its own `.db` file, ensuring data separation.

## 📱 iOS Companion App (Coming Soon)

A native iOS app is currently in development to visualize your analytics on the go.
- **Widgets**: View stats right from your home screen.
- **Secure Pairing**: Scan a QR code to securely link your API.
- **Privacy**: Your data stays on your server and your device.

## License

MIT
