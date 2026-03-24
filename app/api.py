import os
import ipaddress
from fastapi import APIRouter, Request, Depends, HTTPException, Header, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
import qrcode
import io
import base64
import json
from .database import get_db, list_sites
from .utils import hash_ip, get_country_from_ip, parse_user_agent_info, parse_referrer_category
from .ml import generate_forecast, generate_summary, detect_anomalies, detect_bots
from .auth import verify_signature
from .limiter import limiter
import sqlite3

_DEBUG_ENABLED = os.getenv("ENABLE_DEBUG_ENDPOINTS", "false").lower() == "true"


def _get_client_ip(request: Request) -> str:
    """Extract and validate client IP, preferring X-Forwarded-For for proxied deployments."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        raw = forwarded.split(",")[0].strip()
        try:
            ipaddress.ip_address(raw)
            return raw
        except ValueError:
            pass
    return request.client.host or "0.0.0.0"

router = APIRouter()

class VisitData(BaseModel):
    path: str = "/"
    site_id: str = "default"

class ClickData(BaseModel):
    url: str
    site_id: str = "default"

class RegisterKeyData(BaseModel):
    site_id: str
    public_key_hex: str

@router.post("/register-key")
def register_key(data: RegisterKeyData):
    """
    Registers a public key for a site. 
    This is a one-time setup. Once a key is registered, all subsequent 
    requests to stats endpoints for this site MUST be signed.
    """
    conn = get_db(data.site_id)
    cursor = conn.cursor()
    
    # Check if key already exists
    cursor.execute("SELECT key_value FROM auth_config WHERE key_type = 'public_key'")
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Public key already registered for this site")
        
    cursor.execute(
        "INSERT INTO auth_config (key_type, key_value) VALUES ('public_key', ?)",
        (data.public_key_hex,)
    )
    conn.commit()
    conn.close()
    return {"status": "ok", "message": "Public key registered"}

@router.get("/pair/{site_id}", response_class=HTMLResponse)
def pair_device(
    site_id: str,
    request: Request,
    force: bool = False,
    x_timestamp: Optional[int] = Header(None, alias="X-Timestamp"),
    x_signature: Optional[str] = Header(None, alias="X-Signature"),
):
    """
    Generates a new key pair for the site and returns a QR code.
    If force=True, requires a valid signed request (X-Timestamp + X-Signature headers) to
    prevent unauthorized key replacement.
    """
    conn = get_db(site_id)
    cursor = conn.cursor()

    # 1. Check if a key already exists
    cursor.execute("SELECT key_value FROM auth_config WHERE key_type = 'public_key'")
    existing_key = cursor.fetchone()

    if existing_key and not force:
        conn.close()
        return HTMLResponse(
            f"""
            <h1>Error: Already Paired</h1>
            <p>A public key is already registered for site: <strong>{site_id}</strong>.</p>
            <p>Use the signed <code>?force=true</code> endpoint to replace it.</p>
            """,
            status_code=403
        )

    if existing_key and force:
        # Require proof of the existing key before overwriting
        try:
            verify_signature(request, site_id, x_timestamp, x_signature)
        except HTTPException:
            conn.close()
            raise
        cursor.execute("DELETE FROM auth_config WHERE key_type = 'public_key'")
        
    # 2. Generate New Key Pair
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    
    # Serialize Keys
    private_hex = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()
    ).hex()

    public_hex = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    ).hex()
    
    # 3. Save Public Key to DB
    cursor.execute(
        "INSERT INTO auth_config (key_type, key_value) VALUES ('public_key', ?)",
        (public_hex,)
    )
    conn.commit()
    conn.close()
    
    # 4. Create QR Payload
    # Use the request's base URL (e.g., http://192.168.1.5:8000)
    base_url = str(request.base_url).rstrip("/")
    
    payload = {
        "base_url": base_url,
        "site_id": site_id,
        "private_key": private_hex
    }
    
    # 5. Generate QR Code Image
    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(json.dumps(payload))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to Base64 for HTML embedding
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_b64 = base64.b64encode(buf.getvalue()).decode()
    
    # 6. Return HTML
    html_content = f"""
    <!DOCTYPE html>
    <html>
        <head>
            <title>Pair Device - {site_id}</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; text-align: center; padding: 20px; max-width: 600px; margin: 0 auto; }}
                .qr-container {{ margin: 20px 0; border: 1px solid #eee; padding: 20px; display: inline-block; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
                .warning {{ color: #d32f2f; background: #ffebee; padding: 10px; border-radius: 5px; font-size: 0.9em; margin-top: 20px; }}
                code {{ background: #f5f5f5; padding: 2px 5px; border-radius: 3px; }}
            </style>
        </head>
        <body>
            <h1>Pair with iOS App</h1>
            <p>Scan this QR code to configure access for site:</p>
            <h2>{site_id}</h2>
            
            <div class="qr-container">
                <img src="data:image/png;base64,{img_b64}" alt="QR Code" width="300" height="300"/>
            </div>
            
            <div class="warning">
                <strong>Security Warning:</strong> This QR code contains your <strong>Private Key</strong>. 
                <br>Do not share this screen or screenshot it. 
                <br>Once scanned, close this page.
            </div>
            
            <div style="margin-top: 30px; text-align: left; display: inline-block; max-width: 100%;">
                <p><strong>Public Key (for manual registration on other sites):</strong></p>
                <code style="word-break: break-all; display: block; padding: 10px; border: 1px solid #ddd;">{public_hex}</code>
            </div>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@router.get("/debug/auth-status/{site_id}")
def get_auth_status(site_id: str):
    """
    Checks if a public key is registered for the given site_id.
    Only available when ENABLE_DEBUG_ENDPOINTS=true.
    """
    if not _DEBUG_ENABLED:
        raise HTTPException(status_code=404, detail="Not found")
    conn = get_db(site_id)
    cursor = conn.cursor()
    cursor.execute("SELECT key_value FROM auth_config WHERE key_type = 'public_key'")
    row = cursor.fetchone()
    conn.close()
    return {
        "site_id": site_id,
        "is_locked": row is not None,
    }

@router.get("/sites")
def get_sites():
    """
    Returns a list of available sites with their auth status.
    """
    site_ids = list_sites()
    sites_data = []
    
    for site_id in site_ids:
        # Check if site requires auth
        conn = get_db(site_id)
        cursor = conn.cursor()
        cursor.execute("SELECT key_value FROM auth_config WHERE key_type = 'public_key'")
        row = cursor.fetchone()
        conn.close()
        
        sites_data.append({
            "id": site_id,
            "requiresAuth": row is not None
        })
        
    return {"sites": sites_data}

@router.post("/click")
def track_click(request: Request, data: ClickData):
    conn = get_db(data.site_id)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO link_stats (link_url, click_count) 
            VALUES (?, 1) 
            ON CONFLICT(link_url) 
            DO UPDATE SET click_count = click_count + 1
        """, (data.url,))
        conn.commit()
    finally:
        conn.close()
    return {"status": "ok", "url": data.url}

@router.post("/track")
@limiter.limit("60/minute")
def track_visit(request: Request, data: Optional[VisitData] = None):
    client_ip = _get_client_ip(request)

    hashed_ip = hash_ip(client_ip)
    country = get_country_from_ip(client_ip)
    page_path = data.path if data and data.path else "/"
    site_id = data.site_id if data and data.site_id else "default"

    user_agent = request.headers.get("user-agent", "")
    ua_info = parse_user_agent_info(user_agent)
    bot_type = ua_info["bot_type"]
    ua_score = ua_info["ua_score"]

    referrer = request.headers.get("referer")
    referrer_category = parse_referrer_category(referrer)

    is_unique_ever = False
    is_unique_today = False
    today = datetime.utcnow().strftime("%Y-%m-%d")

    conn = get_db(site_id)
    cursor = conn.cursor()
    try:
        # Query existing activity once — used for carry-forward and behavioral checks
        cursor.execute(
            "SELECT request_count, first_seen, last_seen, bot_type FROM visitor_activity WHERE ip_hash = ?",
            (hashed_ip,),
        )
        existing_activity = cursor.fetchone()

        # Carry forward existing bot flag (once flagged, always flagged)
        if existing_activity:
            prev_bot_type = existing_activity["bot_type"] or "none"
            if prev_bot_type != "none" and bot_type == "none":
                bot_type = prev_bot_type
                ua_score = 1.0 if bot_type == "bot" else 0.5

        # Behavioral rate check — only for visitors not yet flagged
        behavioral_flag = False
        if bot_type == "none" and existing_activity:
            try:
                existing_count = existing_activity["request_count"]
                first_seen_dt = datetime.fromisoformat(existing_activity["first_seen"])
                last_seen_dt = datetime.fromisoformat(existing_activity["last_seen"])
                duration_seconds = max(1.0, (last_seen_dt - first_seen_dt).total_seconds())
                rate_per_hour = (existing_count / duration_seconds) * 3600
                if existing_count >= 50 and rate_per_hour > 60:
                    bot_type = "bot"
                    ua_score = 1.0
                    behavioral_flag = True
            except Exception:
                pass

        # Only log a bot on first detection per IP
        prev_bot_type = (existing_activity["bot_type"] or "none") if existing_activity else "none"
        should_log_bot = bot_type != "none" and prev_bot_type == "none"

        # Update visitor_activity for all visitors (needed for rate tracking)
        cursor.execute("""
            INSERT INTO visitor_activity (ip_hash, request_count, ua_score, bot_type)
            VALUES (?, 1, ?, ?)
            ON CONFLICT(ip_hash)
            DO UPDATE SET
                last_seen = CURRENT_TIMESTAMP,
                request_count = request_count + 1,
                ua_score = excluded.ua_score,
                bot_type = CASE
                    WHEN visitor_activity.bot_type = 'bot' THEN 'bot'
                    WHEN excluded.bot_type = 'bot' THEN 'bot'
                    WHEN visitor_activity.bot_type = 'crawler' THEN 'crawler'
                    WHEN excluded.bot_type = 'crawler' THEN 'crawler'
                    ELSE 'none'
                END
        """, (hashed_ip, ua_score, bot_type))

        if bot_type != "none":
            # ── Bot / Crawler path: separate counters, no human stats touched ──
            if bot_type == "bot":
                cursor.execute("""
                    INSERT INTO bot_daily_stats (date, bot_visits, crawler_visits)
                    VALUES (?, 1, 0)
                    ON CONFLICT(date) DO UPDATE SET bot_visits = bot_visits + 1
                """, (today,))
                cursor.execute("""
                    INSERT INTO bot_page_stats (page_path, bot_views, crawler_views)
                    VALUES (?, 1, 0)
                    ON CONFLICT(page_path) DO UPDATE SET bot_views = bot_views + 1
                """, (page_path,))
            else:  # crawler
                cursor.execute("""
                    INSERT INTO bot_daily_stats (date, bot_visits, crawler_visits)
                    VALUES (?, 0, 1)
                    ON CONFLICT(date) DO UPDATE SET crawler_visits = crawler_visits + 1
                """, (today,))
                cursor.execute("""
                    INSERT INTO bot_page_stats (page_path, bot_views, crawler_views)
                    VALUES (?, 0, 1)
                    ON CONFLICT(page_path) DO UPDATE SET crawler_views = crawler_views + 1
                """, (page_path,))

            if should_log_bot:
                if behavioral_flag:
                    reason = "Behavioral: High Request Rate"
                elif bot_type == "crawler":
                    reason = "Known Crawler (User-Agent)"
                else:
                    reason = "Known Bot Signature (User-Agent)"
                cursor.execute(
                    "INSERT INTO bot_logs (ip_hash, reason, bot_type, confidence) VALUES (?, ?, ?, ?)",
                    (hashed_ip, reason, bot_type, ua_score),
                )
        else:
            # ── Human traffic path ──
            # 1. Total visits counter
            cursor.execute("UPDATE general_stats SET value = value + 1 WHERE key = 'total_visits'")

            # 2. Unique visitor tracking
            cursor.execute("SELECT last_seen FROM unique_visitors WHERE ip_hash = ?", (hashed_ip,))
            uv_row = cursor.fetchone()
            if uv_row is None:
                is_unique_ever = True
                is_unique_today = True
                cursor.execute("INSERT INTO unique_visitors (ip_hash) VALUES (?)", (hashed_ip,))
            else:
                last_seen_str = uv_row["last_seen"]
                if not last_seen_str.startswith(today):
                    is_unique_today = True
                cursor.execute(
                    "UPDATE unique_visitors SET last_seen = CURRENT_TIMESTAMP WHERE ip_hash = ?",
                    (hashed_ip,),
                )

            # 3. Daily stats
            cursor.execute("""
                INSERT INTO daily_stats (date, total_visits, unique_visitors)
                VALUES (?, 1, ?)
                ON CONFLICT(date)
                DO UPDATE SET
                    total_visits = total_visits + 1,
                    unique_visitors = unique_visitors + ?
            """, (today, 1 if is_unique_today else 0, 1 if is_unique_today else 0))

            # 4. Country stats
            cursor.execute("""
                INSERT INTO country_stats (country_code, visitor_count)
                VALUES (?, 1)
                ON CONFLICT(country_code)
                DO UPDATE SET visitor_count = visitor_count + 1
            """, (country,))

            # 5. Page stats
            cursor.execute("""
                INSERT INTO page_stats (page_path, view_count)
                VALUES (?, 1)
                ON CONFLICT(page_path)
                DO UPDATE SET view_count = view_count + 1
            """, (page_path,))

            # 6. Device stats
            cursor.execute("""
                INSERT INTO device_stats (device_type, count)
                VALUES (?, 1)
                ON CONFLICT(device_type)
                DO UPDATE SET count = count + 1
            """, (ua_info["device"],))

            # 7. Browser stats
            cursor.execute("""
                INSERT INTO browser_stats (browser_family, count)
                VALUES (?, 1)
                ON CONFLICT(browser_family)
                DO UPDATE SET count = count + 1
            """, (ua_info["browser"],))

            # 8. OS stats
            cursor.execute("""
                INSERT INTO os_stats (os_family, count)
                VALUES (?, 1)
                ON CONFLICT(os_family)
                DO UPDATE SET count = count + 1
            """, (ua_info["os"],))

            # 9. Referrer stats
            cursor.execute("""
                INSERT INTO referrer_stats (category, count)
                VALUES (?, 1)
                ON CONFLICT(category)
                DO UPDATE SET count = count + 1
            """, (referrer_category,))

            # 10. Per-page country stats
            cursor.execute("""
                INSERT INTO page_country_stats (page_path, country_code, view_count)
                VALUES (?, ?, 1)
                ON CONFLICT(page_path, country_code)
                DO UPDATE SET view_count = view_count + 1
            """, (page_path, country))

        conn.commit()
    finally:
        conn.close()

    return {
        "status": "ok",
        "country": country,
        "unique": is_unique_ever,
        "unique_today": is_unique_today,
        "page": page_path,
        "ua_info": ua_info,
        "referrer": referrer_category,
        "bot_type": bot_type,
    }

@router.get("/page-stats", dependencies=[Depends(verify_signature)])
def get_page_stats(site_id: str = "default", path: str = "/"):
    """
    Returns view count and country breakdown for a single page path.
    Useful for displaying per-page analytics directly on the page.
    """
    conn = get_db(site_id)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT view_count FROM page_stats WHERE page_path = ?",
            (path,)
        )
        row = cursor.fetchone()
        view_count = row["view_count"] if row else 0

        cursor.execute(
            "SELECT country_code, view_count FROM page_country_stats "
            "WHERE page_path = ? ORDER BY view_count DESC",
            (path,)
        )
        countries = {r["country_code"]: r["view_count"] for r in cursor.fetchall()}
    finally:
        conn.close()

    return {
        "path": path,
        "view_count": view_count,
        "countries": countries,
    }


@router.get("/stats", dependencies=[Depends(verify_signature)])
def get_stats(site_id: str = "default"):
    conn = get_db(site_id)
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
    
    cursor.execute("SELECT * FROM device_stats ORDER BY count DESC")
    devices = {row["device_type"]: row["count"] for row in cursor.fetchall()}

    cursor.execute("SELECT * FROM browser_stats ORDER BY count DESC")
    browsers = {row["browser_family"]: row["count"] for row in cursor.fetchall()}

    cursor.execute("SELECT * FROM os_stats ORDER BY count DESC")
    os_stats = {row["os_family"]: row["count"] for row in cursor.fetchall()}
    
    cursor.execute("SELECT * FROM referrer_stats ORDER BY count DESC")
    referrers = {row["category"]: row["count"] for row in cursor.fetchall()}
    
    cursor.execute("SELECT * FROM link_stats ORDER BY click_count DESC")
    links = {row["link_url"]: row["click_count"] for row in cursor.fetchall()}
    
    # Get last 30 days of history
    cursor.execute("SELECT * FROM daily_stats ORDER BY date DESC LIMIT 30")
    history = [dict(row) for row in cursor.fetchall()]

    # Per-page country breakdown
    cursor.execute("SELECT page_path, country_code, view_count FROM page_country_stats ORDER BY page_path, view_count DESC")
    page_countries: dict = {}
    for r in cursor.fetchall():
        page_countries.setdefault(r["page_path"], {})[r["country_code"]] = r["view_count"]

    # Bot summary
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    cursor.execute("SELECT SUM(bot_visits) AS bv, SUM(crawler_visits) AS cv FROM bot_daily_stats")
    _bt = cursor.fetchone()
    cursor.execute(
        "SELECT bot_visits, crawler_visits FROM bot_daily_stats WHERE date = ?", (today_str,)
    )
    _bd = cursor.fetchone()
    bot_summary = {
        "total_bot_visits": (_bt["bv"] or 0) if _bt else 0,
        "total_crawler_visits": (_bt["cv"] or 0) if _bt else 0,
        "bots_today": _bd["bot_visits"] if _bd else 0,
        "crawlers_today": _bd["crawler_visits"] if _bd else 0,
    }

    conn.close()
    
    return {
        "total_visits": total_visits,
        "unique_visitors": unique_visitors,
        "history": history,
        "countries": countries,
        "pages": pages,
        "devices": devices,
        "browsers": browsers,
        "os": os_stats,
        "referrers": referrers,
        "links": links,
        "page_countries": page_countries,
        "bot_summary": bot_summary,
    }

@router.get("/forecast", dependencies=[Depends(verify_signature)])
def get_forecast(site_id: str = "default", days: int = Query(default=7, ge=1, le=90)):
    return generate_forecast(site_id, days)

@router.get("/summary", dependencies=[Depends(verify_signature)])
def get_summary(site_id: str = "default"):
    return generate_summary(site_id)

@router.get("/anomalies", dependencies=[Depends(verify_signature)])
def get_anomalies(site_id: str = "default"):
    return detect_anomalies(site_id)

@router.get("/bots", dependencies=[Depends(verify_signature)])
def get_bots(site_id: str = "default"):
    ml_result = detect_bots(site_id)

    conn = get_db(site_id)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT date, bot_visits, crawler_visits FROM bot_daily_stats ORDER BY date DESC LIMIT 30"
        )
        bot_daily_trend = [dict(row) for row in cursor.fetchall()]

        cursor.execute("""
            SELECT page_path, bot_views, crawler_views, (bot_views + crawler_views) AS total
            FROM bot_page_stats
            ORDER BY total DESC
            LIMIT 10
        """)
        top_bot_pages = [dict(row) for row in cursor.fetchall()]

        cursor.execute("SELECT bot_type, COUNT(*) AS count FROM bot_logs GROUP BY bot_type")
        bot_type_breakdown = {row["bot_type"]: row["count"] for row in cursor.fetchall()}

        cursor.execute("""
            SELECT ip_hash, detected_at, reason, bot_type, confidence
            FROM bot_logs
            ORDER BY detected_at DESC
            LIMIT 20
        """)
        recent_bot_logs = [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

    return {
        **ml_result,
        "bot_daily_trend": bot_daily_trend,
        "top_bot_pages": top_bot_pages,
        "bot_type_breakdown": bot_type_breakdown,
        "recent_bot_logs": recent_bot_logs,
    }


@router.get("/bot-stats", dependencies=[Depends(verify_signature)])
def get_bot_stats(site_id: str = "default"):
    conn = get_db(site_id)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT date, bot_visits, crawler_visits FROM bot_daily_stats ORDER BY date DESC"
        )
        daily = [dict(row) for row in cursor.fetchall()]

        cursor.execute("""
            SELECT page_path, bot_views, crawler_views
            FROM bot_page_stats
            ORDER BY (bot_views + crawler_views) DESC
        """)
        pages = [dict(row) for row in cursor.fetchall()]

        cursor.execute("SELECT bot_type, COUNT(*) AS count FROM bot_logs GROUP BY bot_type")
        type_breakdown = {row["bot_type"]: row["count"] for row in cursor.fetchall()}

        cursor.execute("""
            SELECT ip_hash, detected_at, reason, bot_type, confidence
            FROM bot_logs
            ORDER BY detected_at DESC
            LIMIT 50
        """)
        recent_logs = [dict(row) for row in cursor.fetchall()]

        total_bot_visits = sum(r["bot_visits"] for r in daily)
        total_crawler_visits = sum(r["crawler_visits"] for r in daily)
    finally:
        conn.close()

    return {
        "summary": {
            "total_bot_visits": total_bot_visits,
            "total_crawler_visits": total_crawler_visits,
        },
        "daily": daily,
        "pages": pages,
        "type_breakdown": type_breakdown,
        "recent_logs": recent_logs,
    }
