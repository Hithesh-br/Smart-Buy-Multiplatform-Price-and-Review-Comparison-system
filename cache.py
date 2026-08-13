"""
cache.py
========
Smart-Buy: Multiplatform Price Review Comparison System
======================================================
In-memory caching module using cachetools.TTLCache (60-second TTL).
Requirement 4: Cache recent results for 60 seconds (CACHE_TTL = 60).
Requirement 5: Fallback to MongoDB product_cache.
"""

import logging
from cachetools import TTLCache
from database import get_product_cache, save_product_cache

logger = logging.getLogger("smartbuy.cache")

CACHE_TTL = 60
_SEARCH_CACHE = TTLCache(maxsize=500, ttl=CACHE_TTL)


def get_cached_search(cache_key: str, ttl_seconds: int = CACHE_TTL):
    """
    Retrieve cached search data if available and not expired (60s TTL).
    First checks in-memory TTLCache, then MongoDB product_cache.
    """
    if not cache_key:
        return None

    # Memory cache check
    if cache_key in _SEARCH_CACHE:
        logger.info(f"Memory Cache HIT for key: {cache_key[:60]}...")
        return _SEARCH_CACHE[cache_key]

    # MongoDB product_cache check
    db_cached = get_product_cache(cache_key, ttl_seconds=ttl_seconds)
    if db_cached:
        _SEARCH_CACHE[cache_key] = db_cached
        return db_cached

    return None


def set_cached_search(cache_key: str, data: dict):
    """
    Store search result data in memory TTL cache and MongoDB product_cache.
    """
    if cache_key and data:
        _SEARCH_CACHE[cache_key] = data
        save_product_cache(cache_key, data)
        logger.info(f"Cache STORE for key: {cache_key[:60]}...")


def clear_cache():
    """Clear all items from the memory search cache."""
    _SEARCH_CACHE.clear()
    logger.info("Search cache cleared.")

