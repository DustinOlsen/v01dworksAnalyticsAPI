import hashlib
import os
import re
from pathlib import Path
from urllib.parse import urlparse
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

# Legitimate search engine / social-media crawlers
_CRAWLER_RE = re.compile(
    r"Googlebot|Bingbot|Slurp|DuckDuckBot|Baiduspider|YandexBot|Applebot|"
    r"facebookexternalhit|Twitterbot|LinkedInBot|AdsBot-Google|Mediapartners-Google|"
    r"PetalBot|Pinterest|Listing-Bot",
    re.IGNORECASE,
)

# Scrapers, headless browsers, and automation tools
_BOT_SIGNATURE_RE = re.compile(
    r"HeadlessChrome|PhantomJS|Selenium|Puppeteer|wkhtmlto|"
    r"Python-urllib|python-requests|python-httpx|"
    r"Go-http-client|Java/|libwww|"
    r"curl/|Wget/|"
    r"AhrefsBot|SemrushBot|MJ12bot|DotBot|rogerbot|SiteAuditBot|"
    r"BLEXBot|DataForSeoBot|masscan|zgrab|nuclei",
    re.IGNORECASE,
)


def parse_user_agent_info(ua_string: str) -> dict:
    """
    Parses a User-Agent string and returns device, browser, OS, bot_type, and ua_score.
    bot_type: "none" (human), "crawler" (legit search engine), "bot" (scraper/headless)
    ua_score:  0.0 (human),   0.5 (crawler),                   1.0 (bot)
    """
    if not ua_string or not ua_string.strip():
        return {
            "device": "Bot",
            "browser": "Unknown",
            "os": "Unknown",
            "bot_type": "bot",
            "ua_score": 1.0,
        }

    # 1. Known legitimate crawlers (checked before the UA library to avoid
    #    false-negatives where the library doesn't recognise the crawler)
    if _CRAWLER_RE.search(ua_string):
        user_agent = parse(ua_string)
        return {
            "device": "Crawler",
            "browser": user_agent.browser.family,
            "os": user_agent.os.family,
            "bot_type": "crawler",
            "ua_score": 0.5,
        }

    user_agent = parse(ua_string)

    # 2. Known bot signatures or UA-library bot flag
    if _BOT_SIGNATURE_RE.search(ua_string) or user_agent.is_bot:
        return {
            "device": "Bot",
            "browser": user_agent.browser.family,
            "os": user_agent.os.family,
            "bot_type": "bot",
            "ua_score": 1.0,
        }

    # 3. Human visitor
    if user_agent.is_mobile:
        device = "Mobile"
    elif user_agent.is_tablet:
        device = "Tablet"
    elif user_agent.is_pc:
        device = "Desktop"
    else:
        device = "Other"

    return {
        "device": device,
        "browser": user_agent.browser.family,
        "os": user_agent.os.family,
        "bot_type": "none",
        "ua_score": 0.0,
    }

def parse_referrer_category(referrer_url: str) -> str:
    """
    Categorizes the referrer URL into 'Direct', 'Search Engine', 'Social Media', or 'Other'.
    """
    if not referrer_url:
        return "Direct"
    
    try:
        parsed = urlparse(referrer_url)
        hostname = parsed.netloc.lower()
        
        # Common Search Engines
        search_engines = [
            "google.", "bing.", "yahoo.", "duckduckgo.", "baidu.", "yandex.", "ask.com", "aol.com", "ecosia.org"
        ]
        if any(se in hostname for se in search_engines):
            return "Search Engine"
            
        # Common Social Media
        social_media = [
            "facebook.", "twitter.", "t.co", "instagram.", "linkedin.", "pinterest.", "reddit.", "tiktok.", "youtube.", "whatsapp."
        ]
        if any(sm in hostname for sm in social_media):
            return "Social Media"
            
        return "Other"
    except:
        return "Unknown"
