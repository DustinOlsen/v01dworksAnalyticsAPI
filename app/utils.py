import hashlib
import os
from pathlib import Path
import geoip2.database

# Salt for hashing IP addresses. 
# Created once and stored to maintain consistency across restarts.
SALT_FILE = Path(".salt")

def get_salt():
    if not SALT_FILE.exists():
        salt = os.urandom(32)
        with open(SALT_FILE, "wb") as f:
            f.write(salt)
    with open(SALT_FILE, "rb") as f:
        return f.read()

SALT = get_salt()

def hash_ip(ip_address: str) -> str:
    """
    Hashes an IP address with a salt.
    This ensures we can track uniqueness without storing the actual IP.
    """
    return hashlib.sha256(SALT + ip_address.encode()).hexdigest()

def get_country_from_ip(ip_address: str) -> str:
    """
    Resolves an IP address to a country code using GeoLite2.
    Returns 'Unknown' if database is missing or IP is not found.
    """
    # You need to download GeoLite2-City.mmdb and place it in the project root
    db_path = "GeoLite2-City.mmdb"
    try:
        with geoip2.database.Reader(db_path) as reader:
            response = reader.city(ip_address)
            return response.country.iso_code or "Unknown"
    except (FileNotFoundError, Exception):
        return "Unknown"
