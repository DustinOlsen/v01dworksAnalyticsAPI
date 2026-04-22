import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from app.api import router
from app.database import init_db, list_sites, get_db
from app.limiter import limiter

# ── Request body size limit ──────────────────────────────────────────────────
MAX_REQUEST_BODY = 64 * 1024  # 64 KB

class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > MAX_REQUEST_BODY:
                    return Response(content="Request body too large", status_code=413)
            except ValueError:
                pass
        return await call_next(request)

# ── App setup ────────────────────────────────────────────────────────────────
app = FastAPI(title="Privacy Visitor Tracker")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — set ALLOWED_ORIGINS env var to a comma-separated list of your domains.
# e.g. ALLOWED_ORIGINS="https://yourmediasite.com,https://www.yourmediasite.com"
_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8000,http://localhost:8011")
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Timestamp", "X-Signature"],
)
app.add_middleware(RequestSizeLimitMiddleware)

@app.on_event("startup")
def on_startup():
    sites = list_sites() or ["default"]
    for site_id in sites:
        init_db(site_id)
        _retroactive_flag_high_path_bots(site_id)
    if "default" not in sites:
        init_db("default")


def _retroactive_flag_high_path_bots(site_id: str):
    """Flag any IPs in ip_path_counts with >50 distinct paths not yet marked as bots."""
    conn = get_db(site_id)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT ipc.ip_hash, COUNT(ipc.path) AS path_count
            FROM ip_path_counts ipc
            JOIN visitor_activity va ON va.ip_hash = ipc.ip_hash
            WHERE va.bot_type != 'bot'
            GROUP BY ipc.ip_hash
            HAVING path_count > 50
        """)
        rows = cursor.fetchall()
        for row in rows:
            ip_hash = row["ip_hash"]
            cursor.execute(
                "UPDATE visitor_activity SET bot_type = 'bot', ua_score = 1.0 WHERE ip_hash = ?",
                (ip_hash,),
            )
            cursor.execute("SELECT id FROM bot_logs WHERE ip_hash = ? LIMIT 1", (ip_hash,))
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO bot_logs (ip_hash, reason, bot_type, confidence) VALUES (?, ?, ?, ?)",
                    (ip_hash, "Behavioral: High Unique Path Count (retroactive)", "bot", 1.0),
                )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()

@app.get("/")
def read_root():
    return {"message": "Privacy Visitor Tracker API is running"}

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return 204

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8011)
