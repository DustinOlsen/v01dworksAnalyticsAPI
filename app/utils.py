import hashlib
import os
from pathlib import Path
import geoip2.database
from user_agents import parse

# Salt for hashing IP addresses. 
# Created once and stored to maintain consistency across restarts.
SALT_FILE = Path("data/.salt")

def get_salt():
    # Ensure parent directory exists
    SALT_FILE.parent.mkdir(exist_ok=True)
    
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
    # Check for Country or City database
    db_files = ["GeoLite2-Country.mmdb", "GeoLite2-City.mmdb"]
    db_path = next((f for f in db_files if os.path.exists(f)), None)
    
    if not db_path:
        return "Unknown"

    try:
        with geoip2.database.Reader(db_path) as reader:
            # .country() works for both City and Country databases
            response = reader.country(ip_address)
            return response.country.iso_code or "Unknown"
    except (FileNotFoundError, Exception):
        return "Unknown"

def parse_user_agent_info(ua_string: str):
    """
    Parses User-Agent string to extract Device, Browser, and OS info.
    """
    if not ua_string:
        return {
            "device": "Unknown",
            "browser": "Unknown",
            "os": "Unknown"
        }
        
    user_agent = parse(ua_string)
    
    # Device Type
    if user_agent.is_mobile:
        device = "Mobile"
    elif user_agent.is_tablet:
        device = "Tablet"
    elif user_agent.is_pc:
        device = "Desktop"
    elif user_agent.is_bot:
        device = "Bot"
    else:
        device = "Other"
        
    # Browser Family (e.g., "Chrome", "Firefox", "Mobile Safari")
    browser = user_agent.browser.family
    
    # OS Family (e.g., "Windows", "Mac OS X", "iOS", "Android")
    os_family = user_agent.os.family
    
    return {
        "device": device,
        "browser": browser,
        "os": os_family
    }
