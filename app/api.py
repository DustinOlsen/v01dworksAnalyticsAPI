from fastapi import APIRouter, Request, Depends, HTTPException
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
import sqlite3

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
def pair_device(site_id: str, request: Request):
    """
    Generates a new key pair for the site and returns a QR code 
    containing the configuration (URL, Site ID, Private Key) for the iOS app.
    Only works if no key is currently registered.
    """
    conn = get_db(site_id)
    cursor = conn.cursor()
    
    # 1. Check if key already exists
    cursor.execute("SELECT key_value FROM auth_config WHERE key_type = 'public_key'")
    if cursor.fetchone():
        conn.close()
        return HTMLResponse(
            "<h1>Error: Already Paired</h1>"
            "<p>A public key is already registered for this site.</p>"
            "<p>To re-pair, you must manually delete the key from the database or use a new site ID.</p>",
            status_code=403
        )
        
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
            
            <p><small>Public Key has been registered successfully.</small></p>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@router.get("/sites")
def get_sites():
    return {"sites": list_sites()}

@router.post("/click")
def track_click(request: Request, data: ClickData):
    conn = get_db(data.site_id)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO link_stats (link_url, click_count) 
        VALUES (?, 1) 
        ON CONFLICT(link_url) 
        DO UPDATE SET click_count = click_count + 1
    """, (data.url,))
    
    conn.commit()
    conn.close()
    
    return {"status": "ok", "url": data.url}

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
    site_id = data.site_id if data and data.site_id else "default"
    
    # Parse User-Agent
    user_agent = request.headers.get("user-agent", "")
    ua_info = parse_user_agent_info(user_agent)
    
    # Parse Referrer
    referrer = request.headers.get("referer")
    referrer_category = parse_referrer_category(referrer)
    
    conn = get_db(site_id)
    cursor = conn.cursor()
    
    # --- Update Visitor Activity (For Bot Detection) ---
    # Calculate simple UA score (1.0 if unknown/bot, 0.0 if common)
    # This is a simplified heuristic. In production, you'd query the browser_stats frequency.
    ua_score = 0.0
    if ua_info['device'] == 'Bot' or ua_info['browser'] == 'Unknown':
        ua_score = 1.0
        
    cursor.execute("""
        INSERT INTO visitor_activity (ip_hash, request_count, ua_score)
        VALUES (?, 1, ?)
        ON CONFLICT(ip_hash)
        DO UPDATE SET 
            last_seen = CURRENT_TIMESTAMP,
            request_count = request_count + 1,
            ua_score = ?
    """, (hashed_ip, ua_score, ua_score))
    
    # 1. Update Total Visits
    cursor.execute("UPDATE general_stats SET value = value + 1 WHERE key = 'total_visits'")
    
    # 2. Update Unique Visitors & Daily Stats
    today = datetime.utcnow().strftime("%Y-%m-%d")
    
    # Check if IP has visited before to determine uniqueness
    cursor.execute("SELECT last_seen FROM unique_visitors WHERE ip_hash = ?", (hashed_ip,))
    row = cursor.fetchone()
    
    is_unique_ever = False
    is_unique_today = False
    
    if row is None:
        # Never seen before
        is_unique_ever = True
        is_unique_today = True
        cursor.execute("INSERT INTO unique_visitors (ip_hash) VALUES (?)", (hashed_ip,))
    else:
        # Seen before, check if it was today (UTC)
        last_seen_str = row["last_seen"] # Format: YYYY-MM-DD HH:MM:SS
        if not last_seen_str.startswith(today):
            is_unique_today = True
        
        # Update last seen
        cursor.execute("UPDATE unique_visitors SET last_seen = CURRENT_TIMESTAMP WHERE ip_hash = ?", (hashed_ip,))

    # Update Daily Stats
    cursor.execute("""
        INSERT INTO daily_stats (date, total_visits, unique_visitors) 
        VALUES (?, 1, ?) 
        ON CONFLICT(date) 
        DO UPDATE SET 
            total_visits = total_visits + 1,
            unique_visitors = unique_visitors + ?
    """, (today, 1 if is_unique_today else 0, 1 if is_unique_today else 0))
        
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
    
    # 5. Update Device Stats
    cursor.execute("""
        INSERT INTO device_stats (device_type, count) 
        VALUES (?, 1) 
        ON CONFLICT(device_type) 
        DO UPDATE SET count = count + 1
    """, (ua_info["device"],))

    # 6. Update Browser Stats
    cursor.execute("""
        INSERT INTO browser_stats (browser_family, count) 
        VALUES (?, 1) 
        ON CONFLICT(browser_family) 
        DO UPDATE SET count = count + 1
    """, (ua_info["browser"],))

    # 7. Update OS Stats
    cursor.execute("""
        INSERT INTO os_stats (os_family, count) 
        VALUES (?, 1) 
        ON CONFLICT(os_family) 
        DO UPDATE SET count = count + 1
    """, (ua_info["os"],))

    # 8. Update Referrer Stats
    cursor.execute("""
        INSERT INTO referrer_stats (category, count) 
        VALUES (?, 1) 
        ON CONFLICT(category) 
        DO UPDATE SET count = count + 1
    """, (referrer_category,))
    
    conn.commit()
    conn.close()
    
    return {
        "status": "ok", 
        "country": country, 
        "unique": is_unique_ever, 
        "unique_today": is_unique_today,
        "page": page_path,
        "ua_info": ua_info,
        "referrer": referrer_category
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
        "links": links
    }

@router.get("/forecast", dependencies=[Depends(verify_signature)])
def get_forecast(site_id: str = "default", days: int = 7):
    return generate_forecast(site_id, days)

@router.get("/summary", dependencies=[Depends(verify_signature)])
def get_summary(site_id: str = "default"):
    return generate_summary(site_id)

@router.get("/anomalies", dependencies=[Depends(verify_signature)])
def get_anomalies(site_id: str = "default"):
    return detect_anomalies(site_id)

@router.get("/bots", dependencies=[Depends(verify_signature)])
def get_bots(site_id: str = "default"):
    return detect_bots(site_id)
