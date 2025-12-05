import sqlite3
from pathlib import Path
import os

# Ensure data directory exists
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "stats.db"

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
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
        CREATE TABLE IF NOT EXISTS general_stats (
            key TEXT PRIMARY KEY,
            value INTEGER DEFAULT 0
        )
    """)
    # Initialize total visits if not exists
    cursor.execute("INSERT OR IGNORE INTO general_stats (key, value) VALUES ('total_visits', 0)")
    conn.commit()
    conn.close()
