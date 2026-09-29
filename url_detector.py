"""
url_detector.py
===============
SmartBuy URL Detection & Validation Module.

Validates product URLs and identifies whether user input is:
- normal product text: {"type": "product_name"}
- Amazon URL: {"type": "product_url", "platform": "amazon"}
- Flipkart URL / Short URL (dl.flipkart.com/s/...): {"type": "product_url", "platform": "flipkart"}
- Meesho URL: {"type": "product_url", "platform": "meesho"}
"""

import re
import urllib.parse
from typing import Optional, Dict, Any

AMAZON_DOMAINS = {
    "amazon.in", "www.amazon.in", "amazon.co.in", "www.amazon.co.in",
    "amazon.com", "www.amazon.com", "amzn.in", "amzn.to"
}
FLIPKART_DOMAINS = {"flipkart.com", "www.flipkart.com", "dl.flipkart.com", "fkrt.it"}
MEESHO_DOMAINS = {"meesho.com", "www.meesho.com"}


def is_valid_http_url(url: str) -> bool:
    """Check if string is a well-formed HTTP/HTTPS URL."""
    if not url or not isinstance(url, str):
        return False
    clean = url.strip()
    try:
        parsed = urllib.parse.urlparse(clean)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def normalize_product_url(raw_url: str, platform: Optional[str] = None) -> str:
    """
    Normalizes URL encoding and removes tracking/referral parameters
    while strictly preserving the canonical product identity.
    """
    if not raw_url or not isinstance(raw_url, str):
        return ""
    clean = raw_url.strip()
    try:
        parsed = urllib.parse.urlparse(clean)
        plat = platform or detect_platform_from_url(clean)

        if plat == "amazon":
            asin = extract_amazon_asin(clean)
            if asin:
                # Use canonical Amazon.in URL
                domain = "www.amazon.in" if "amazon.in" in (parsed.hostname or "") or "amzn" in (parsed.hostname or "") else (parsed.hostname or "www.amazon.in")
                return f"https://{domain}/dp/{asin}"
            # Strip standard Amazon tracking params
            tracking_params = {
                'ref', 'ref_', 'tag', 'linkCode', 'psc', 'th', 'creative', 'camp',
                'creativeASIN', 'ascsubtag', 'pf_rd_r', 'pf_rd_p', 'pf_rd_m', 'pf_rd_s',
                'pf_rd_t', 'pf_rd_i', 'crid', 'sprefix', 'keywords', 'qid', 'sr'
            }
            qs = urllib.parse.parse_qs(parsed.query)
            clean_qs = {k: v for k, v in qs.items() if k.lower() not in tracking_params}
            new_query = urllib.parse.urlencode(clean_qs, doseq=True)
            return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, ""))

        elif plat == "flipkart":
            # For short share links, keep clean URL for resolver
            if "dl.flipkart.com/s/" in clean or "fkrt.it/" in clean:
                return clean
            # For standard Flipkart links, preserve pid and path
            pid = extract_flipkart_id(clean)
            tracking_params = {
                'lid', 'marketplace', 'spotlightTagId', 'store', 'srno', 'otracker',
                'otracker1', 'fm', 'iid', 'ppn', 'ppt', 'qH', 'affid'
            }
            qs = urllib.parse.parse_qs(parsed.query)
            clean_qs = {k: v for k, v in qs.items() if k.lower() not in tracking_params}
            if pid and 'pid' not in clean_qs:
                clean_qs['pid'] = [pid]
            new_query = urllib.parse.urlencode(clean_qs, doseq=True)
            return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, ""))

        elif plat == "meesho":
            tracking_params = {
                'ref', 'source', 'campaign', 'utm_source', 'utm_medium',
                'utm_campaign', 'utm_term', 'utm_content'
            }
            qs = urllib.parse.parse_qs(parsed.query)
            clean_qs = {k: v for k, v in qs.items() if k.lower() not in tracking_params}
            new_query = urllib.parse.urlencode(clean_qs, doseq=True)
            return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, ""))

    except Exception:
        pass
    return clean


def detect_search_type(query: str) -> Dict[str, Any]:
    """
    Detect whether user entered:
    - a product name text search: {"type": "product_name"}
    - or a product URL: {"type": "product_url", "platform": "amazon"|"flipkart"|"meesho"}

    Examples:
    "Samsung Galaxy S24" -> {"type": "product_name"}
    "BAJAJ coconut oil" -> {"type": "product_name"}
    "https://dl.flipkart.com/s/0chNErNNNN" -> {"type": "product_url", "platform": "flipkart"}
    "https://www.amazon.in/dp/B0CHX1W1XY" -> {"type": "product_url", "platform": "amazon"}
    "https://www.meesho.com/s/p/4abc12" -> {"type": "product_url", "platform": "meesho"}
    """
    if not query or not isinstance(query, str):
        return {"type": "product_name"}

    q_clean = query.strip()

    # Look for URL pattern anywhere in the query string
    url_match = re.search(r'https?://[^\s<>"]+', q_clean)
    if url_match:
        test_url = url_match.group(0)
    else:
        # Check if starts with a recognized marketplace domain
        if re.match(r'^(?:www\.)?(?:dl\.)?(amazon\.(?:in|com|co\.in)|flipkart\.com|meesho\.com|amzn\.(?:in|to)|fkrt\.it)/', q_clean, re.I):
            test_url = "https://" + q_clean
        else:
            return {"type": "product_name"}

    platform = detect_platform_from_url(test_url)
    if platform:
        canonical = normalize_product_url(test_url, platform)
        return {
            "type": "product_url",
            "platform": platform,
            "url": canonical or test_url
        }

    return {"type": "product_name"}


def detect_platform_from_url(url: str) -> Optional[str]:
    """
    Detect the marketplace platform from product URL.
    Returns: 'amazon', 'flipkart', 'meesho', or None.
    """
    if not url or not isinstance(url, str):
        return None

    clean = url.strip().lower()

    # Domain substring checks matching Section 2 requirements
    if "amazon.in" in clean or "amazon.com" in clean or "amazon.co.in" in clean or "amzn.in" in clean or "amzn.to" in clean:
        return "amazon"
    if "flipkart.com" in clean or "fkrt.it" in clean:
        return "flipkart"
    if "meesho.com" in clean:
        return "meesho"

    if not is_valid_http_url(clean):
        if clean.startswith("www.") or re.match(r'^(?:dl\.)?(amazon|flipkart|meesho|amzn)\.', clean, re.I):
            clean = "https://" + clean
        else:
            return None

    try:
        parsed = urllib.parse.urlparse(clean)
        hostname = (parsed.hostname or "").lower()

        if any(hostname == d or hostname.endswith("." + d) for d in AMAZON_DOMAINS) or "amazon" in hostname:
            return "amazon"
        if any(hostname == d or hostname.endswith("." + d) for d in FLIPKART_DOMAINS) or "flipkart" in hostname:
            return "flipkart"
        if any(hostname == d or hostname.endswith("." + d) for d in MEESHO_DOMAINS) or "meesho" in hostname:
            return "meesho"
    except Exception:
        pass

    return None


def extract_amazon_asin(url: str) -> Optional[str]:
    """Extract 10-character ASIN from Amazon URL."""
    clean_url = url.strip()
    match = re.search(r'/(?:dp|gp/product|gp/aw/d|product)/([A-Z0-9]{10})(?:[/?&#]|$)', clean_url, re.IGNORECASE)
    if match:
        return match.group(1).upper()

    match2 = re.search(r'/asin/([A-Z0-9]{10})(?:[/?&#]|$)', clean_url, re.IGNORECASE)
    if match2:
        return match2.group(1).upper()

    parsed = urllib.parse.urlparse(clean_url)
    qs = urllib.parse.parse_qs(parsed.query)
    if 'asin' in qs and qs['asin']:
        return qs['asin'][0].strip().upper()

    return None


def extract_flipkart_id(url: str) -> Optional[str]:
    """Extract product ID (PID) or product slug from Flipkart URL."""
    clean_url = url.strip()
    parsed = urllib.parse.urlparse(clean_url)
    qs = urllib.parse.parse_qs(parsed.query)

    if 'pid' in qs and qs['pid']:
        return qs['pid'][0].strip()

    match = re.search(r'/p/(itm[a-zA-Z0-9]+)', parsed.path)
    if match:
        return match.group(1)

    match2 = re.search(r'/p/([a-zA-Z0-9]+)', parsed.path)
    if match2:
        return match2.group(1)

    # For short URLs: /s/XXXX
    match3 = re.search(r'/s/([a-zA-Z0-9]+)', parsed.path)
    if match3:
        return match3.group(1)

    return None


def extract_meesho_id(url: str) -> Optional[str]:
    """Extract product code/slug from Meesho URL."""
    clean_url = url.strip()
    parsed = urllib.parse.urlparse(clean_url)

    match = re.search(r'/(?:s/)?p/([a-zA-Z0-9]+)', parsed.path)
    if match:
        return match.group(1)

    segments = [s for s in parsed.path.split('/') if s]
    if segments:
        last = segments[-1]
        if re.match(r'^[a-zA-Z0-9]+$', last) and len(last) >= 4:
            return last

    return None


def validate_and_detect_url(raw_url: str) -> Dict[str, Any]:
    """
    Validates user input URL and returns detailed metadata.
    Supports Flipkart short URLs (dl.flipkart.com/s/...).
    """
    if not raw_url or not isinstance(raw_url, str):
        return {
            "is_valid": False,
            "platform": None,
            "platform_name": None,
            "canonical_url": "",
            "original_url": "",
            "product_id": None,
            "error": "Please enter a product URL."
        }

    url = raw_url.strip()
    if not is_valid_http_url(url):
        if url.startswith("www.") or re.match(r'^(?:dl\.)?(amazon|flipkart|meesho|amzn)\.', url, re.IGNORECASE):
            url = "https://" + url
        else:
            return {
                "is_valid": False,
                "platform": None,
                "platform_name": None,
                "canonical_url": "",
                "original_url": raw_url,
                "product_id": None,
                "error": "Invalid URL format. Please provide a full URL starting with https://."
            }

    platform = detect_platform_from_url(url)
    if not platform:
        return {
            "is_valid": False,
            "platform": None,
            "platform_name": None,
            "canonical_url": "",
            "original_url": url,
            "product_id": None,
            "error": "Unsupported platform. SmartBuy supports Amazon India, Flipkart, and Meesho URLs."
        }

    parsed = urllib.parse.urlparse(url)
    path = parsed.path.lower()

    # Reject standard search result or listing pages (unless it's a short URL dl.flipkart.com/s/...)
    if platform == "amazon":
        if ("/s" in path and not path.startswith("/s/")) or "k=" in parsed.query or "field-keywords" in parsed.query:
            return {
                "is_valid": False,
                "platform": platform,
                "platform_name": "Amazon",
                "canonical_url": "",
                "original_url": url,
                "product_id": None,
                "error": "This is an Amazon search results page. Please provide a direct product page URL."
            }
        is_short = "amzn.in/d/" in url or "amzn.to/" in url
        resolved_url = url
        asin = extract_amazon_asin(url)
        if is_short and not asin:
            try:
                from search.url_resolver import resolve_product_url
                resolved_url = resolve_product_url(url, "amazon")
                asin = extract_amazon_asin(resolved_url) or asin
            except Exception:
                pass
        return {
            "is_valid": True,
            "platform": "amazon",
            "platform_name": "Amazon",
            "canonical_url": f"https://www.amazon.in/dp/{asin}" if asin else resolved_url,
            "original_url": url,
            "product_id": asin,
            "is_short_url": is_short,
            "error": None
        }

    elif platform == "flipkart":
        # Check if it's a Flipkart search page, but NOT a short share link dl.flipkart.com/s/...
        if ("/search" in path or "q=" in parsed.query) and "dl.flipkart.com" not in (parsed.hostname or ""):
            return {
                "is_valid": False,
                "platform": platform,
                "platform_name": "Flipkart",
                "canonical_url": "",
                "original_url": url,
                "product_id": None,
                "error": "This is a Flipkart search page. Please provide a direct product page URL."
            }

        # Flipkart short URLs dl.flipkart.com/s/XXXX are VALID product share URLs!
        is_short = "dl.flipkart.com/s/" in url or "dl.flipkart.com/dl/" in url or "fkrt.it/" in url
        resolved_url = url
        pid = extract_flipkart_id(url)
        if is_short:
            try:
                from search.url_resolver import resolve_product_url
                resolved_url = resolve_product_url(url, "flipkart")
                pid = extract_flipkart_id(resolved_url) or pid
            except Exception:
                pass
        return {
            "is_valid": True,
            "platform": "flipkart",
            "platform_name": "Flipkart",
            "canonical_url": resolved_url,
            "original_url": url,
            "product_id": pid,
            "is_short_url": is_short,
            "error": None
        }

    elif platform == "meesho":
        if "/search" in path and not path.startswith("/s/p/"):
            return {
                "is_valid": False,
                "platform": platform,
                "platform_name": "Meesho",
                "canonical_url": "",
                "original_url": url,
                "product_id": None,
                "error": "This is a Meesho search page. Please provide a direct product page URL."
            }
        mid = extract_meesho_id(url)
        return {
            "is_valid": True,
            "platform": "meesho",
            "platform_name": "Meesho",
            "canonical_url": url,
            "original_url": url,
            "product_id": mid,
            "error": None
        }

    return {
        "is_valid": False,
        "platform": None,
        "platform_name": None,
        "canonical_url": "",
        "original_url": url,
        "product_id": None,
        "error": "Unable to validate product URL."
    }
