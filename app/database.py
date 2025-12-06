import sqlite3
from pathlib import Path
import os
import re

# Ensure data directory exists
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

def get_db_path(site_id: str) -> Path:
    # Sanitize site_id to prevent path traversal
    # Allow alphanumeric, dashes, underscores, and dots (for domains)
    safe_id = re.sub(r'[^a-zA-Z0-9_.-]', '', site_id)
    if not safe_id:
        safe_id = "default"
    return DATA_DIR / f"{safe_id}.db"

def list_sites():
    """
    Lists all available site IDs based on the database files.
    """
    sites = []
    for file in DATA_DIR.glob("*.db"):
        # Remove .db extension
        sites.append(file.stem)
    return sorted(sites)

def get_db(site_id: str = "default"):
    db_path = get_db_path(site_id)
    
    # Always ensure tables exist, even if file exists
    # This handles schema migrations (like adding new tables)
    init_db(site_id)
        
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(site_id: str = "default"):
    db_path = get_db_path(site_id)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS unique_visitors (
            ip_hash TEXT PRIMARY KEY,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS country_stats (
            country_code TEXT PRIMARY KEY,
            visitor_count INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS page_stats (
            page_path TEXT PRIMARY KEY,
            view_count INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS device_stats (
            device_type TEXT PRIMARY KEY,
            count INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS browser_stats (
            browser_family TEXT PRIMARY KEY,
            count INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS os_stats (
            os_family TEXT PRIMARY KEY,
            count INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS referrer_stats (
            category TEXT PRIMARY KEY,
            count INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_stats (
            date TEXT PRIMARY KEY,
            total_visits INTEGER DEFAULT 0,
            unique_visitors INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS link_stats (
            link_url TEXT PRIMARY KEY,
            click_count INTEGER DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS visitor_activity (
            ip_hash TEXT PRIMARY KEY,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            request_count INTEGER DEFAULT 1,
            ua_score REAL DEFAULT 0.0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bot_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_hash TEXT,
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reason TEXT,
            confidence REAL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS general_stats (
            key TEXT PRIMARY KEY,
            value INTEGER DEFAULT 0
        )
    """)
    # Initialize total visits if not exists
    cursor.execute("INSERT OR IGNORE INTO general_stats (key, value) VALUES ('total_visits', 0)")
    conn.commit()
    conn.close()
