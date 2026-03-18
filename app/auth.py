import base64
import time
from typing import Optional
from fastapi import HTTPException, Header, Request, Query
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
from .database import get_db

_UNAUTHORIZED = HTTPException(status_code=401, detail="Unauthorized")

def verify_signature(
    request: Request,
    site_id: str = Query("default"),
    x_timestamp: Optional[int] = Header(None, alias="X-Timestamp"),
    x_signature: Optional[str] = Header(None, alias="X-Signature")
):
    """
    Verifies the request signature using the stored public key for the site.
    If no key is stored, allows access (optional auth).
    Message format signed by client: "{site_id}:{x_timestamp}" (hex-encoded Ed25519 signature).
    """
    # 1. Check if site has a public key registered
    conn = get_db(site_id)
    cursor = conn.cursor()
    cursor.execute("SELECT key_value FROM auth_config WHERE key_type = 'public_key'")
    row = cursor.fetchone()
    conn.close()

    if not row:
        # No key configured — allow public access
        return True

    # 2. Key exists; auth is required
    if not x_timestamp or not x_signature:
        raise _UNAUTHORIZED

    public_key_hex = row["key_value"]

    # 3. Verify timestamp to prevent replay attacks (5-minute window)
    current_time = int(time.time())
    if abs(current_time - x_timestamp) > 300:
        raise _UNAUTHORIZED

    # 4. Verify Ed25519 signature
    try:
        message = f"{site_id}:{x_timestamp}".encode()

        try:
            signature = bytes.fromhex(x_signature)
        except ValueError:
            raise _UNAUTHORIZED

        try:
            public_key_bytes = bytes.fromhex(public_key_hex)
            public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
        except ValueError:
            raise HTTPException(status_code=500, detail="Internal server error")

        public_key.verify(signature, message)
        return True

    except InvalidSignature:
        raise _UNAUTHORIZED
    except HTTPException:
        raise
    except Exception:
        raise _UNAUTHORIZED
