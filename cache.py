"""
cache.py
========
Platform-isolated caching module for marketplace search results.
Enforces that Amazon, Flipkart, and Meesho results have distinct cache keys:
    platform + ":" + normalized_query (e.g. 'amazon:ghar soap')
Prevents platform data cross-contamination and supports ?fresh=1 cache bypass.
"""

import os
import time
import logging
from cachetools import TTLCache
from search.normalizer import normalize_query

logger = logging.getLogger("smartbuy.cache")

# Short TTL (1800s / 30 mins) for fresh e-commerce pricing
CACHE_TTL = int(os.getenv("SCRAPER_CACHE_TTL", "1800"))
_PLATFORM_CACHE = TTLCache(maxsize=500, ttl=CACHE_TTL)
_SEARCH_CACHE = TTLCache(maxsize=200, ttl=CACHE_TTL)
_URL_CACHE = TTLCache(maxsize=200, ttl=CACHE_TTL)


def build_url_cache_key(platform: str, url: str) -> str:
    """Construct URL cache key: e.g. 'amazon:https://www.amazon.in/dp/B0... '."""
    clean_p = (platform or "").lower().strip()
    clean_u = (url or "").strip()
    return f"{clean_p}:{clean_u}"


def get_cached_url_product(platform: str, url: str, bypass_fresh: bool = False):
    """Retrieve cached scraped product for a canonical product URL."""
    if bypass_fresh or not is_cache_enabled():
        return None
    key = build_url_cache_key(platform, url)
    if key in _URL_CACHE:
        entry = _URL_CACHE[key]
        logger.info(f"[CACHE] URL Hit for '{key}'")
        return entry.get("product")
    return None


def set_cached_url_product(platform: str, url: str, product: dict):
    """Cache product for a canonical product URL."""
    if not is_cache_enabled() or not product:
        return
    key = build_url_cache_key(platform, url)
    _URL_CACHE[key] = {
        "timestamp": time.time(),
        "platform": platform.lower(),
        "url": url,
        "product": product,
        "scraped_at": product.get("scraped_at")
    }
    logger.info(f"[CACHE] Stored product for URL '{key}'")



def is_cache_enabled() -> bool:
    """Check whether scraping cache is enabled via env (default true)."""
    return os.environ.get("SCRAPER_CACHE_ENABLED", "true").lower() in ("true", "1", "yes")


def build_platform_cache_key(platform: str, query: str) -> str:
    """Construct platform-isolated cache key: e.g. 'amazon:ghar soap'."""
    norm_q = normalize_query(query)
    clean_p = (platform or "").lower().strip()
    return f"{clean_p}:{norm_q}"


def get_platform_cached_results(platform: str, query: str, bypass_fresh: bool = False):
    """
    Retrieve cached results for a specific platform.
    Bypassed when fresh=1 is requested or cache is disabled.
    """
    if bypass_fresh or not is_cache_enabled():
        return None
    key = build_platform_cache_key(platform, query)
    if key in _PLATFORM_CACHE:
        entry = _PLATFORM_CACHE[key]
        logger.info(f"[CACHE] Hit for platform key '{key}' ({len(entry.get('results', []))} items)")
        return entry
    return None


def set_platform_cached_results(platform: str, query: str, results: list, scrape_status: str):
    """
    Store scraped results for a specific platform in TTL cache.
    Never caches empty/error responses as permanent success.
    """
    if not is_cache_enabled() or not results:
        return
    key = build_platform_cache_key(platform, query)
    entry = {
        "timestamp": time.time(),
        "platform": platform.lower(),
        "query": query,
        "results": results,
        "scrape_status": scrape_status
    }
    _PLATFORM_CACHE[key] = entry
    logger.info(f"[CACHE] Stored {len(results)} items for '{key}'")


def get_cached_search(cache_key: str, bypass_fresh: bool = False):
    """Legacy/unified search cache lookup."""
    if bypass_fresh or not is_cache_enabled():
        return None
    if cache_key in _SEARCH_CACHE:
        logger.info(f"[CACHE] Hit for unified query key: {cache_key[:50]}...")
        return _SEARCH_CACHE[cache_key]
    return None


def set_cached_search(cache_key: str, data: dict):
    """Store unified comparison search result."""
    if not is_cache_enabled() or not data:
        return
    _SEARCH_CACHE[cache_key] = data
    logger.info(f"[CACHE] Stored unified query key: {cache_key[:50]}...")


def clear_cache():
    """Clear all caches."""
    _PLATFORM_CACHE.clear()
    _SEARCH_CACHE.clear()
    logger.info("[CACHE] Search caches cleared.")
