# Privacy-Focused Visitor Tracker API

A super basic, privacy-respecting visitor count tracker built with Python and FastAPI.

## Features

- **Privacy First**: No IP addresses are stored. IPs are hashed with a salt to track unique visitors without compromising user identity.
- **Multi-Site Support**: Track multiple websites with isolated databases.
- **Machine Learning Insights**:
    - **Traffic Forecasting**: Predicts future visitor trends.
    - **Anomaly Detection**: Identifies unusual traffic spikes or dips.
    - **Bot Detection**: Flags suspicious bot-like behavior.
- **Optional Authentication**: Secure your data with Ed25519 key-based authentication.
- **Country Statistics**: Tracks visitor counts by country using GeoLite2 (local database).
- **Page View & Link Tracking**: Tracks most visited pages and outgoing link clicks.
- **Simple Statistics**: Provides total visits, unique visitors count, country breakdown, and page views.
- **SQLite Database**: Lightweight and self-contained.

## Requirements

- Python 3.11+
- GeoLite2 City Database (`GeoLite2-City.mmdb`) - *Note: You must obtain this from MaxMind or another source and place it in the project root.*

## Installation

### Option 1: Docker (Recommended)

1.  Download `GeoLite2-City.mmdb` and place it in the project root.
2.  Run with Docker Compose:
    ```bash
    docker-compose up -d
    ```
    The API will be available at `http://localhost:8000`.

### Option 2: Local Python

1.  Clone the repository.
2.  Create a virtual environment:
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    ```
3.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
4.  Download `GeoLite2-City.mmdb` and place it in the root directory.

## Usage

1.  **Run the server**:
    -   **Docker**: `docker-compose up`
    -   **Local**: `uvicorn main:app --reload` (or use VS Code Task: `Run FastAPI`)

2.  **API Endpoints**:
    -   `POST /track`: Record a visit.
        -   Optional JSON body: `{"path": "/your-page-path"}`
    -   `GET /stats`: Retrieve statistics.

## Privacy Details

- **IP Hashing**: Client IPs are hashed using SHA-256 with a salt stored in `data/.salt`. The salt is generated once on first run.
- **Data Storage**:
    -   Database is stored in `data/stats.db`.
    -   `unique_visitors`: Stores `ip_hash` and `last_seen`.
    -   `country_stats`: Stores `country_code` and `visitor_count`.
    -   `page_stats`: Stores `page_path` and `view_count`.
    -   `general_stats`: Stores `total_visits`.
-   No raw IP addresses or user agent strings are stored.

## License

MIT
