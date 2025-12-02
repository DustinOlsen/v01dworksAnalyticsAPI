import sqlite3
from pathlib import Path

DB_PATH = Path("stats.db")

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
        CREATE TABLE IF NOT EXISTS general_stats (
            key TEXT PRIMARY KEY,
            value INTEGER DEFAULT 0
        )
    """)
    # Initialize total visits if not exists
    cursor.execute("INSERT OR IGNORE INTO general_stats (key, value) VALUES ('total_visits', 0)")
    conn.commit()
    conn.close()
