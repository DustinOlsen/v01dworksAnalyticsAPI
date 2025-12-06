import base64
import time
from typing import Optional
from fastapi import HTTPException, Header, Request, Query
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature
from .database import get_db

def verify_signature(
    request: Request,
    site_id: str = Query("default"),
    x_timestamp: Optional[int] = Header(None, alias="X-Timestamp"),
    x_signature: Optional[str] = Header(None, alias="X-Signature")
):
    """
    Verifies the request signature using the stored public key for the site.
    If no key is stored, allows access (optional auth).
    """
    # 1. Check if site has a public key
    conn = get_db(site_id)
    cursor = conn.cursor()
    cursor.execute("SELECT key_value FROM auth_config WHERE key_type = 'public_key'")
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        # No key configured, allow public access
        return True
        
    # 2. Key exists, so Auth is REQUIRED
    if not x_timestamp or not x_signature:
        raise HTTPException(status_code=401, detail="Authentication required (Missing X-Timestamp or X-Signature)")
    
    public_key_hex = row["key_value"]
    
    # 3. Verify Timestamp (prevent replay attacks)
    # Allow 5 minute window
    current_time = int(time.time())
    if abs(current_time - x_timestamp) > 300:
        raise HTTPException(status_code=401, detail="Timestamp expired or invalid")
        
    # 4. Verify Signature
    try:
        # Reconstruct the message: "site_id:timestamp"
        # We use the site_id from the query param as the source of truth
        message = f"{site_id}:{x_timestamp}".encode()
        
        # Decode signature (expecting Hex)
        try:
            signature = bytes.fromhex(x_signature)
        except ValueError:
            raise HTTPException(status_code=401, detail="Invalid signature format (Hex expected)")
            
        # Load Public Key (Ed25519)
        # We expect the key to be stored as a Hex string of the raw bytes
        try:
            public_key_bytes = bytes.fromhex(public_key_hex)
            public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
        except ValueError:
             raise HTTPException(status_code=500, detail="Stored public key is invalid")

        public_key.verify(signature, message)
        return True
        
    except InvalidSignature:
        raise HTTPException(status_code=401, detail="Invalid signature")
    except Exception as e:
        print(f"Auth Error: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")
