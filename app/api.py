from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import Optional
from .database import get_db
from .utils import hash_ip, get_country_from_ip
import sqlite3

router = APIRouter()

class VisitData(BaseModel):
    path: str = "/"

@router.post("/track")
def track_visit(request: Request, data: Optional[VisitData] = None):
    # Get client IP. 
    # Check X-Forwarded-For first (for proxies/load balancers)
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    else:
        client_ip = request.client.host
    
    hashed_ip = hash_ip(client_ip)
    country = get_country_from_ip(client_ip)
    page_path = data.path if data and data.path else "/"
    
    conn = get_db()
    cursor = conn.cursor()
    
    # 1. Update Total Visits
    cursor.execute("UPDATE general_stats SET value = value + 1 WHERE key = 'total_visits'")
    
    # 2. Update Unique Visitors
    # Try to insert. If exists, it's not unique.
    is_unique = False
    try:
        cursor.execute("INSERT INTO unique_visitors (ip_hash) VALUES (?)", (hashed_ip,))
        is_unique = True
    except sqlite3.IntegrityError:
        # Already visited, update last seen
        cursor.execute("UPDATE unique_visitors SET last_seen = CURRENT_TIMESTAMP WHERE ip_hash = ?", (hashed_ip,))
        
    # 3. Update Country Stats
    # We count every visit for country stats to see traffic volume by region
    cursor.execute("""
        INSERT INTO country_stats (country_code, visitor_count) 
        VALUES (?, 1) 
        ON CONFLICT(country_code) 
        DO UPDATE SET visitor_count = visitor_count + 1
    """, (country,))

    # 4. Update Page Stats
    cursor.execute("""
        INSERT INTO page_stats (page_path, view_count) 
        VALUES (?, 1) 
        ON CONFLICT(page_path) 
        DO UPDATE SET view_count = view_count + 1
    """, (page_path,))
    
    conn.commit()
    conn.close()
    
    return {"status": "ok", "country": country, "unique": is_unique, "page": page_path}

@router.get("/stats")
def get_stats():
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT value FROM general_stats WHERE key = 'total_visits'")
    row = cursor.fetchone()
    total_visits = row["value"] if row else 0
    
    cursor.execute("SELECT COUNT(*) as count FROM unique_visitors")
    row = cursor.fetchone()
    unique_visitors = row["count"] if row else 0
    
    cursor.execute("SELECT * FROM country_stats ORDER BY visitor_count DESC")
    countries = {row["country_code"]: row["visitor_count"] for row in cursor.fetchall()}

    cursor.execute("SELECT * FROM page_stats ORDER BY view_count DESC")
    pages = {row["page_path"]: row["view_count"] for row in cursor.fetchall()}
    
    conn.close()
    
    return {
        "total_visits": total_visits,
        "unique_visitors": unique_visitors,
        "countries": countries,
        "pages": pages
    }
