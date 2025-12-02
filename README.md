# Privacy-Focused Visitor Tracker API

A super basic, privacy-respecting visitor count tracker built with Python and FastAPI.

## Features

- **Privacy First**: No IP addresses are stored. IPs are hashed with a salt to track unique visitors without compromising user identity.
- **Country Statistics**: Tracks visitor counts by country using GeoLite2 (local database).
- **Simple Statistics**: Provides total visits, unique visitors count, and country breakdown.
- **SQLite Database**: Lightweight and self-contained.

## Requirements

- Python 3.11+
- GeoLite2 City Database (`GeoLite2-City.mmdb`) - *Note: You must obtain this from MaxMind or another source and place it in the project root.*

## Installation

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

1.  Run the server:
    ```bash
    uvicorn main:app --reload
    ```
    Or use the VS Code Task: `Run FastAPI`.

2.  API Endpoints:
    -   `POST /track`: Record a visit.
    -   `GET /stats`: Retrieve statistics.

## Privacy Details

- **IP Hashing**: Client IPs are hashed using SHA-256 with a salt stored in `.salt`. The salt is generated once on first run.
- **Data Storage**:
    -   `unique_visitors`: Stores `ip_hash` and `last_seen`.
    -   `country_stats`: Stores `country_code` and `visitor_count`.
    -   `general_stats`: Stores `total_visits`.
-   No raw IP addresses or user agent strings are stored.

## License

MIT
